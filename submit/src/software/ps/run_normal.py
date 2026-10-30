'Continuous capture; horizontal motion requires explicit opt-in and calibration. Summary only after STOP.'
import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sys
import time

from ps_client import Solver, FAULT, STATUS, DROP, SEQ
from run_capture import address_from_hwh, single_owner
from run_smp import pinned, validate_cpus, HOST_TIMEOUT, POLL_INTERVAL
from volume_gate import VolumeClient
from angle_filter import validate_window

START_TIMEOUT = 20.0
DISPLAY_INTERVAL = .5
SNAPSHOT_BYTES = 16384


class Mailbox:
    """一个可覆盖快照，不是不断增长的帧队列。双方均不等待锁。

    CPU0轮询也更新存活时间。显示使用非阻塞写，串口堵塞不拖住CPU1；
    父进程死亡/失联超过原750ms预算，CPU1仍会STOP。
    """
    def __init__(self, context):
        self.data = context.Array('B', SNAPSHOT_BYTES, lock=False)
        self.size = context.Value('i', 0, lock=False)
        self.host_time = context.Value('d', 0, lock=False)
        self.lock = context.Lock()

    def publish(self, state):
        payload = json.dumps(state, ensure_ascii=True).encode('ascii')
        if len(payload) > SNAPSHOT_BYTES:
            raise RuntimeError('Status snapshot exceeds fixed capacity')
        if not self.lock.acquire(False):
            return None
        try:
            self.data[:len(payload)] = payload
            self.size.value = len(payload)
            return self.host_time.value
        finally:
            self.lock.release()

    def poll(self):
        if not self.lock.acquire(False):
            return None
        try:
            self.host_time.value = time.monotonic()
            raw = bytes(self.data[:self.size.value])
        finally:
            self.lock.release()
        return json.loads(raw) if raw else None


class RuntimeState:
    """保留固定种类的计数和最近一条记录，绝不积累原始帧列表。"""
    def __init__(self):
        self.began = time.monotonic()
        self.stats = dict(consumed=0, drained=0, raw_valid=0, accepted_windows=0,
                          target_updates=0, below_volume=0, sequence_gaps=0,
                          first_sequence=None, last_sequence=None, fault_or=0,
                          drops_first=None, drops_last=None, max_service_ns=0, motion_commits=0)
        self.reasons = {str(i): 0 for i in range(7)}
        self.reasons['other'] = 0
        self.latest = None
        self.window = None
        self.last_group = None
        self.last_clear = None
        self.last_record = None
        self.tail = False

    def accept(self, record):
        # Client在此返回后才做最后故障检查与CONSUME。正常模式的接管
        # 是完成计算/统计，有意放弃逐帧恢复能力；不能声称已持久保存。
        self.last_record = record
        frame, result = record['frame'], record['result']
        output = record['direction_output']
        details = record.get('angle_filter', {})
        now = time.monotonic()
        self.latest = dict(sequence=frame['sequence'],
                           level=record['volume']['level_counts'],
                           output=output, at=now,
                           window_count=details.get('frame_count', 0),
                           window_size=details.get('window_size', 20),
                           min_valid=details.get('min_valid', 12),
                           valid_count=details.get('valid_count', 0), motion=record.get('motion'))
        if self.tail:
            self.window = None
            return
        # 仅保存上一组和最近清窗各一个快照；不因半秒刷新错过单帧事件。
        if details.get('complete'):
            self.last_group = dict(sequence=frame['sequence'], at=now,
                                   reason=output['reason'], valid=bool(output['valid']),
                                   valid_count=details['valid_count'],
                                   inlier_count=details.get('inlier_count', 0),
                                   angle_deg=output.get('angle_deg'))
        if details.get('reset_reason'):
            self.last_clear = dict(sequence=frame['sequence'], at=now, reason=details['reset_reason'])
        s = self.stats
        s['motion_commits'] += int(record.get('motion', {}).get('committed', False))
        s['raw_valid'] += int(bool(result['direction_valid']))
        s['fault_or'] |= frame['fault']
        s['drops_last'] = frame['drops']
        if s['first_sequence'] is None:
            s['first_sequence'] = frame['sequence']
            s['drops_first'] = frame['drops']
        elif frame['sequence'] != s['last_sequence'] + 1:
            s['sequence_gaps'] += 1
        s['last_sequence'] = frame['sequence']
        key = str(result.get('reason'))
        self.reasons[key if key in self.reasons else 'other'] += 1
        s['below_volume'] += int(output['reason'] == 'below_volume_threshold')
        if output['valid']:
            s['accepted_windows'] += 1
            s['target_updates'] += int(output.get('updated', False))
            self.window = dict(angle_deg=output['angle_deg'], sequence=frame['sequence'], at=now)
        elif (output['reason'] != 'collecting_window'
              or record.get('angle_filter', {}).get('sequence_reset')):
            self.window = None

    def snapshot(self, phase='running'):
        return dict(phase=phase, at=time.monotonic(), stats=dict(self.stats),
                    elapsed_seconds=time.monotonic()-self.began,
                    solver_reasons=dict(self.reasons), latest=self.latest, window=self.window,
                    last_group=self.last_group, last_clear=self.last_clear)


def normal_session(connection, stop, mailbox, client, args, state_factory=RuntimeState, final_extra=None):
    """唯一MMIO所有者；正常完成排尾，异常保留未确认硬件槽供调试恢复。"""
    state = state_factory()
    started = False
    error = None
    reason = 'requested_frames'
    final_hw = None
    last_host = time.monotonic()
    last_publish = 0.0
    try:
        connection.send(('ready', dict(worker_pid=os.getpid())))
        before = client.read(FAULT)
        client.start(bist={'real': None, 'bist-pass': 1, 'bist-reject': 0}[args.mode],
                     clear_faults=args.clear_faults)
        started = True
        while not stop.is_set() and (args.frames == 0 or state.stats['consumed'] < args.frames):
            now = time.monotonic()
            if now - last_publish >= .05:
                host = mailbox.publish(state.snapshot())
                if host:
                    last_host = host
                last_publish = now
            if now - last_host > HOST_TIMEOUT:
                raise TimeoutError('Parent lost; STOP and retain unconsumed slots')
            began = time.monotonic_ns()
            client.record_one(state.accept)
            state.stats['consumed'] += 1
            state.stats['max_service_ns'] = max(state.stats['max_service_ns'], time.monotonic_ns()-began)
        if stop.is_set():
            reason = 'user_stop'
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        reason = 'error'
    finally:
        try:
            # An extension-register error must not suppress the independent
            # legacy STOP/SYS path (DA-SW-001). Preserve both failures if needed.
            cleanup_errors = []
            for cleanup in (client.stop_direction_output, client.disable):
                try:
                    cleanup()
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
            if cleanup_errors:
                raise RuntimeError('; '.join(cleanup_errors))
            # 故障时不丢弃锁定的失败帧；正常结束最多处理两个STOP尾帧。
            if started and error is None:
                state.tail = True
                while client.read(STATUS) & 3:
                    if state.stats['drained'] >= 2:
                        raise RuntimeError('More than two tail frames after STOP')
                    client.record_one(state.accept, allow_fault=True)
                    state.stats['drained'] += 1
            final_hw = dict(status=client.read(STATUS), fault=client.read(FAULT),
                            drops=client.read(DROP), locked_sequence=client.read(SEQ))
        except BaseException as exc:
            error = (error + '; ' if error else '') + 'STOP/drain: ' + str(exc)
        result = dict(state.snapshot('failed' if error else 'stopped'), error=error,
                      stop_reason=reason, fault_before=locals().get('before'),
                      hardware=final_hw, requested_frames=args.frames,
                      motion_requested=bool(getattr(args, 'motion_requested', getattr(args, 'horizontal_motion', False))), retention='statistics_only',
                      last_processed_record=state.last_record if error else None)
        mailbox.publish(result)
        # Optional bounded debug records travel only after STOP, never through
        # the fixed-size real-time mailbox or the acquisition service path.
        if final_extra is not None:
            result.update(final_extra())
        connection.send(('error' if error else 'done', result))
        connection.close()


def worker_main(connection, stop, mailbox, args, base, size):
    # Ctrl+C由父进程请求STOP，避免子进程正好在CONSUME附近被异步中断。
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        with pinned(args.worker_cpu), single_owner(args.lock_file):
            from pynq import MMIO
            if getattr(args, 'horizontal_motion', False):
                from horizontal_motion import HorizontalClient
                client = HorizontalClient(MMIO(base, size), Solver(args.library), args.min_level,
                                          args.calibration, args.manual_angle,
                                          args.window_frames, args.min_valid)
                client.stop_requested = stop.is_set
            else:
                client = VolumeClient(MMIO(base, size), Solver(args.library), args.min_level, angle_filter=True,
                                      window_frames=args.window_frames, min_valid=args.min_valid)
            client.identify()  # 失败时不向错误设备写STOP。
            normal_session(connection, stop, mailbox, client, args)
    except BaseException as exc:
        connection.send(('error', dict(error=type(exc).__name__+': '+str(exc),
                                       motion_requested=bool(getattr(args, 'horizontal_motion', False)))))
    finally:
        connection.close()


REASON_TEXT = dict(collecting_window='COLLECTING', below_volume_threshold='LOW_VOLUME',
                   insufficient_valid='INSUFFICIENT_VALID_ANGLES', insufficient_consensus='INSUFFICIENT_CONSENSUS',
                   undefined_mean='UNDEFINED_CIRCULAR_MEAN', bist_no_acoustic_output='BIST_NO_ACOUSTIC_OUTPUT',
                   fault_or_cancelled='FAULT_OR_CANCELLED', stopped_or_drain='STOPPED_OR_DRAIN',
                   solver_error='SOLVER_ERROR', level_unavailable='LEVEL_UNAVAILABLE',
                   sequence_gap='SEQUENCE_GAP', target_updated='ACCEPTED_UPDATED',
                   within_deadband='ACCEPTED_HELD_3DEG')


def progress_text(state, now):
    latest = state['latest']
    text = ' WINDOW=%s/%s VALID=%s MIN=%s' % (
        latest.get('window_count', 0), latest.get('window_size', 20),
        latest.get('valid_count', 0), latest.get('min_valid', 12))
    group = state.get('last_group')
    if group:
        text += '; LAST_GROUP=%s@%s VALID=%s KEEP=%s AGE=%.1fs' % (
            REASON_TEXT.get(group['reason'], group['reason']), group['sequence'],
            group['valid_count'], group['inlier_count'], max(0, now-group['at']))
        if group['valid']:
            text += ' TARGET=%.2fdeg(HISTORY)' % group['angle_deg']
    else:
        text += '; LAST_GROUP=NONE'
    cleared = state.get('last_clear')
    if cleared:
        text += '; LAST_CLEAR=%s@%s AGE=%.1fs' % (
            REASON_TEXT.get(cleared['reason'], cleared['reason']), cleared['sequence'],
            max(0, now-cleared['at']))
    else:
        text += '; LAST_CLEAR=NONE'
    return text


def display_line(state, now=None):
    now = time.monotonic() if now is None else now
    if not state or state.get('latest') is None:
        return 'NO_OUTPUT: STARTING_OR_WAITING_FOR_FIRST_FRAME\n'
    latest = state['latest']
    prefix = 'FRAME=%s LEVEL=%s ' % (latest['sequence'], latest['level'])
    motion = latest.get('motion')
    if state.get('phase') != 'running' or now - latest['at'] > HOST_TIMEOUT:
        return prefix + 'NO_OUTPUT: STOPPED_FAULT_OR_STALE_DATA' + progress_text(state, now) + '\n'
    if motion:
        prefix += 'SERVO=%s ' % ('TARGET_%sdeg' % motion['servo_deg'] if motion['committed'] else motion['reason'])
    out = latest['output']
    if out['valid']:
        return prefix + 'ANGLE=%.2f deg' % out['angle_deg'] + ('' if motion else ' SERVO=OFF') + progress_text(state, now) + '\n'
    message = prefix + 'NO_OUTPUT: ' + REASON_TEXT.get(out['reason'], out['reason'])
    window = state.get('window')
    if window and now - window['at'] <= HOST_TIMEOUT:
        message += '; LAST_VALID_WINDOW=%.2f deg AGE=%.2f s (HISTORY_ONLY)' % (window['angle_deg'], now-window['at'])
    return message + progress_text(state, now) + '\n'


class NonblockingConsole:
    """串口堵塞只跳过显示，不积累输出队列，也不等待终端腾空间。"""
    def __init__(self, fd):
        self.fd = fd
        self.previous = os.get_blocking(fd)
        os.set_blocking(fd, False)
        self.pending = b''
        self.skipped = 0

    def offer(self, line):
        if self.pending:
            self.skipped += 1
        else:
            self.pending = line.encode('utf-8')
        self.flush()

    def flush(self):
        if self.pending:
            try:
                written = os.write(self.fd, self.pending)
                self.pending = self.pending[written:]
            except BlockingIOError:
                pass
            except OSError:
                self.skipped += 1
                self.pending = b''

    def close(self):
        os.set_blocking(self.fd, self.previous)


def collect(connection, worker, stop, mailbox, console, formatter=display_line):
    ready = False
    began = time.monotonic()
    next_display = began
    state = None
    while True:
        try:
            current = mailbox.poll()
            if current is not None:
                state = current
            now = time.monotonic()
            console.flush()
            if now >= next_display:
                console.offer(formatter(state, now))
                next_display = now + DISPLAY_INTERVAL
            if connection.poll(POLL_INTERVAL):
                kind, result = connection.recv()
                if kind == 'ready':
                    ready = True
                    began = time.monotonic()
                elif kind in ('done', 'error'):
                    return kind, result
                else:
                    raise RuntimeError('Unknown worker message')
            if not worker.is_alive():
                if connection.poll(.1):
                    continue
                raise RuntimeError('Worker exited without reporting a result')
            reference = max(began, state['at']) if state else began
            if now - reference > (HOST_TIMEOUT if ready else START_TIMEOUT):
                raise TimeoutError('Worker lost; STOP requested, hardware stop not confirmed')
        except KeyboardInterrupt:
            stop.set()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hwh', type=Path, required=True)
    p.add_argument('--ip', default='ps_link')
    p.add_argument('--output', type=Path, required=True, help='Write summary JSON after stopping; no per-frame log')
    p.add_argument('--library', type=Path, default=Path(__file__).with_name('libss_solver.so'))
    p.add_argument('--mode', choices=['real', 'bist-pass', 'bist-reject'], default='real')
    p.add_argument('--frames', type=int, default=0, help='0 runs continuously until Ctrl+C; BIST requires 1')
    p.add_argument('--min-level', type=int, required=True, help='Experimental level threshold; previous B tests used 7000')
    p.add_argument('--window-frames', type=int, default=20)
    p.add_argument('--min-valid', type=int, default=12)
    p.add_argument('--clear-faults', type=lambda x: int(x, 0), default=0)
    p.add_argument('--host-cpu', type=int, default=0)
    p.add_argument('--worker-cpu', type=int, default=1)
    p.add_argument('--lock-file', default='/tmp/soundsight-ps-owner.lock')
    p.add_argument('--horizontal-motion', action='store_true', help='Explicitly enable horizontal motion; default OFF')
    p.add_argument('--motion-config', type=Path, help='PYNQ calibration JSON; required for motion')
    p.add_argument('--manual-angle', type=int, help='Deprecated; use soundsight.sh servo-angle')
    a = p.parse_args(argv)
    if a.manual_angle is not None:
        p.error('Manual calibration is separate: sudo sh soundsight.sh servo-angle DEG --seconds 5')
    try:
        validate_window(a.window_frames, a.min_valid)
    except ValueError as exc:
        p.error(str(exc))
    if a.frames < 0 or (a.mode != 'real' and a.frames != 1):
        p.error('Real mode requires frames>=0; BIST requires frames=1')
    if not 1 <= a.min_level <= 0xffffff or not 0 <= a.clear_faults <= 0xfff:
        p.error('Level must be in 1..16777215; clear mask must be in 0..0xfff')
    a.calibration = None
    if a.horizontal_motion:
        if a.mode != 'real' or not a.motion_config:
            p.error('Horizontal motion requires real mode and --motion-config')
        from horizontal_motion import load_calibration, check_hwh
        try:
            a.calibration = load_calibration(a.motion_config)
            check_hwh(a.hwh, a.ip)
            if a.manual_angle is not None and not a.calibration['min_deg'] <= a.manual_angle <= a.calibration['max_deg']:
                raise ValueError('Manual angle is outside configured mechanical limits')
        except (ValueError, OSError) as exc:
            p.error(str(exc))
    elif a.manual_angle is not None or a.motion_config is not None:
        p.error('Motion arguments require --horizontal-motion; default capture never moves servos')
    return a


def main(argv=None):
    args = parse_args(argv)
    validate_cpus(args.host_cpu, args.worker_cpu)
    base, size = address_from_hwh(args.hwh, args.ip)
    context = mp.get_context('spawn')
    parent, child = context.Pipe()
    stop = context.Event()
    mailbox = Mailbox(context)
    mailbox.poll()
    worker = context.Process(target=worker_main, args=(child, stop, mailbox, args, base, size))
    result = dict(error='Not started', motion_requested=args.horizontal_motion)
    console = None
    # 先独占创建汇总文件，路径错/已有同名文件时不碰硬件。
    with args.output.open('x', encoding='utf-8') as handle:
        try:
            console = NonblockingConsole(sys.stdout.fileno())
            worker.start()
            child.close()
            with pinned(args.host_cpu):
                kind, result = collect(parent, worker, stop, mailbox, console)
        except BaseException as exc:
            result = dict(error=type(exc).__name__+': '+str(exc),
                          last_snapshot=mailbox.poll(), motion_requested=args.horizontal_motion)
        finally:
            stop.set()
            if worker.pid is not None:
                worker.join(HOST_TIMEOUT)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(HOST_TIMEOUT)
                    result['cleanup_error'] = 'Worker terminated; hardware STOP not confirmed'
            parent.close()
            child.close()
            if console:
                result['console_skipped'] = console.skipped
                console.close()
            result['settings'] = dict(min_level=args.min_level, frames=args.frames, mode=args.mode,
                                      display_seconds=DISPLAY_INTERVAL, angle_filter=True,
                                      window_frames=args.window_frames, min_valid=args.min_valid,
                                      horizontal_motion=args.horizontal_motion, calibration=args.calibration,
                                      manual_angle=args.manual_angle)
            # 此时已经退出采集；SD慢或写盘失败不会拖住正常运行中的槽释放。
            handle.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
            handle.flush()
            os.fsync(handle.fileno())
    print('NORMAL_STOPPED SUMMARY=', args.output, 'ERROR=', result.get('error'), flush=True)
    return 1 if result.get('error') or result.get('cleanup_error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
