'Install a PS-only update with backups. Keep bit/HWH, C library and historical logs unchanged.'
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def install(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    for name in ('soundsight.bit', 'soundsight.hwh', 'software/ps/libss_solver.so'):
        if not (destination/name).is_file():
            raise FileNotFoundError('Target is not an installed volume directory; missing: '+name)
    manifest = json.loads((source/'FILES.json').read_text(encoding='utf-8'))
    pairs = []
    for name in manifest:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError('Invalid relative path')
        if not name.startswith(('software/ps/', 'software/tests/', 'document/')) and name not in ('tools/install_normal_update.py', 'soundsight.sh'):
            raise ValueError('Path is outside the software update scope')
        src, dst = source/'payload'/relative, destination/relative
        if not src.is_file() or destination not in dst.resolve().parents:
            raise ValueError('Missing source or target outside destination: '+name)
        pairs.append((name, src, dst))
    backup = Path(tempfile.mkdtemp(prefix='backup_normal_', dir=str(destination)))
    added = []
    # 所有旧文件先备份完成，之后才替换；中途失败保留备份与实际状态。
    for name, src, dst in pairs:
        if dst.exists():
            old = backup/name
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, old)
        else:
            added.append(name)
    (backup/'added-files.json').write_text(json.dumps(added, indent=2), encoding='utf-8')
    print('BACKUP=', backup, flush=True)
    for name, src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.normal-update-', dir=str(dst.parent))
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(src.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            # sudo安装后普通xilinx用户仍须能读取源码与执行离线自测。
            os.chmod(temp, 0o644)
            os.replace(temp, dst)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        if dst.read_bytes() != src.read_bytes():
            raise RuntimeError('Copy verification failed: '+name)
    print('NORMAL_UPDATE_INSTALLED FILES=', len(pairs), 'HARDWARE_ACTIONS=0')
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true', help='After installation, test software and load/verify FPGA using soundsight.sh prepare')
    args = parser.parse_args()
    # 与运行程序共用原单所有者锁；有采集进程时拒绝热替换。
    import fcntl
    with open('/tmp/soundsight-ps-owner.lock', 'a') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Stop normal/debug capture before installing the update') from None
        install(Path(__file__).resolve().parent, args.destination)
    # 退出安装互斥锁后再准备：prepare有自己的锁；默认install仍然不碰硬件。
    if args.prepare:
        raise SystemExit(subprocess.call(['sh', str(args.destination.resolve()/'soundsight.sh'), 'prepare']))


if __name__ == '__main__':
    main()
