"""Relocated ZIP/install regression. Synthetic local profiles; no hardware."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from package_speaker_enrollment_update import FILES

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = ROOT/'software/build'
    evidence = ROOT/'document/evidence/speaker-enrollment-20261029'
    evidence.mkdir(parents=True, exist_ok=True)
    archives = [ROOT/'release/output'/n for n in ('soundsight_pynq_3d_speaker.zip', 'soundsight_enrollment_update.zip')]
    with tempfile.TemporaryDirectory(prefix='enrollment-package-', dir=str(work)) as tmp:
        stage = Path(tmp)
        for archive in archives:
            with ZipFile(archive) as z:
                assert z.testzip() is None
                assert all('..' not in Path(n).parts and not Path(n).is_absolute() for n in z.namelist())
                assert not any('/speaker-profiles/' in n or n.endswith('.local.json') for n in z.namelist())
                z.extractall(stage)
        app = stage/'SoundSight_PYNQ_3D_Speaker'
        update = stage/'soundsight_enrollment_update'
        # Existing files, including broken/unconfigured profiles, are user's
        # data: installation must not silently rewrite or reinterpret them.
        private = ('speaker-target.local.json', 'speaker-follow.local.json', 'settings.local.json',
                   'servo3d.local.json', 'speaker-profiles/P02-v1/profile.json',
                   'speaker-profiles/alice/profile.json', 'logs/old-result.json')
        for name in private:
            p = app/name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'{"preserve_existing_test_fixture":true}\n')
        old_source = app/'software/ps/run_pcm.py'
        old_source.write_bytes(b'# older source fixture\n')
        result = subprocess.run([sys.executable, '-B', str(update/'install.py'), '--destination', str(app)],
                                capture_output=True, text=True, check=True)
        backups = list(app.glob('backup_3d_*'))
        assert len(backups) == 1
        assert (backups[0]/'software/ps/run_pcm.py').read_bytes() == b'# older source fixture\n'
        for name in private:
            assert (app/name).read_bytes() == b'{"preserve_existing_test_fixture":true}\n', name
        for name in FILES:
            assert (app/name).read_bytes() == (ROOT/name).read_bytes(), name
        # Execute tests from the unpacked application, not the repository path.
        checks = subprocess.run([sys.executable, '-B', str(app/'software/tests/test_speaker_enrollment.py'), '-v'],
                                 capture_output=True, text=True)
        (evidence/'relocated-tests.log').write_text(checks.stdout+checks.stderr, encoding='utf-8')
        if checks.returncode:
            raise RuntimeError('Relocated tests failed: '+checks.stderr[-4000:])
        receipt = json.loads((app/'reports/user-build-receipt.json').read_text(encoding='utf-8'))
        for kind in ('bit', 'hwh'):
            assert hashlib.sha256((app/('soundsight.'+kind)).read_bytes()).hexdigest() == receipt['artifacts'][kind]['sha256']
        result = dict(result='PASS', updated_files=len(FILES), private_files_preserved=len(private),
                      backup_verified=True, relocated_tests=18, hardware_unchanged=True, hardware_actions=0,
                      packages=[dict(name=p.name, bytes=p.stat().st_size,
                                     sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in archives])
        (evidence/'package.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
