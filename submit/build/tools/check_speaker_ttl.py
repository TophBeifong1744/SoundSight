"""Linux-only offline regression for score-TTL permission; no board access."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    'software/tests/test_speaker_follow.py',
    'software/tests/test_speaker_display.py',
    'software/tests/test_latest_result.py',
    'software/tests/test_speaker_process.py',
    'software/tetra3d/tests/test_online_3d.py',
)


def check_increment(evidence):
    """Install the shipped increment over a relocated app with private settings."""
    work = ROOT/'simulation/work'
    work.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='speaker ttl install ', dir=work) as tmp:
        tmp = Path(tmp)
        with ZipFile(ROOT/'release/output/soundsight_pynq_3d_speaker.zip') as z:
            z.extractall(tmp)
        app = tmp/'SoundSight_PYNQ_3D_Speaker'
        private = {
            'speaker-follow.local.json': json.dumps(dict(schema=1, threshold=.45,
                permit_seconds=10., policy='delayed_permission_v1', recognition_qualified=False)).encode(),
            'speaker-target.local.json': b'{"target_id":"user2"}',
            'speaker-profiles/user2/profile.json': b'{"private":"fixture"}',
            'logs/existing.json': b'{"preserve":true}',
        }
        for name, data in private.items():
            p = app/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        bit_before = (app/'soundsight.bit').read_bytes()
        hwh_before = (app/'soundsight.hwh').read_bytes()
        # A recognizable previous source proves the installer actually backs up.
        (app/'software/ps/speaker_permission.py').write_text('# previous installed source\n')
        with ZipFile(ROOT/'release/output/soundsight_enrollment_update.zip') as z:
            z.extractall(tmp)
        update = tmp/'soundsight_enrollment_update'
        run = subprocess.run([sys.executable, '-B', str(update/'install.py'),
                              '--destination', str(app)], capture_output=True, text=True)
        (evidence/'increment-install.log').write_text(run.stdout+run.stderr, encoding='utf-8')
        assert run.returncode == 0, run.stdout+run.stderr
        backups = list(app.glob('backup_3d_*'))
        assert len(backups) == 1
        assert (backups[0]/'software/ps/speaker_permission.py').read_text() == '# previous installed source\n'
        for name, data in private.items():
            assert (app/name).read_bytes() == data, name
        for p in (update/'files').rglob('*'):
            if p.is_file():
                rel = p.relative_to(update/'files')
                assert p.read_bytes() == (ROOT/rel).read_bytes() == (app/rel).read_bytes(), str(rel)
        assert (app/'soundsight.bit').read_bytes() == bit_before
        assert (app/'soundsight.hwh').read_bytes() == hwh_before
        probe = subprocess.run([sys.executable, '-B', '-c',
            "import sys;sys.path.insert(0,'software/ps');from speaker_permission import load_settings;"
            "s=load_settings('.');assert (s['policy'],s['threshold'],s['permit_seconds'])==('score_ttl_v2',.45,10.)"],
            cwd=app, capture_output=True, text=True)
        assert probe.returncode == 0, probe.stderr
    (evidence/'increment-check.json').write_text(json.dumps(dict(result='PASS',
        private_files_preserved=4, previous_source_backed_up=True, bit_hwh_unchanged=True,
        legacy_settings_preserved=True, hardware_actions=0), indent=2)+'\n')


def main():
    evidence = ROOT/'document/evidence/speaker-ttl-20261030'
    evidence.mkdir(parents=True, exist_ok=True)
    results = []
    for name in TESTS:
        run = subprocess.run([sys.executable, '-B', name, '-v'], cwd=ROOT,
                             capture_output=True, text=True)
        (evidence/(Path(name).stem+'.log')).write_text(run.stdout+run.stderr, encoding='utf-8')
        results.append(dict(test=name, exit=run.returncode))
        print(name, run.returncode, flush=True)
        if run.returncode:
            print(run.stdout+run.stderr)
    passed = all(r['exit'] == 0 for r in results)
    if passed:
        check_increment(evidence)
    (evidence/'tests.json').write_text(json.dumps(dict(
        result='PASS' if passed else 'FAIL', tests=results, hardware_actions=0), indent=2)+'\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
