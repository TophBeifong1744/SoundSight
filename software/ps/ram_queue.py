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


MAX_RECORD_BYTES = 16384


def create_ram_directory():
    """只接受Linux已挂载的/dev/shm tmpfs，避免把临时目录误放回SD。"""
    mounts = Path('/proc/mounts').read_text().splitlines()
    if not any(row.split()[1:3] == ['/dev/shm', 'tmpfs'] for row in mounts):
        raise RuntimeError('/dev/shm不是已确认的tmpfs；不启动采集')
    # tmpfs在内存压力下可能换出。记录平台事实，不擅自修改系统swap配置。
    swap_active = len(Path('/proc/swaps').read_text().strip().splitlines()) > 1
    print('RAM_QUEUE_SWAP_ACTIVE=', swap_active, flush=True)
    return Path(tempfile.mkdtemp(prefix='soundsight-', dir='/dev/shm'))


class RamQueue:
    def __init__(self, directory, capacity, save):
        self.directory = Path(directory)
        self.capacity = capacity
        self.save = save
        self.pending = deque()
        self.condition = threading.Condition()
        self.closing = False
        self.error = None
        self.accepted = self.durable = self.durable_frames = self.peak = 0
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
            raise ValueError('记录超过RAM队列单条上限；未确认消费')
        with self.condition:
            if self.closing or len(self.pending) >= self.capacity:
                raise RuntimeError('RAM队列已关闭或已满；未确认消费')
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
                    path = self.pending[0]
                record = json.loads(path.read_text(encoding='utf-8'))
                self.save(record)
                with self.condition:
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
            raise RuntimeError('SD写入失败或超时；未落盘记录保留于 %s；不要断电。原因=%s'
                               % (self.directory, self.error or 'writer timeout'))
        self.directory.rmdir()
