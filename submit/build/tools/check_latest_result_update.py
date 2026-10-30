"""Offline relocated installation test; preserves private files and bit/HWH."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = ROOT/'simulation/work'
    work.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='latest package ', dir=work) as temp:
        base = Path(temp)
        for name in ('soundsight_pynq_3d_speaker.zip', 'soundsight_latest_result_update.zip'):
            with ZipFile(ROOT/'release/output'/name) as z:
                assert z.testzip() is None
                z.extractall(base)
        target = base/'SoundSight_PYNQ_3D_Speaker'
        private = ('speaker-follow.local.json', 'speaker-profiles/test/profile.json',
                   'servo-3d.local.json', 'logs/keep.json')
        for name in private:
            p = target/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'{"keep":true}\n')
        preserved = {name: (target/name).read_bytes() for name in (*private, 'soundsight.bit', 'soundsight.hwh')}
        old = (target/'software/tetra3d/linux/client_3d.py').read_bytes()
        subprocess.run([sys.executable, '-B', str(base/'soundsight_latest_result_update/install.py'),
                        '--destination', str(target)], check=True)
        backups = list(target.glob('backup_3d_*'))
        assert len(backups) == 1
        assert (backups[0]/'software/tetra3d/linux/client_3d.py').read_bytes() == old
        for name, data in preserved.items():
            assert (target/name).read_bytes() == data, name
        assert (target/'software/tetra3d/linux/client_3d.py').read_bytes() == (ROOT/'software/tetra3d/linux/client_3d.py').read_bytes()
        for test in ('software/tests/test_latest_result.py', 'software/tetra3d/tests/test_online_3d.py',
                     'software/tests/test_speaker_follow.py'):
            subprocess.run([sys.executable, '-B', test], cwd=target, check=True)
        print('LATEST_PACKAGE_PASS PRIVATE_FILES=4 BIT_HWH_UNCHANGED=1 BACKUP_VERIFIED=1 HARDWARE_ACTIONS=0')


if __name__ == '__main__':
    main()
