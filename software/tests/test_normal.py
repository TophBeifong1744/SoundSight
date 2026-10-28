"""正常模式离线验证：真实Client与音量筛选，假寄存器；不访问PYNQ硬件。"""
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ps'))
import ps_client as hw
import run_normal as app
from volume_gate import VolumeClient


class Device:
    """独立模型：每次CONSUME推进帧，STOP留一个尾帧；禁止任何动作提交。"""
    def __init__(self, fail=False, low=False):
        self.sequence = 1
        self.active = False
        self.queued = False
        self.locked = False
        self.fault = 0
        self.pair = 0
        self.consumed = 0
        self.fail = fail
        self.low = low
        self.stopped = False

    def read(self, a):
        if a == hw.MAGIC: return 0x5a5a2026
        if a == hw.ABI: return 0x10001
        if a == hw.STATUS: return (1 << 17) | 32 | int(self.locked) | (2 if self.queued else 0)
        if a == hw.SEQ: return self.sequence if self.locked else 0
        if a == hw.FEATURE: return self.pair << 8
        if a == hw.ENERGY: return 100 if self.low else 10000
        if a == hw.FAULT: return self.fault
        if a == hw.SYS: return 9 if self.active else 8
        return 0

    def write(self, a, value):
        if a == hw.SELECT: self.pair = value
        elif a == hw.FAULT: self.fault &= ~value
        elif a == hw.SYS and value & 1:
            self.active = self.queued = True
        elif a == hw.ACT:
            assert value == 2, 'normal mode must never ARM or COMMIT'
            self.active = False
            self.fault |= 64
            self.stopped = True
        elif a == hw.SNAP and value == 1: self.locked = True
        elif a == hw.SNAP and value == 4:
            assert self.locked
            self.consumed += 1
            self.sequence += 1
            self.locked = False
            self.queued = self.active


class Solver:
    def __init__(self, fail=False): self.fail = fail
    def solve(self, frame, config=None):
        if self.fail: raise ValueError('injected C failure')
        return dict(api_status=0, bridge_status=0, direction_valid=1, reason=0,
                    angle_q8=179*256, servo_cmd_valid=0)


class Connection:
    def __init__(self): self.messages = []
    def send(self, message): self.messages.append(message)
    def close(self): pass


def options(frames=45):
    return SimpleNamespace(frames=frames, mode='real', clear_faults=0)


def fake_worker(connection, stop, mailbox, frames):
    device = Device()
    client = VolumeClient(device, Solver(), 7000, angle_filter=True)
    app.normal_session(connection, stop, mailbox, client, options(frames))


class Console:
    def __init__(self): self.lines = []
    def offer(self, line): self.lines.append(line)
    def flush(self): pass


class NormalTests(unittest.TestCase):
    def setUp(self):
        self.ctx = mp.get_context('spawn')
        self.mailbox = app.Mailbox(self.ctx)
        self.mailbox.poll()

    def session(self, frames=45, fail=False, low=False, stop=None, mailbox=None):
        device = Device(low=low)
        client = VolumeClient(device, Solver(fail), 7000, angle_filter=True)
        connection = Connection()
        # 运行期间禁止任何写盘同步；既有Client执行真实读/算/检查/CONSUME。
        with patch('os.fsync', side_effect=AssertionError('runtime disk sync')):
            app.normal_session(connection, stop or self.ctx.Event(), mailbox or self.mailbox,
                               client, options(frames))
        return device, connection.messages[-1]

    def test_compute_consume_stop_tail_and_no_motion(self):
        device, (kind, result) = self.session()
        self.assertEqual(kind, 'done')
        self.assertEqual(result['stats']['consumed'], 45)
        self.assertEqual(result['stats']['drained'], 1)
        self.assertEqual(device.consumed, 46)
        self.assertEqual(result['stats']['accepted_windows'], 2)
        self.assertEqual(result['stats']['target_updates'], 1)
        self.assertEqual(result['hardware']['fault'], 64)
        self.assertFalse(result['motion_requested'])
        self.assertIsNone(result['last_processed_record'])

    def test_failure_stops_without_consuming_locked_frame(self):
        device, (kind, result) = self.session(fail=True)
        self.assertEqual(kind, 'error')
        self.assertIn('injected C failure', result['error'])
        self.assertEqual(device.consumed, 0)
        self.assertTrue(device.locked and device.stopped)

    def test_quiet_still_consumes_without_output(self):
        _, (_, result) = self.session(low=True)
        self.assertEqual(result['stats']['below_volume'], 45)
        self.assertEqual(result['stats']['accepted_windows'], 0)
        self.assertEqual(result['stats']['consumed'], 45)

    def test_stats_applied_before_consume_and_release_failure_retains_record(self):
        device = Device()
        client = VolumeClient(device, Solver(), 7000, angle_filter=True)
        state = app.RuntimeState()
        client.start()
        original = device.write
        def write(address, value):
            if address == hw.SNAP and value == 4:
                self.assertEqual(state.last_record['frame']['sequence'], 1)
                self.assertEqual(state.stats['raw_valid'], 1)
                raise OSError('injected consume failure')
            return original(address, value)
        device.write = write
        with self.assertRaisesRegex(OSError, 'consume failure'):
            client.record_one(state.accept)
        self.assertTrue(device.stopped and device.locked)
        self.assertEqual(state.last_record['frame']['sequence'], 1)

    def test_state_memory_does_not_grow_with_frame_count(self):
        state = app.RuntimeState()
        record = dict(frame=dict(sequence=1, fault=0, drops=0),
                      result=dict(direction_valid=1, reason=0),
                      volume=dict(level_counts=10000),
                      direction_output=dict(valid=False, reason='collecting_window'))
        tracemalloc.start()
        try:
            for i in range(1000):
                record['frame']['sequence'] = i+1; state.accept(record)
            before = tracemalloc.get_traced_memory()[0]
            for i in range(1000, 30000):
                record['frame']['sequence'] = i+1; state.accept(record)
            after = tracemalloc.get_traced_memory()[0]
            self.assertLess(after-before, 20000)
            self.assertEqual(state.stats['raw_valid'], 30000)
            self.assertEqual(len(state.reasons), 8)
        finally:
            tracemalloc.stop()

    def test_low_volume_and_bad_window_clear_last_display_target(self):
        state = app.RuntimeState()
        record = dict(frame=dict(sequence=1, fault=0, drops=0),
                      result=dict(direction_valid=1, reason=0), volume=dict(level_counts=10000),
                      direction_output=dict(valid=True, reason='target_updated', angle_deg=12, updated=True))
        state.accept(record)
        self.assertEqual(state.window['angle_deg'], 12)
        for reason in ('below_volume_threshold', 'insufficient_consensus'):
            state.window = dict(angle_deg=12)
            record['direction_output'] = dict(valid=False, reason=reason)
            state.accept(record)
            self.assertIsNone(state.window)

    def test_display_scheduler_half_second_even_without_frames(self):
        clock = [0.0]
        calls = []
        class TimedConnection:
            def poll(self, timeout):
                clock[0] += .125
                return clock[0] >= 1.5
            def recv(self): return 'done', {}
        class Alive:
            def is_alive(self): return True
        class EmptyMailbox:
            def poll(self): return None
        class TimedConsole:
            def flush(self): pass
            def offer(self, text): calls.append((clock[0], text))
        with patch.object(app.time, 'monotonic', side_effect=lambda: clock[0]):
            app.collect(TimedConnection(), Alive(), self.ctx.Event(), EmptyMailbox(), TimedConsole())
        self.assertEqual([x[0] for x in calls], [0, .5, 1.0])
        self.assertTrue(all('NO_OUTPUT' in x[1] for x in calls))

    def test_continuous_mode_stops_on_event(self):
        stop = self.ctx.Event()
        outer = self.mailbox
        class StopAfterPublish:
            def publish(self, state):
                stop.set()
                return outer.publish(state)
        _, (_, result) = self.session(frames=0, stop=stop, mailbox=StopAfterPublish())
        self.assertEqual(result['stop_reason'], 'user_stop')
        self.assertLessEqual(result['stats']['consumed'], 1)

    def test_host_loss_stops(self):
        class Lost:
            def publish(self, state): return time.monotonic()-2
        device, (kind, result) = self.session(mailbox=Lost())
        self.assertEqual(kind, 'error')
        self.assertIn('Parent lost', result['error'])
        self.assertTrue(device.stopped)
        self.assertEqual(device.consumed, 0)

    def test_mailbox_overwrites_and_lock_does_not_block(self):
        for i in range(10000): self.mailbox.publish({'frame': i})
        self.assertEqual(self.mailbox.poll()['frame'], 9999)
        self.assertEqual(len(self.mailbox.data), app.SNAPSHOT_BYTES)
        with self.mailbox.lock:
            self.assertIsNone(self.mailbox.publish({'frame': -1}))
            self.assertIsNone(self.mailbox.poll())

    def test_spawn_actual_shared_memory_and_collect(self):
        parent, child = self.ctx.Pipe()
        stop = self.ctx.Event()
        worker = self.ctx.Process(target=fake_worker, args=(child, stop, self.mailbox, 3000))
        worker.start(); child.close()
        try:
            kind, result = app.collect(parent, worker, stop, self.mailbox, Console())
            self.assertEqual(kind, 'done', result)
            self.assertEqual(result['stats']['consumed'], 3000)
            self.assertEqual(result['stats']['sequence_gaps'], 0)
            self.assertEqual(result['stats']['accepted_windows'], 150)
        finally:
            stop.set(); worker.join(3); parent.close()
            if worker.is_alive(): worker.terminate(); worker.join()
        self.assertEqual(worker.exitcode, 0)

    def test_display_invalid_is_not_zero_or_stale_angle(self):
        now = time.monotonic()
        s = dict(phase='running', latest=dict(sequence=1, level=100, at=now,
                 output=dict(valid=False, reason='below_volume_threshold')), window=None)
        line = app.display_line(s, now)
        self.assertIn('NO_OUTPUT', line)
        self.assertIn('LOW_VOLUME', line)
        self.assertNotIn('ANGLE=', line)
        s['latest']['output'] = dict(valid=True, angle_deg=179.0)
        self.assertIn('179.00', app.display_line(s, now))
        self.assertNotIn('179.00', app.display_line(s, now+1))

    def test_collecting_reports_last_window_as_history_only(self):
        now = time.monotonic()
        s = dict(phase='running', latest=dict(sequence=22, level=10000, at=now,
                 output=dict(valid=False, reason='collecting_window')),
                 window=dict(angle_deg=-179, at=now-.1))
        line = app.display_line(s, now)
        self.assertIn('NO_OUTPUT', line)
        self.assertIn('HISTORY_ONLY', line)
        self.assertIn('-179.00', line)

    def test_blocked_console_keeps_one_line_and_never_waits(self):
        with patch('os.get_blocking', return_value=True), patch('os.set_blocking'), \
                patch('os.write', side_effect=BlockingIOError):
            c = app.NonblockingConsole(1)
            for _ in range(10000): c.offer('NO_OUTPUT\n')
            self.assertEqual(c.pending, 'NO_OUTPUT\n'.encode())
            self.assertEqual(c.skipped, 9999)
            c.close()

    def test_partial_console_write_preserves_line(self):
        with patch('os.get_blocking', return_value=True), patch('os.set_blocking'), \
                patch('os.write', side_effect=[2, 2]) as write:
            c = app.NonblockingConsole(1); c.offer('abc\n'); c.flush()
            self.assertEqual(write.call_args_list[1].args[1], b'c\n')
            self.assertEqual(c.pending, b'')

    def test_cli_continuous_and_bounded(self):
        args = ['--hwh', 'x.hwh', '--output', 'x.json', '--min-level', '7000']
        self.assertEqual(app.parse_args(args).frames, 0)
        self.assertEqual(app.parse_args(args+['--frames', '3000']).frames, 3000)
        with self.assertRaises(SystemExit): app.parse_args(args+['--mode', 'bist-pass'])
        with self.assertRaises(SystemExit): app.parse_args(args+['--horizontal-motion'])

    def test_modes_dispatch_preserves_debug_arguments(self):
        import run_device
        with patch('run_buffered.main', return_value=2) as debug:
            self.assertEqual(run_device.main(['--operation', 'debug', '--frames', '100']), 2)
            debug.assert_called_once_with(['--frames', '100'])
        with patch('run_normal.main', return_value=0) as normal:
            run_device.main(['--operation', 'normal', '--frames', '0'])
            normal.assert_called_once_with(['--frames', '0'])


if __name__ == '__main__':
    unittest.main()
