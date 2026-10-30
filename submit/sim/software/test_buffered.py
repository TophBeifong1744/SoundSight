"""RAM接收/写盘/STOP自测：真实spawn与线程，注入慢盘/满盘。不是板测或RTL仿真。"""
import json
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'software/ps'))
sys.path.insert(0, str(Path(__file__).parent))
import ps_client as hw
import run_buffered as app
from ram_queue import RamQueue, MAX_RECORD_BYTES, create_ram_directory, durable_batch_sink
from run_capture import durable_sink
from recover_ram import recover
from test_smp import Device, Solver


def read_ram_evidence(path):
    """测试观察者不阻止writer删除已保存文件；匹配Linux的打开后unlink语义。"""
    if sys.platform != 'win32':
        return path.read_text(encoding='utf-8')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    import os
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close(handle)
        raise
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        return stream.read()


class BufferedDevice(Device):
    """独立硬件槽模型：STOP时尾帧仍可读；CONSUME前必须找到完整RAM/SD记录。"""
    def __init__(self, output, ram):
        super().__init__(output)
        self.ram = Path(ram)
        self.sequence = 1
        self.started = False
        self.tail = 0

    def read(self, address):
        if address == hw.SEQ:
            return self.sequence if self.locked else 0
        return super().read(address)

    def write(self, address, value):
        if address == hw.SYS and value & 1:
            self.started = True
        if address == hw.ACT and value == 2 and self.started:
            self.tail = 2
            self.started = False
            self.queued = True
        if address == hw.SNAP and value == 4:
            # 期望来自持久的RAM文件或已写SD文件，不依赖queue内部成员。
            records = []
            for path in list(self.ram.glob('*.jsonl')) + [self.output]:
                try:
                    records.extend(json.loads(line) for line in read_ram_evidence(path).splitlines())
                except FileNotFoundError:
                    pass  # writer刚完成迁移；再次读取SD即可。
            if self.output.exists():
                records.extend(json.loads(line) for line in self.output.read_text(encoding='utf-8').splitlines())
            assert any(r.get('frame', {}).get('sequence') == self.sequence and 'result' in r for r in records)
            with self.output.with_suffix('.consumed').open('a') as f:
                f.write(str(self.sequence)+'\n')
            self.sequence += 1
            self.locked = False
            if self.tail:
                self.tail -= 1
                self.queued = self.tail > 0
            else:
                self.queued = True
            return
        super().write(address, value)


class BufferedVolumeDevice(BufferedDevice):
    def read(self, address):
        if address == hw.ABI: return 0x10001
        if address == hw.ENERGY: return 1000
        value = super().read(address)
        return value | (1 << 17) | (1 << 5) if address == hw.STATUS else value


class AngleSolver(Solver):
    def solve(self, frame, config=None):
        return dict(super().solve(frame,config), api_status=0, angle_q8=-13*256)


def fake_worker(connection, abort, stop, output, directory, frames, failure=None, angle=False):
    if angle:
        from volume_gate import VolumeClient
        client = VolumeClient(BufferedVolumeDevice(output,directory),AngleSolver(failure),1000,angle_filter=True)
    else:
        client = hw.Client(BufferedDevice(output, directory), Solver(failure))
    options = SimpleNamespace(mode='real', frames=frames, drain_existing=False, clear_faults=0, angle_filter=angle)
    app.buffered_session(connection, abort, stop, client, options, {'backend': 'fake-mmio'})


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ram = self.root/'ram'
        self.ram.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_acceptance_is_complete_and_copy_is_immutable(self):
        q = RamQueue(self.ram, 2, lambda r: None)
        record = {'frame': {'sequence': 42, 'words': [1, 2]}}
        q.put(record)
        record['frame']['words'][0] = 99
        self.assertEqual(json.loads(next(self.ram.glob('*.jsonl')).read_text())['frame']['words'], [1, 2])
        q.put({'event': 'second'})
        with self.assertRaisesRegex(RuntimeError, 'full'):
            q.put({'event': 'third'})
        self.assertEqual(q.depth, 2)

    def test_inflight_writer_occupies_capacity_and_timeout_preserves(self):
        release = threading.Event()
        entered = threading.Event()
        def slow(record):
            entered.set()
            release.wait(3)
        q = RamQueue(self.ram, 1, slow)
        q.start()
        try:
            q.put({'frame': {'sequence': 1}})
            self.assertTrue(entered.wait(1))
            self.assertEqual(q.depth, 1)
            with self.assertRaises(RuntimeError):
                q.finish(.01)
            self.assertEqual(len(list(self.ram.glob('*.jsonl'))), 1)
        finally:
            release.set()
            q.writer.join(1)
        q.finish(1)

    def test_disk_failure_preserves_failed_head_and_following_records(self):
        def fail(record):
            raise OSError('injected SD full')
        q = RamQueue(self.ram, 4, fail)
        q.put({'frame': {'sequence': 1}})
        q.put({'frame': {'sequence': 2}})
        q.start()
        with self.assertRaisesRegex(RuntimeError, 'SD full'):
            q.finish(1)
        self.assertEqual(q.durable, 0)
        self.assertEqual(len(list(self.ram.glob('*.jsonl'))), 2)

    def test_ram_write_error_cannot_confirm_acceptance(self):
        q = RamQueue(self.ram, 4, lambda r: None)
        with patch.object(Path, 'open', side_effect=OSError('tmpfs full')):
            with self.assertRaises(OSError):
                q.put({'frame': {'sequence': 1}})
        self.assertEqual(q.accepted, 0)
        self.assertEqual(q.depth, 0)

    def test_record_size_bound(self):
        q = RamQueue(self.ram, 4, lambda r: None)
        with self.assertRaises(ValueError):
            q.put({'oversize': 'x'*MAX_RECORD_BYTES})
        self.assertEqual(q.accepted, 0)

    def test_disk_temp_rejected_before_hardware(self):
        with patch.object(Path, 'read_text', return_value='/dev/mmcblk0p2 /dev/shm ext4 rw 0 0\n'):
            with self.assertRaisesRegex(RuntimeError, 'tmpfs'):
                create_ram_directory()

    def test_fifo_and_durable_counts(self):
        seen = []
        q = RamQueue(self.ram, 8, seen.append)
        for i in range(5):
            q.put({'frame': {'sequence': i}})
        q.start()
        q.finish(1)
        self.assertEqual([r['frame']['sequence'] for r in seen], list(range(5)))
        self.assertEqual(q.durable_frames, 5)
        self.assertFalse(self.ram.exists())

    def test_recovery_copies_without_deleting_or_overwriting(self):
        q = RamQueue(self.ram, 4, lambda r: None)
        q.put({'frame': {'sequence': 1}, 'ram_record': {'session': 'test', 'ticket': 1}})
        q.put({'frame': {'sequence': 2}, 'ram_record': {'session': 'test', 'ticket': 2}})
        output = self.root/'recovered.jsonl'
        self.assertEqual(recover(self.ram, output), 2)
        self.assertEqual(len(list(self.ram.glob('*.jsonl'))), 2)
        with self.assertRaises(FileExistsError):
            recover(self.ram, output)


class SpawnTests(unittest.TestCase):
    setUp = QueueTests.setUp
    tearDown = QueueTests.tearDown
    def run_session(self, frames=20, high=48, capacity=64, delay=.0, failure=None, disk_error=False, angle=False, batch=False):
        context = mp.get_context('spawn')
        parent, child = context.Pipe()
        abort, stop = context.Event(), context.Event()
        output = self.root/'frames.jsonl'
        handle = output.open('x', encoding='utf-8')
        save = durable_batch_sink(handle) if batch else durable_sink(handle)
        def slow_save(record):
            time.sleep(delay)
            if disk_error:
                raise OSError('injected SD full')
            save(record)
        q = (RamQueue(self.ram, capacity, None, batch_size=min(8, high), batch_wait=.05,
                      save_batch=slow_save) if batch else RamQueue(self.ram, capacity, slow_save))
        worker = context.Process(target=fake_worker,
                                 args=(child, abort, stop, output, self.ram, frames, failure, angle))
        worker.start()
        child.close()
        q.start()
        try:
            kind, result = app.collect(parent, stop, q, high, {'backend': 'fake-host'})
            worker.join(2)
            self.assertFalse(worker.is_alive())
            if disk_error:
                with self.assertRaises(RuntimeError):
                    q.finish(2)
            else:
                q.finish(5)
            return kind, result, q, output
        finally:
            abort.set()
            parent.close()
            worker.join(1)
            if worker.is_alive():
                worker.terminate()
                worker.join(1)
            q.writer.join(5)
            handle.close()

    def test_slow_sd_does_not_delay_consume_until_fsync(self):
        kind, result, q, output = self.run_session(frames=12, delay=.035)
        self.assertEqual(kind, 'done', result)
        self.assertEqual(result['stats']['consumed'], 12)
        self.assertEqual(result['stats']['drained'], 2)
        self.assertEqual(q.durable_frames, 14)
        self.assertGreater(q.peak, 1)
        self.assertEqual(len(output.with_suffix('.consumed').read_text().splitlines()), 14)

    def test_batched_online_filter_complete_and_no_motion(self):
        kind, result, q, output = self.run_session(frames=40, delay=.01, angle=True, batch=True)
        self.assertEqual(kind, 'done', result)
        self.assertIsNone(result['host_stop_reason'])
        self.assertEqual(result['stats']['consumed'], 40)
        self.assertEqual(q.durable_frames, 42)
        self.assertLess(q.storage['batches'], q.durable)
        rows = [json.loads(s) for s in output.read_text(encoding='utf-8').splitlines()]
        frames = [r for r in rows if 'frame' in r]
        self.assertEqual([r['frame']['sequence'] for r in frames], list(range(1, 43)))
        self.assertEqual([r['frame']['sequence'] for r in frames if r['direction_output']['valid']], [20, 40])
        self.assertFalse(output.with_suffix('.commanded').exists())

    def test_batched_slow_disk_still_stops_at_high_water(self):
        kind, result, q, output = self.run_session(frames=100, high=3, capacity=7, delay=.2, batch=True)
        self.assertEqual(kind, 'done', result)
        self.assertEqual(result['host_stop_reason'], 'queue_high_water')
        self.assertEqual(result['stats']['drained'], 2)
        self.assertLess(result['stats']['consumed'], 100)
        self.assertEqual(q.durable_frames, result['stats']['consumed'] + 2)
        self.assertLessEqual(q.peak, 7)

    def test_batched_disk_error_keeps_ram_and_stops(self):
        kind, result, q, output = self.run_session(frames=100, high=8, capacity=12, disk_error=True, batch=True)
        self.assertIn(result['host_stop_reason'], ('storage_error', 'queue_high_water'))
        self.assertTrue(output.with_suffix('.stopped').exists())
        self.assertEqual(q.durable, 0)
        self.assertEqual(len(list(self.ram.glob('*.jsonl'))), q.depth)

    def test_high_water_stops_and_preserves_two_tail_frames(self):
        kind, result, q, output = self.run_session(frames=100, high=3, capacity=7, delay=.03)
        self.assertEqual(kind, 'done', result)
        self.assertEqual(result['host_stop_reason'], 'queue_high_water')
        self.assertLess(result['stats']['consumed'], 100)
        self.assertEqual(result['stats']['drained'], 2)
        self.assertLessEqual(q.peak, 7)
        records = [json.loads(s) for s in output.read_text(encoding='utf-8').splitlines()]
        seq = [r['frame']['sequence'] for r in records if 'frame' in r]
        self.assertEqual(seq, list(range(1, len(seq)+1)))

    def test_online_filter_in_real_spawn_queue_with_slow_writer(self):
        kind,result,q,output=self.run_session(frames=40,delay=.01,angle=True)
        self.assertEqual(kind,'done',result)
        self.assertEqual(result['stats'],dict(consumed=40,drained=2,max_service_ns=result['stats']['max_service_ns']))
        rows=[json.loads(s) for s in output.read_text(encoding='utf-8').splitlines()]
        frames=[r for r in rows if 'frame' in r]
        self.assertEqual(len(frames),42)
        self.assertEqual([r['frame']['sequence'] for r in frames if r['direction_output']['valid']],[20,40])
        self.assertTrue(frames[19]['direction_output']['updated'])
        self.assertFalse(frames[39]['direction_output']['updated'])
        self.assertTrue(all(r['direction_output']['reason']=='stopped_or_drain' for r in frames[-2:]))
        self.assertFalse(output.with_suffix('.commanded').exists())

    def test_online_filter_high_water_keeps_records_without_target(self):
        kind,result,q,output=self.run_session(frames=100,high=3,capacity=7,delay=.03,angle=True)
        self.assertEqual(kind,'done')
        self.assertEqual(result['host_stop_reason'],'queue_high_water')
        rows=[json.loads(s) for s in output.read_text(encoding='utf-8').splitlines()]
        frames=[r for r in rows if 'frame' in r]
        self.assertFalse(any(r['direction_output']['valid'] for r in frames))
        self.assertEqual(len(frames),result['stats']['consumed']+2)
        self.assertEqual(q.durable_frames,len(frames))
        self.assertFalse(output.with_suffix('.commanded').exists())

    def test_write_failure_stops_and_retains_ram_tail(self):
        kind, result, q, output = self.run_session(frames=100, high=3, capacity=7, disk_error=True)
        self.assertIn(result['host_stop_reason'], ('storage_error', 'queue_high_water'))
        self.assertLess(result['stats']['consumed'], 100)
        self.assertGreater(q.depth, 0)
        self.assertTrue(output.with_suffix('.stopped').exists())
        self.assertEqual(len(list(self.ram.glob('*.jsonl'))), q.depth)

    def test_solver_failure_is_not_success_or_consumed(self):
        kind, result, q, output = self.run_session(failure='exception')
        self.assertEqual(kind, 'error')
        self.assertIn('solver injected failure', result['error'])
        self.assertEqual(result['stats']['consumed'], 0)
        self.assertFalse(output.with_suffix('.consumed').exists())

    def test_wrong_ack_retains_hardware_frame(self):
        context = mp.get_context('spawn')
        parent, child = context.Pipe()
        abort, stop = context.Event(), context.Event()
        output = self.root/'frames.jsonl'
        output.touch()
        worker = context.Process(target=fake_worker,
                                 args=(child, abort, stop, output, self.ram, 1))
        worker.start()
        child.close()
        try:
            self.assertTrue(parent.poll(5))
            self.assertEqual(parent.recv()[0], 'ready')
            self.assertTrue(parent.poll(1))
            record = parent.recv()
            parent.send(('saved', record[1]))  # 旧协议不能冒充RAM确认。
            self.assertTrue(parent.poll(1))
            self.assertEqual(parent.recv()[0], 'error')
            worker.join(1)
            self.assertFalse(output.with_suffix('.consumed').exists())
        finally:
            parent.close()
            worker.join(1)
            if worker.is_alive():
                worker.terminate()
                worker.join(1)

    def test_ctrl_c_requests_graceful_stop_and_keeps_processing(self):
        stop = threading.Event()
        class Connection:
            calls = 0
            def poll(self, timeout):
                self.calls += 1
                if self.calls == 1:
                    raise KeyboardInterrupt()
                return True
            def recv(self):
                return ('done', {'stats': {'consumed': 0, 'drained': 0}})
        q = RamQueue(self.ram, 8, lambda r: None)
        kind, result = app.collect(Connection(), stop, q, 4, {})
        self.assertTrue(stop.is_set())
        self.assertEqual(result['host_stop_reason'], 'keyboard_interrupt')
        self.assertEqual(kind, 'done', result)

    def test_ack_timeout_does_not_accept_record(self):
        class Connection:
            def send(self, message): pass
            def poll(self, timeout):
                time.sleep(timeout)
                return False
        sink = app.QueuedBeforeConsume(Connection(), threading.Event(), timeout=.01)
        with self.assertRaises(TimeoutError):
            sink({'frame': {'sequence': 1}})

    def test_motion_and_insufficient_reserve_rejected_before_mmio(self):
        args = ['--hwh', 'missing.hwh', '--output', 'unused.jsonl', '--mode', 'real']
        with self.assertRaises(SystemExit):
            app.main(args + ['--queue-capacity', '4'])
        with self.assertRaises(SystemExit):
            config = self.root/'config.json'
            config.write_text('[0,1,-100,100,0,180,180]')
            app.main(args + ['--horizontal-motion', '--servo-config', str(config), '--watchdog-ticks', '1000'])

    def startup_connection(self, ready_at, done_after=None):
        # 模拟时钟让测试不真等20秒；时间点来自独立启动/运行要求。
        class Connection:
            now = 0.0
            sent_ready = False
            def poll(self, timeout):
                self.now += timeout
                if self.now < ready_at:
                    return False
                return not self.sent_ready or (done_after is not None and self.now >= ready_at+done_after)
            def recv(self):
                if not self.sent_ready:
                    self.sent_ready = True
                    return ('ready', {'backend': 'startup-clock-fixture'})
                return ('done', {'stats': {'consumed': 0, 'drained': 0}})
        return Connection()

    def test_six_second_startup_fails_old_budget_but_passes_new(self):
        q = RamQueue(self.ram, 8, lambda r: None)
        old = self.startup_connection(6.0, .01)
        with patch.object(app, 'START_TIMEOUT', 5.0), patch.object(app.time, 'monotonic', lambda: old.now):
            with self.assertRaisesRegex(TimeoutError, 'startup timed out'):
                app.collect(old, threading.Event(), q, 4, {})
        new = self.startup_connection(6.0, .01)
        with patch.object(app.time, 'monotonic', lambda: new.now):
            kind, result = app.collect(new, threading.Event(), q, 4, {})
        self.assertEqual(kind, 'done', result)
        self.assertIsNone(result['host_stop_reason'])

    def test_startup_remains_bounded(self):
        q = RamQueue(self.ram, 8, lambda r: None)
        connection = self.startup_connection(30.0)
        with patch.object(app.time, 'monotonic', lambda: connection.now):
            with self.assertRaisesRegex(TimeoutError, 'startup timed out'):
                app.collect(connection, threading.Event(), q, 4, {})
        self.assertGreaterEqual(connection.now, 20.0)
        self.assertLess(connection.now, 20.02)

    def test_ready_restores_short_runtime_timeout(self):
        q = RamQueue(self.ram, 8, lambda r: None)
        connection = self.startup_connection(6.0)
        with patch.object(app.time, 'monotonic', lambda: connection.now):
            with self.assertRaisesRegex(TimeoutError, 'Solver worker lost'):
                app.collect(connection, threading.Event(), q, 4, {})
        self.assertGreaterEqual(connection.now, 6.75)
        self.assertLess(connection.now, 6.78)



if __name__ == '__main__':
    unittest.main()
