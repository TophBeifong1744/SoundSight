"""Deterministic SD barrier/backlog tests; no hardware or timing assumptions."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ps'))
import ram_queue
from run_capture import durable_sink


def barrier_workload(batched=False):
    """Four arrivals per SD barrier; 64 capacity/48 stop, no sleeps."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ram = root / 'ram'
        ram.mkdir()
        produced = 0
        stopped = False
        barriers = 0
        with (root / 'out.jsonl').open('w', encoding='utf-8') as handle:
            if batched:
                q = ram_queue.RamQueue(ram, 64, None, batch_size=8,
                                      batch_wait=0, save_batch=ram_queue.durable_batch_sink(handle))
            else:
                q = ram_queue.RamQueue(ram, 64, durable_sink(handle))

            def produce(count):
                nonlocal produced, stopped
                for _ in range(count):
                    if stopped or produced >= 240:
                        break
                    produced += 1
                    q.put({'frame': {'sequence': produced}})
                    if q.depth >= 48:
                        stopped = True

            def sync(fd):
                nonlocal barriers
                barriers += 1
                produce(4)

            produce(8)
            # Run the actual writer in this thread; finish when it empties.
            # put rejects closing, so the last sink signals closure itself.
            original_save = q.save
            def save(record):
                original_save(record)
                if stopped or produced == 240:
                    q.closing = True
            q.save = save
            if batched:
                original_batch = q.save_batch
                def batch(records):
                    original_batch(records)
                    if stopped or produced == 240:
                        q.closing = True
                q.save_batch = batch
            with patch('os.fsync', side_effect=sync):
                q._write()
            if q.error:
                raise q.error
        rows = [json.loads(s) for s in (root / 'out.jsonl').read_text().splitlines()]
        assert [r['frame']['sequence'] for r in rows] == list(range(1, produced + 1))
        assert q.depth == 0 and q.durable_frames == produced
        return dict(produced=produced, high_water=stopped, barriers=barriers, peak=q.peak)


class BacklogTests(unittest.TestCase):
    def test_original_per_record_sync_reaches_high_water(self):
        result = barrier_workload(batched=False)
        print('ORIGINAL_BARRIER_WORKLOAD=', result)
        self.assertTrue(result['high_water'])
        self.assertEqual(result['peak'], 48)

    def test_arrivals_during_sd_barriers_finish_without_high_water(self):
        result = barrier_workload(batched=hasattr(ram_queue, 'durable_batch_sink'))
        print('BARRIER_WORKLOAD=', result)
        self.assertFalse(result['high_water'])
        self.assertEqual(result['produced'], 240)

    def test_write_flush_and_sync_failure_keep_entire_batch(self):
        for stage in ('write', 'flush', 'fsync'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                ram = Path(tmp) / 'ram'
                ram.mkdir()
                class Handle:
                    def write(self, data):
                        if stage == 'write':
                            raise OSError('injected write failure')
                        return len(data)
                    def flush(self):
                        if stage == 'flush':
                            raise OSError('injected flush failure')
                    def fileno(self):
                        return 123
                def sync(fd):
                    if stage == 'fsync':
                        raise OSError('injected fsync failure')
                q = ram_queue.RamQueue(ram, 8, None, batch_size=4,
                                      save_batch=ram_queue.durable_batch_sink(Handle()))
                for i in range(6):
                    q.put({'frame': {'sequence': i}})
                with patch('os.fsync', side_effect=sync):
                    q.start()
                    with self.assertRaises(RuntimeError):
                        q.finish(2)
                self.assertEqual(q.durable, 0)
                self.assertEqual(q.depth, 6)
                self.assertEqual(len(list(ram.glob('*.jsonl'))), 6)

    def test_blocked_sync_keeps_inflight_capacity_and_partial_tail_flushes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ram = root / 'ram'
            ram.mkdir()
            entered, release = threading.Event(), threading.Event()
            def sync(fd):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('test sync release missing')
            with (root / 'out').open('w', encoding='utf-8') as h:
                q = ram_queue.RamQueue(ram, 6, None, batch_size=4,
                                      save_batch=ram_queue.durable_batch_sink(h))
                for i in range(4):
                    q.put({'frame': {'sequence': i}})
                with patch('os.fsync', side_effect=sync):
                    q.start()
                    try:
                        self.assertTrue(entered.wait(2))
                        q.put({'frame': {'sequence': 4}})
                        q.put({'frame': {'sequence': 5}})
                        with self.assertRaises(RuntimeError):
                            q.put({'frame': {'sequence': 6}})
                        with self.assertRaises(RuntimeError):
                            q.finish(.01)
                        self.assertEqual(q.durable, 0)
                        self.assertEqual(len(list(ram.glob('*.jsonl'))), 6)
                    finally:
                        release.set()
                        q.writer.join(2)
                    q.finish(2)
                self.assertEqual(q.storage['batches'], 2)
                self.assertEqual(q.storage['records'], 6)
                self.assertEqual(q.durable_frames, 6)
            rows = [json.loads(s) for s in (root / 'out').read_text().splitlines()]
            self.assertEqual([r['frame']['sequence'] for r in rows], list(range(6)))

    def test_partial_live_batch_has_bounded_wait_without_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            ram = Path(tmp) / 'ram'
            ram.mkdir()
            saved = threading.Event()
            q = ram_queue.RamQueue(ram, 64, None, batch_size=8, batch_wait=.05,
                                  save_batch=lambda records: saved.set())
            q.start()
            try:
                q.put({'frame': {'sequence': 1}})
                self.assertTrue(saved.wait(1))
            finally:
                q.finish(2)

    def test_invalid_batch_configuration(self):
        for size, wait in ((0, 0), (65, 0), (8, -.1), (8, float('nan')), (8, .101)):
            with self.assertRaises(ValueError):
                ram_queue.RamQueue('.', 64, None, batch_size=size, batch_wait=wait)


if __name__ == '__main__':
    unittest.main()
