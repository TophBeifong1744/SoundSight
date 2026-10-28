"""Install the software increment into an existing PCM/PYNQ directory.

No bitstream, clock, MMIO, compilation or servo action. Back up only files
being updated; preserve voiceprint assets, user settings and saved evidence.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys


@contextmanager
def idle_owner():
    # Same ordinary process lock as all capture entrypoints. No hardware access.
    if sys.platform.startswith('linux'):
        import fcntl
        with open('/tmp/soundsight-ps-owner.lock', 'a', encoding='utf-8') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    else:
        yield  # Offline installation tests on the development PC.


def inside(path, base):
    try:
        path.resolve().relative_to(base)
        return True
    except ValueError:
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', type=Path, required=True)
    args = p.parse_args()
    source = Path(__file__).resolve().parent/'files'
    target = args.destination.resolve(strict=True)
    if not target.is_dir() or source == target or source in target.parents or target in source.parents:
        raise ValueError('Destination must be an existing, separate PYNQ application directory')
    required = ['soundsight.sh','software/ps/board_tools.py','software/ps/pcm_capture.py',
                'software/ps/ps_client.py','software/ps/volume_gate.py','software/ps/angle_filter.py',
                'software/ps/run_capture.py','software/ps/run_smp.py','software/tests/test_normal.py']
    for name in required:
        path = target/name
        if not path.is_file() or not inside(path, target):
            raise ValueError('Missing or external runtime dependency: '+name)
    files = sorted(p for p in source.rglob('*') if p.is_file())
    if not files:
        raise ValueError('Empty update')
    plan = []
    for item in files:
        relative = item.relative_to(source)
        destination = target/relative
        if item.is_symlink() or not inside(destination, target):
            raise ValueError('External/symbolic update path rejected: '+str(relative))
        plan.append((item, destination, relative))
    backup = target/('backup_3d_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    changes = []
    for item, destination, relative in plan:
        if destination.exists():
            old = backup/relative
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, old)
        changes.append(dict(path=relative.as_posix(), existed=destination.exists()))
    (backup/'FILES.json').write_text(json.dumps(changes, indent=2)+'\n', encoding='utf-8')
    for item, destination, relative in plan:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
    print('BACKUP='+str(backup))
    print('THREE_D_SOFTWARE_INSTALLED FILES=%d HARDWARE_ACTIONS=0 BIT_HWH_INCLUDED=0' % len(plan))


if __name__ == '__main__':
    try:
        with idle_owner():
            main()
    except Exception as exc:
        print('STOP: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
