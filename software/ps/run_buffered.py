"""无动作双核采集：完整记录进入RAM后释放PL槽，CPU0独立写SD。

此入口显式采用断电可能丢RAM记录的策略。旧run_smp.py的逐帧耐久确认不变。
不加载bit，不复位；不修改ABI、C求解器、硬件采集周期或运动协议。
"""
import multiprocessing as mp
import os
import sys
import time

from ps_client import Client, Solver, FAULT, STATUS
from ram_queue import RamQueue, create_ram_directory
from run_capture import address_from_hwh, argument_parser, durable_sink, prepare_args, single_owner
from run_smp import (HOST_TIMEOUT, START_TIMEOUT, POLL_INTERVAL,
                     SavedBeforeConsume, pinned, validate_cpus, finish_worker)


class QueuedBeforeConsume(SavedBeforeConsume):
    """复用有界IPC等待，但ACK明确标识queued，绝不声称已落盘。"""
    def __call__(self, record):
        self.ticket += 1
        self.connection.send(('record', self.ticket, record))
        deadline = time.monotonic() + self.timeout
        while not self.cancel.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('RAM接收确认超时；保留硬件锁帧')
            if self.connection.poll(min(POLL_INTERVAL, remaining)):
                if self.connection.recv() != ('queued', self.ticket):
                    raise RuntimeError('RAM接收确认不匹配；保留硬件锁帧')
                if time.monotonic() >= deadline or self.cancel.is_set():
                    raise TimeoutError('RAM接收确认过期或父进程失联；保留硬件锁帧')
                return
        raise RuntimeError('父进程取消；保留硬件锁帧')


def buffered_session(connection, abort, stop_new, client, options, info):
    """CPU1为唯一MMIO所有者。高水位只停新增，不撤销当前记录的RAM确认。"""
    sink = QueuedBeforeConsume(connection, abort)
    stats = dict(consumed=0, drained=0, max_service_ns=0)
    failure = None
    reason = 'requested_frames'
    started = False
    try:
        connection.send(('ready', info))
        sink(dict(event='startup', fault_before=client.read(FAULT),
                  requested_clear_faults=options.clear_faults,
                  retention='ram_before_consume', **info))
        if not options.drain_existing and not stop_new.is_set():
            client.start(bist={'bist-reject': 0, 'bist-pass': 1, 'real': None}[options.mode],
                         clear_faults=options.clear_faults)
            started = True
            for _ in range(options.frames):
                if stop_new.is_set():
                    reason = 'host_stop'
                    break
                began = time.monotonic_ns()
                client.record_one(sink)
                stats['consumed'] += 1
                stats['max_service_ns'] = max(stats['max_service_ns'], time.monotonic_ns()-began)
            if stop_new.is_set():
                reason = 'host_stop'
        else:
            reason = 'drain_existing' if options.drain_existing else 'host_stop'
    except BaseException as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    # STOP并等待PL终结后，双槽最多还留两帧。预留容量用于这些尾帧。
    # 未成功启动（如历史故障/旧槽拒绝启动）时不擅自消费旧会话。
    try:
        client.disable()
        if (started or options.drain_existing) and not abort.is_set():
            while client.read(STATUS) & 3:
                if stats['drained'] >= 2:
                    raise RuntimeError('STOP后超过双槽上限；保留硬件现场')
                client.record_one(sink, allow_fault=True)
                stats['drained'] += 1
    except BaseException as exc:
        failure = (failure + '; ' if failure else '') + 'STOP/排尾: ' + str(exc)
    try:
        connection.send(('error' if failure else 'done',
                         dict(error=failure, stats=stats, stop_reason=reason,
                              requested_frames=options.frames)))
    except (EOFError, OSError):
        pass
    finally:
        connection.close()


def worker_main(connection, abort, stop_new, options, base, size):
    try:
        with pinned(options.worker_cpu), single_owner(options.lock_file):
            from pynq import MMIO
            client = Client(MMIO(base, size), Solver(options.library))
            client.identify()  # 不向身份错误的设备写STOP。
            info = dict(worker_pid=os.getpid(), worker_cpu=options.worker_cpu,
                        worker_affinity=sorted(os.sched_getaffinity(0)))
            buffered_session(connection, abort, stop_new, client, options, info)
    except BaseException as exc:
        try:
            connection.send(('error', dict(error=type(exc).__name__+': '+str(exc))))
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


def collect(connection, stop_new, queue, high_water, host_info):
    ready = False
    deadline = time.monotonic() + START_TIMEOUT
    stop_reason = None
    while True:
        try:
            if queue.error is not None and stop_reason is None:
                stop_reason = 'storage_error'
                stop_new.set()
            if not connection.poll(POLL_INTERVAL):
                if time.monotonic() >= deadline:
                    raise TimeoutError('算法进程失联；请求STOP，RAM文件保留')
                continue
            message = connection.recv()
            deadline = time.monotonic() + HOST_TIMEOUT
            kind = message[0]
            if kind == 'ready':
                ready = True
                print('PYNQ双核已启动：', dict(host_info, **message[1]), flush=True)
            elif kind == 'record' and ready:
                _, ticket, record = message
                # 唯一恢复键是本次队列目录+ticket；帧序号仍沿用硬件ABI。
                record = dict(record, ram_record=dict(session=queue.directory.name, ticket=ticket))
                queue.put(record)
                if queue.depth >= high_water and stop_reason is None:
                    stop_reason = 'queue_high_water'
                    stop_new.set()
                connection.send(('queued', ticket))
            elif kind in ('done', 'error'):
                result = dict(message[1], host_stop_reason=stop_reason, queue_peak=queue.peak)
                queue.put(dict(event='failed' if kind == 'error' else 'finished',
                               retention='ram_before_consume', **host_info, **result))
                return kind, result
            else:
                raise RuntimeError('未知进程消息')
        except KeyboardInterrupt:
            # 第一次Ctrl+C让所有者STOP并排尾，不能立即杀掉已接收记录。
            stop_reason = 'keyboard_interrupt'
            stop_new.set()
            print('已请求STOP；正在排尾和保存RAM记录，请等待。', flush=True)


def main(argv=None):
    parser = argument_parser()
    parser.description = __doc__
    parser.add_argument('--host-cpu', type=int, default=0)
    parser.add_argument('--worker-cpu', type=int, default=1)
    parser.add_argument('--queue-capacity', type=int, default=64)
    parser.add_argument('--high-water', type=int, default=48)
    parser.add_argument('--flush-timeout', type=float, default=5.0)
    args = parser.parse_args(argv)
    prepare_args(args, parser)
    if args.horizontal_motion:
        parser.error('RAM入口不支持动作；动作仍使用run_smp.py逐帧落盘确认')
    if not 1 <= args.high_water <= args.queue_capacity - 4 or args.queue_capacity > 4096:
        parser.error('队列至少预留4条（在途/双槽尾帧/结束记录），容量不超过4096')
    if not 0 < args.flush_timeout <= 60:
        parser.error('--flush-timeout须在0..60秒内')
    validate_cpus(args.host_cpu, args.worker_cpu)
    base, size = address_from_hwh(args.hwh, args.ip)
    directory = create_ram_directory()
    # 独占新文件，避免重跑混合不同会话；文件打不开时尚未启动硬件。
    try:
        handle = args.output.open('x', encoding='utf-8')
    except BaseException:
        directory.rmdir()
        raise
    print('RAM_RECOVERY_DIR=', directory, flush=True)
    context = mp.get_context('spawn')
    parent, child = context.Pipe()
    abort, stop_new = context.Event(), context.Event()
    worker = context.Process(target=worker_main,
                             args=(child, abort, stop_new, args, base, size),
                             name='soundsight-c-solver')
    queue = RamQueue(directory, args.queue_capacity, durable_sink(handle))
    cleanup_error = None
    try:
        worker.start()
        child.close()
        with pinned(args.host_cpu):
            # Linux新线程继承创建线程的affinity，写盘线程也在CPU0。
            queue.start()
            info = dict(host_pid=os.getpid(), host_cpu=args.host_cpu,
                        host_affinity=sorted(os.sched_getaffinity(0)))
            kind, result = collect(parent, stop_new, queue, args.high_water, info)
    finally:
        stop_new.set()
        try:
            if worker.pid is not None:
                finish_worker(worker, abort)
        except Exception as exc:
            cleanup_error = exc
            print(str(exc), file=sys.stderr)
        finally:
            parent.close()
            if queue.writer.ident is not None:
                try:
                    queue.finish(args.flush_timeout)
                finally:
                    # 不关闭正卡在fsync内的线程所持文件；RAM原件仍可恢复。
                    if not queue.writer.is_alive():
                        handle.close()
            else:
                handle.close()
    if cleanup_error is not None:
        raise cleanup_error
    print('DURABLE_FRAMES=', queue.durable_frames, 'QUEUE_PEAK=', queue.peak,
          'RESULT=', result, flush=True)
    if kind == 'error' or result.get('host_stop_reason') == 'storage_error':
        raise RuntimeError(result.get('error') or 'SD写入失败')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
