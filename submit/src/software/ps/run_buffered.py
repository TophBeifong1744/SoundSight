'No-motion SMP capture. Accept records in RAM before consuming PL slots; batch writes to SD.'
import multiprocessing as mp
import os
import sys
import time

from ps_client import Client, Solver, FAULT, STATUS
from angle_filter import validate_window
from ram_queue import RamQueue, create_ram_directory, durable_batch_sink
from run_capture import address_from_hwh, argument_parser, prepare_args, single_owner
from run_smp import (HOST_TIMEOUT, POLL_INTERVAL,
                     SavedBeforeConsume, pinned, validate_cpus, finish_worker)

# 板端CPU1仅导入PYNQ已测4.589s，旧5s总启动等待余量不足。
# 只为进程/库初始化留20s；ready之后仍用原750ms，取帧/ACK/STOP仍为250ms。
START_TIMEOUT = 20.0


class QueuedBeforeConsume(SavedBeforeConsume):
    """复用有界IPC等待，但ACK明确标识queued，绝不声称已落盘。"""
    def __call__(self, record):
        self.ticket += 1
        self.connection.send(('record', self.ticket, record))
        deadline = time.monotonic() + self.timeout
        while not self.cancel.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('RAM acceptance ACK timed out; retain hardware locked frame')
            if self.connection.poll(min(POLL_INTERVAL, remaining)):
                if self.connection.recv() != ('queued', self.ticket):
                    raise RuntimeError('RAM acceptance ACK mismatch; retain hardware locked frame')
                if time.monotonic() >= deadline or self.cancel.is_set():
                    raise TimeoutError('RAM acceptance ACK expired or parent lost; retain hardware locked frame')
                return
        raise RuntimeError('Parent cancelled; retain hardware locked frame')


def buffered_session(connection, abort, stop_new, client, options, info):
    """CPU1为唯一MMIO所有者。高水位只停新增，不撤销当前记录的RAM确认。"""
    sink = QueuedBeforeConsume(connection, abort)
    stats = dict(consumed=0, drained=0, max_service_ns=0)
    failure = None
    reason = 'requested_frames'
    started = False
    try:
        if options.drain_existing and hasattr(client, 'stop_direction_output'):
            client.stop_direction_output()
        connection.send(('ready', info))
        sink(dict(event='startup', fault_before=client.read(FAULT),
                  requested_clear_faults=options.clear_faults,
                  retention='ram_before_consume',
                  window_frames=getattr(options, 'window_frames', 20),
                  min_valid=getattr(options, 'min_valid', 12),
                  online_angle_filter=getattr(options, 'angle_filter', False), **info))
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
        if hasattr(client, 'stop_direction_output'):
            client.stop_direction_output()
        client.disable()
        if (started or options.drain_existing) and not abort.is_set():
            while client.read(STATUS) & 3:
                if stats['drained'] >= 2:
                    raise RuntimeError('More than two tail frames after STOP; preserve hardware state')
                client.record_one(sink, allow_fault=True)
                stats['drained'] += 1
    except BaseException as exc:
        failure = (failure + '; ' if failure else '') + 'STOP/drain: ' + str(exc)
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
            print('WORKER_STAGE=IMPORT_PYNQ', flush=True)
            from pynq import MMIO
            print('WORKER_STAGE=MMIO_SOLVER_ID', flush=True)
            if getattr(options, 'measure_level', False) or getattr(options, 'min_level', None) is not None:
                from volume_gate import VolumeClient
                client = VolumeClient(MMIO(base, size), Solver(options.library), options.min_level,
                                      angle_filter=options.angle_filter,
                                      window_frames=options.window_frames, min_valid=options.min_valid)
            else:
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
                    if not ready:
                        raise TimeoutError('PYNQ startup timed out before ready; inspect WORKER_STAGE')
                    raise TimeoutError('Solver worker lost; request STOP and retain RAM files')
                continue
            message = connection.recv()
            deadline = time.monotonic() + HOST_TIMEOUT
            kind = message[0]
            if kind == 'ready':
                ready = True
                print('PYNQ_SMP_READY=', dict(host_info, **message[1]), flush=True)
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
                raise RuntimeError('Unknown process message')
        except KeyboardInterrupt:
            # 第一次Ctrl+C让所有者STOP并排尾，不能立即杀掉已接收记录。
            stop_reason = 'keyboard_interrupt'
            stop_new.set()
            print('STOP requested; draining and saving RAM records, please wait.', flush=True)


def main(argv=None):
    parser = argument_parser()
    parser.description = __doc__
    parser.add_argument('--host-cpu', type=int, default=0)
    parser.add_argument('--worker-cpu', type=int, default=1)
    parser.add_argument('--queue-capacity', type=int, default=64)
    parser.add_argument('--high-water', type=int, default=48)
    parser.add_argument('--flush-timeout', type=float, default=5.0)
    parser.add_argument('--sd-batch-size', type=int, default=8,
                        help='maximum records per SD sync (1..64; capped by high-water)')
    parser.add_argument('--sd-batch-wait-ms', type=float, default=50.0,
                        help='maximum batch collection wait, 0..100 ms')
    volume = parser.add_mutually_exclusive_group()
    volume.add_argument('--measure-level', action='store_true', help='Measure real level only, no direction output; requires PS volume bitstream')
    volume.add_argument('--min-level', type=int, help='Fixed level threshold in mean absolute DC-removed PCM counts; requires volume bitstream')
    parser.add_argument('--angle-filter', action='store_true',
                        help='Apply multi-frame filtering, circular mean and 3-deg deadband after level gate; no motion')
    parser.add_argument('--window-frames', type=int, default=20)
    parser.add_argument('--min-valid', type=int, default=12)
    args = parser.parse_args(argv)
    try:
        validate_window(args.window_frames, args.min_valid)
    except ValueError as exc:
        parser.error(str(exc))
    prepare_args(args, parser)
    if args.horizontal_motion:
        parser.error('RAM entry does not support motion; legacy motion uses run_smp.py durable confirmation')
    if args.min_level is not None and not 1 <= args.min_level <= 0xffffff:
        parser.error('--min-level must be an integer in 1..16777215; zero is not a calibrated threshold')
    if args.angle_filter and args.min_level is None:
        parser.error('--angle-filter requires --min-level; measure-only mode has no direction output')
    if not 1 <= args.high_water <= args.queue_capacity - 4 or args.queue_capacity > 4096:
        parser.error('Reserve at least 4 queue entries for in-flight/tail/end records; capacity must not exceed 4096')
    if not 0 < args.flush_timeout <= 60:
        parser.error('--flush-timeout must be greater than 0 and at most 60 seconds')
    if not 1 <= args.sd_batch_size <= 64 or not 0 <= args.sd_batch_wait_ms <= 100:
        parser.error('SD batch size must be 1..64; wait must be 0..100 ms')
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
    batch_size = min(args.sd_batch_size, args.high_water)
    queue = RamQueue(directory, args.queue_capacity, None,
                     batch_size=batch_size, batch_wait=args.sd_batch_wait_ms / 1000.0,
                     save_batch=durable_batch_sink(handle))
    print('STORAGE_DIAG=SD_BATCH_V1', 'BATCH_SIZE=', batch_size,
          'BATCH_WAIT_MS=', args.sd_batch_wait_ms, 'HIGH_WATER=', args.high_water, flush=True)
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
    print('STORAGE_STATS=', queue.storage, flush=True)
    if kind == 'error' or result.get('host_stop_reason') == 'storage_error':
        raise RuntimeError(result.get('error') or 'SD write failed')
    if result.get('host_stop_reason') == 'queue_high_water':
        print('CAPTURE_INCOMPLETE=queue_high_water', flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
