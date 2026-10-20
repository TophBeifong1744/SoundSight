"""同一Linux/PYNQ的双核入口：CPU1取帧/调用C/提交，CPU0控制/落盘/显示。

不加载bit、不复位PS。默认BIST且不运动。当前公共ABI仅支持水平轴。
"""
import contextlib
import multiprocessing as mp
import os
import sys
import time

from ps_client import Client, Solver, FAULT
from run_capture import (address_from_hwh, argument_parser, capture, durable_sink,
                         prepare_args, single_owner)

# 沿用现有250ms软件等待上界；这不是板测的实时服务保证。
ACK_TIMEOUT = .25
POLL_INTERVAL = .01
START_TIMEOUT = 5.0  # 仅进程启动/导入库，不是采集服务预算。
HOST_TIMEOUT = .75  # 失联检测；不延长acquire/ACK/排空各自的上界。


class Cancelled(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel.is_set():raise Cancelled('主进程要求停止；保留未消费帧')


def validate_cpus(host_cpu, worker_cpu):
    if not hasattr(os,'sched_getaffinity') or not hasattr(os,'sched_setaffinity'):
        raise RuntimeError('需要Linux CPU affinity；Windows不能代替目标PYNQ运行')
    available=os.sched_getaffinity(0)
    if host_cpu==worker_cpu or not {host_cpu,worker_cpu}<=available:
        raise RuntimeError('需要两个可用Linux核；当前允许CPU：'+str(sorted(available)))
    return available


@contextlib.contextmanager
def pinned(cpu):
    previous=os.sched_getaffinity(0)
    os.sched_setaffinity(0,{cpu})
    try:
        if os.sched_getaffinity(0)!={cpu}:raise RuntimeError('CPU affinity未生效')
        yield
    finally:os.sched_setaffinity(0,previous)


class SavedBeforeConsume:
    """一次一条IPC记录；CPU0完成fsync才确认，CPU1收到确认才继续。"""
    def __init__(self, connection, cancel, timeout=ACK_TIMEOUT):
        self.connection=connection;self.cancel=cancel;self.timeout=timeout;self.ticket=0

    def __call__(self, record):
        check_cancel(self.cancel);self.ticket+=1
        self.connection.send(('record',self.ticket,record))
        deadline=time.monotonic()+self.timeout
        while True:
            check_cancel(self.cancel)
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('等待落盘确认超时；保留锁帧')
            if self.connection.poll(min(POLL_INTERVAL,remaining)):
                reply=self.connection.recv()
                if time.monotonic()>=deadline:raise TimeoutError('落盘确认超过等待上界；保留锁帧')
                if reply!=('saved',self.ticket):raise RuntimeError('落盘确认与当前记录不一致')
                check_cancel(self.cancel)
                return


class InterruptibleClient(Client):
    def __init__(self, ip, solver, cancel):
        super().__init__(ip,solver);self.cancel=cancel

    def record_one(self, *args, **kwargs):
        check_cancel(self.cancel)
        return super().record_one(*args,**kwargs)

    def command(self, *args, **kwargs):
        check_cancel(self.cancel)
        return super().command(*args,**kwargs)

    def consume(self, *args, **kwargs):
        check_cancel(self.cancel)
        return super().consume(*args,**kwargs)


def worker_session(connection,cancel,client,options,config,info):
    """唯一硬件所有者；错误先由capture/Client请求STOP，再向父进程报告。"""
    stats={}
    try:
        connection.send(('ready',info))
        sink=SavedBeforeConsume(connection,cancel)
        # 清错前留原始故障和操作者的明确选择，不静默清历史异常。
        sink(dict(event='startup',fault_before=client.read(FAULT),
                  requested_clear_faults=options.clear_faults,**info))
        check_cancel(cancel)
        saved=capture(client,sink,options.mode,options.frames,options.drain_existing,
                      config,options.watchdog_ticks,options.clear_faults,stats)
        connection.send(('done',dict(saved=saved,stats=stats)))
    except BaseException as exc:
        # 启动记录阶段也可能失败；此时尚未进入capture的finally。
        try:client.disable()
        except Exception as cleanup:
            print('worker停用未确认：'+str(cleanup),file=sys.stderr)
        try:connection.send(('error',dict(error=type(exc).__name__+': '+str(exc),stats=stats)))
        except (EOFError,OSError):pass
    finally:connection.close()


def worker_main(connection,cancel,options,base,size,config):
    try:
        # spawn的子进程独立导入PYNQ、创建MMIO；父进程不持有MMIO映射。
        with pinned(options.worker_cpu),single_owner(options.lock_file):
            solver=Solver(options.library)
            from pynq import MMIO
            client=InterruptibleClient(MMIO(base,size),solver,cancel)
            client.identify()  # ID不匹配时不向该地址写STOP或其它控制。
            info=dict(worker_pid=os.getpid(),worker_cpu=options.worker_cpu,
                      worker_affinity=sorted(os.sched_getaffinity(0)))
            worker_session(connection,cancel,client,options,config,info)
    except BaseException as exc:
        try:connection.send(('error',dict(error=type(exc).__name__+': '+str(exc))))
        except (EOFError,OSError):pass
    finally:connection.close()


def collect(connection,worker,cancel,sink,host_info):
    """父进程只保存和确认，不取数、不提交角度；异常立即通知所有者停止。"""
    ready=False
    try:
        while True:
            timeout=HOST_TIMEOUT if ready else START_TIMEOUT
            if not connection.poll(timeout):
                raise TimeoutError('算法进程未响应；已请求停止')
            message=connection.recv();kind=message[0]
            if kind=='ready':
                ready=True
                print('PYNQ双核已启动：',dict(host_info,**message[1]),flush=True)
            elif kind=='record':
                _,ticket,record=message
                sink(record)  # 必须write/flush/fsync成功后才回ACK。
                connection.send(('saved',ticket))
            elif kind=='done':
                sink(dict(event='finished',**host_info,**message[1]))
                return message[1]
            elif kind=='error':
                sink(dict(event='failed',**host_info,**message[1]))
                raise RuntimeError('算法进程失败：'+message[1]['error'])
            else:raise RuntimeError('未知进程消息')
    finally:
        cancel.set()


def finish_worker(worker,cancel):
    cancel.set();worker.join(HOST_TIMEOUT)
    if worker.is_alive():
        # C库或驱动挂死时Python不能保证STOP；不能伪称已停止执行器。
        worker.terminate();worker.join(HOST_TIMEOUT)
        raise RuntimeError('算法进程无响应而被终止；硬件STOP未经确认，须由A检查现场/看门狗')


def main(argv=None):
    parser=argument_parser();parser.description=__doc__
    parser.add_argument('--host-cpu',type=int,default=0)
    parser.add_argument('--worker-cpu',type=int,default=1)
    args=parser.parse_args(argv);config=prepare_args(args,parser)
    validate_cpus(args.host_cpu,args.worker_cpu)
    base,size=address_from_hwh(args.hwh,args.ip)
    context=mp.get_context('spawn');parent,child=context.Pipe();cancel=context.Event()
    worker=context.Process(target=worker_main,args=(child,cancel,args,base,size,config),
                           name='soundsight-c-solver')
    # 输出文件先打开，避免因路径错误启动采集。先spawn，后固定父进程CPU。
    with args.output.open('a',encoding='utf-8') as handle:
        worker.start();child.close()
        try:
            with pinned(args.host_cpu):
                info=dict(host_pid=os.getpid(),host_cpu=args.host_cpu,
                          host_affinity=sorted(os.sched_getaffinity(0)))
                result=collect(parent,worker,cancel,durable_sink(handle),info)
        finally:
            original=sys.exc_info()[0]
            parent.close()
            try:finish_worker(worker,cancel)
            except Exception as exc:
                if original is None:raise
                print(str(exc),file=sys.stderr)
    print('已消费帧数：',result['saved'],'；水平动作启用：',args.horizontal_motion)
    return 0


if __name__=='__main__':raise SystemExit(main())
