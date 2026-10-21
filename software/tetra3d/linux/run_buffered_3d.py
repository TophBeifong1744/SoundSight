"""三维无动作RAM入口：复用主线有界队列/20秒启动，CPU1取数及C求解。

完整记录入RAM后确认消费，断电可能丢未落盘记录；CPU0后台写SD。
本入口默认不逐帧显示，结果在JSONL；不加载bit、不复位、不动作。
"""
import multiprocessing as mp
import os
import sys

from runtime_3d import Client3D,SolverAdapter3D,durable_sink_3d
from solver_3d import Solver3D
from run_smp_3d import argument_parser,prepare_args
from run_capture import address_from_hwh,single_owner
from ram_queue import RamQueue,create_ram_directory
import run_buffered as shared
from run_smp import pinned,validate_cpus,finish_worker


def worker_main(connection,abort,stop_new,options,base,size,geometry):
    try:
        with pinned(options.worker_cpu),single_owner(options.lock_file):
            solver=SolverAdapter3D(Solver3D(options.library,geometry))
            print('WORKER_STAGE=IMPORT_PYNQ',flush=True)
            from pynq import MMIO
            print('WORKER_STAGE=MMIO_SOLVER_ID',flush=True)
            client=Client3D(MMIO(base,size),solver,abort,options.measure_level)
            client.identify()  # 错身份不向设备写STOP；所有数值/几何检查先于MMIO。
            info=dict(worker_pid=os.getpid(),worker_cpu=options.worker_cpu,
                      worker_affinity=sorted(os.sched_getaffinity(0)),profile='TETRA40_3D',
                      geometry=solver.geometry,motion='DISABLED',measure_level=options.measure_level)
            shared.buffered_session(connection,abort,stop_new,client,options,info)
    except BaseException as exc:
        try:connection.send(('error',dict(error=type(exc).__name__+': '+str(exc))))
        except (EOFError,OSError):pass
    finally:connection.close()


def main(argv=None):
    parser=argument_parser();parser.description=__doc__
    parser.add_argument('--queue-capacity',type=int,default=64)
    parser.add_argument('--high-water',type=int,default=48)
    parser.add_argument('--flush-timeout',type=float,default=5.0)
    args=parser.parse_args(argv);geometry=prepare_args(args,parser)
    if not 1<=args.high_water<=args.queue_capacity-4 or args.queue_capacity>4096:
        parser.error('队列预留4条在途/双槽尾帧/结束记录，容量不超过4096')
    if not 0<args.flush_timeout<=60:parser.error('--flush-timeout须在0..60秒')
    validate_cpus(args.host_cpu,args.worker_cpu)
    base,size=address_from_hwh(args.hwh,args.ip)
    directory=create_ram_directory()
    try:handle=args.output.open('x',encoding='utf-8')
    except BaseException:
        directory.rmdir();raise
    print('RAM_RECOVERY_DIR=',directory,flush=True)
    context=mp.get_context('spawn');parent,child=context.Pipe()
    abort,stop_new=context.Event(),context.Event()
    worker=context.Process(target=worker_main,args=(child,abort,stop_new,args,base,size,geometry),
                           name='soundsight-3d-solver')
    # 显示不占用SD写入线程；完整方向与独立valid均保留在文件。
    queue=RamQueue(directory,args.queue_capacity,durable_sink_3d(handle,display=None))
    cleanup_error=None
    try:
        worker.start();child.close()
        with pinned(args.host_cpu):
            queue.start()
            info=dict(host_pid=os.getpid(),host_cpu=args.host_cpu,
                      host_affinity=sorted(os.sched_getaffinity(0)),profile='TETRA40_3D',motion='DISABLED')
            kind,result=shared.collect(parent,stop_new,queue,args.high_water,info)
    finally:
        original=sys.exc_info()[0];stop_new.set()
        try:
            if worker.pid is not None:finish_worker(worker,abort)
        except Exception as exc:
            cleanup_error=exc;print(str(exc),file=sys.stderr)
        finally:
            parent.close();child.close()
            if queue.writer.ident is not None:
                try:queue.finish(args.flush_timeout)
                finally:
                    if not queue.writer.is_alive():handle.close()
            else:handle.close()
        if cleanup_error is not None and original is None:raise cleanup_error
    print('CAPTURE_BUFFERED_3D_COMPLETE DURABLE_FRAMES=',queue.durable_frames,
          'QUEUE_PEAK=',queue.peak,'RESULT=',result,flush=True)
    if kind=='error' or result.get('host_stop_reason')=='storage_error':
        raise RuntimeError(result.get('error') or 'SD写入失败')
    return 0


if __name__=='__main__':raise SystemExit(main())
