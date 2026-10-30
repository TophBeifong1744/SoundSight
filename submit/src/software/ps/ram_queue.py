"""有界待写队列。生产环境目录位于tmpfs，断电不保留；SD写失败则留下RAM文件。

只有SD的write/flush/fsync全部成功，才删除对应RAM文件并归还容量。
因此正在写盘的那条也占队列容量。此模块不访问硬件。
"""
from collections import deque
import json
import os
from pathlib import Path
import tempfile
import threading
import time


MAX_RECORD_BYTES = 16384


def durable_batch_sink(handle):
    """One barrier per bounded batch. Caller retains every RAM copy on failure."""
    def save(records):
        handle.write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
        handle.flush()
        os.fsync(handle.fileno())
    return save


def create_ram_directory():
    """只接受Linux已挂载的/dev/shm tmpfs，避免把临时目录误放回SD。"""
    mounts = Path('/proc/mounts').read_text().splitlines()
    if not any(row.split()[1:3] == ['/dev/shm', 'tmpfs'] for row in mounts):
        raise RuntimeError('/dev/shm is not a verified tmpfs; capture not started')
    # tmpfs在内存压力下可能换出。记录平台事实，不擅自修改系统swap配置。
    swap_active = len(Path('/proc/swaps').read_text().strip().splitlines()) > 1
    print('RAM_QUEUE_SWAP_ACTIVE=', swap_active, flush=True)
    return Path(tempfile.mkdtemp(prefix='soundsight-', dir='/dev/shm'))


class RamQueue:
    def __init__(self, directory, capacity, save, *, batch_size=1,
                 batch_wait=0.0, save_batch=None):
        if not 1 <= batch_size <= min(capacity, 64) or not 0 <= batch_wait <= 0.1:
            raise ValueError('invalid bounded SD batch configuration')
        if save_batch is None and (save is None or batch_size != 1):
            raise ValueError('batch sink required for batch_size > 1')
        self.directory = Path(directory)
        self.capacity = capacity
        self.save = save
        self.save_batch = save_batch
        self.batch_size = batch_size
        self.batch_wait = batch_wait
        self.pending = deque()
        self.condition = threading.Condition()
        self.closing = False
        self.error = None
        self.accepted = self.durable = self.durable_frames = self.peak = 0
        self.storage = dict(batches=0, records=0, max_batch=0,
                            total_save_ns=0, max_save_ns=0)
        # 若底层fsync挂死，主程序仍能STOP；待写文件保留在tmpfs中。
        self.writer = threading.Thread(target=self._write, name='soundsight-sd', daemon=True)

    def start(self):
        self.writer.start()

    @property
    def depth(self):
        with self.condition:
            return len(self.pending)

    def put(self, record):
        data = (json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8')
        if len(data) > MAX_RECORD_BYTES:
            raise ValueError('Record exceeds RAM queue size limit; consume not acknowledged')
        with self.condition:
            if self.closing or len(self.pending) >= self.capacity:
                raise RuntimeError('RAM queue closed or full; consume not acknowledged')
            ticket = self.accepted + 1
            path = self.directory / ('%08d.jsonl' % ticket)
            # close前写完完整JSON；不需要对RAM执行SD式耐久同步。
            # 写失败留下的.partial不是已接收记录，不能自动恢复为有效帧。
            partial = path.with_suffix('.partial')
            with partial.open('xb') as handle:
                handle.write(data)
            partial.rename(path)
            self.pending.append(path)
            self.accepted = ticket
            self.peak = max(self.peak, len(self.pending))
            self.condition.notify_all()
            return ticket

    def _write(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.pending or self.closing)
                    if not self.pending:
                        return
                    # Wait at most once per batch; new arrivals cannot extend
                    # the deadline. STOP/finish bypasses this coalescing delay.
                    self.condition.wait_for(
                        lambda: len(self.pending) >= self.batch_size or self.closing,
                        timeout=self.batch_wait)
                    paths = list(self.pending)[:self.batch_size]
                records = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
                began = time.monotonic_ns()
                if self.save_batch is None:
                    self.save(records[0])
                else:
                    self.save_batch(records)
                elapsed = time.monotonic_ns() - began
                with self.condition:
                    self.storage['batches'] += 1
                    self.storage['records'] += len(records)
                    self.storage['max_batch'] = max(self.storage['max_batch'], len(records))
                    self.storage['total_save_ns'] += elapsed
                    self.storage['max_save_ns'] = max(self.storage['max_save_ns'], elapsed)
                    for path, record in zip(paths, records):
                        path.unlink()  # fsync之后才撤销RAM保管；失败时允许重复，不能丢。
                        self.pending.popleft()
                        self.durable += 1
                        self.durable_frames += int('frame' in record)
                    self.condition.notify_all()
        except BaseException as exc:
            with self.condition:
                self.error = exc
                self.condition.notify_all()

    def finish(self, timeout):
        with self.condition:
            self.closing = True
            self.condition.notify_all()
        self.writer.join(timeout)
        if self.writer.is_alive() or self.error is not None or self.depth:
            raise RuntimeError('SD write failed or timed out; unsaved records remain in %s; keep power on. Cause=%s'
                               % (self.directory, self.error or 'writer timeout'))
        self.directory.rmdir()
