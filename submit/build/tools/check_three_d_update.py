"""Exercise the ZIP installer in a disposable receiver, without board access."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', required=True)
    args = parser.parse_args()
    evidence = ROOT/'document/evidence/ps-dual-axis-20261028'
    base = (ROOT/'software/build').resolve()
    base.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='three-d-package-', dir=str(base)) as name:
        temp = Path(name).resolve()
        temp.relative_to(base)  # Verify cleanup remains in this task's output tree.
        with ZipFile(ROOT/'release/output/soundsight_3d_software_update.zip') as z:
            assert z.testzip() is None
            for entry in z.namelist():
                assert not Path(entry).is_absolute() and '..' not in Path(entry).parts
                if entry.endswith('.py'):
                    ast.parse(z.read(entry).decode('utf-8'), feature_version=(3, 8))
                if '/files/' in entry:
                    relative = entry.split('/files/', 1)[1]
                    assert z.read(entry) == (ROOT/relative).read_bytes(), relative
            z.extractall(temp)
        app = temp/'receiver with spaces'
        (app/'software/ps').mkdir(parents=True)
        (app/'software/tests').mkdir()
        for p in (ROOT/'software/ps').glob('*.py'):
            shutil.copy2(p, app/'software/ps'/p.name)
        for relative in ('soundsight.sh', 'software/tests/test_normal.py'):
            shutil.copy2(ROOT/relative, app/relative)
        protected = ['soundsight.bit', 'soundsight.hwh', 'settings.local.json',
                     'servo3d.local.json', 'speaker-private.wav', 'logs/old.json']
        for relative in protected:
            p = app/relative
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(('PRESERVE:'+relative).encode('ascii'))
        old = app/'software/ps/run_normal.py'
        old.write_bytes(old.read_bytes()+b'\n# prior receiver source\n')
        prior = old.read_bytes()
        installer = temp/'soundsight_3d_software_update/install.py'
        commands = [
            [sys.executable, '-B', str(installer), '--destination', str(app)],
            [sys.executable, '-B', str(app/'software/tetra3d/tests/test_online_3d.py')],
            [sys.executable, '-B', str(app/'software/tetra3d/tests/test_solver_3d_migration.py'),
             '--cc', args.cc, '--output', str(temp/'numeric.json')],
            [sys.executable, '-B', str(installer), '--destination', str(app)]]
        for index, command in enumerate(commands):
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
            (evidence/('package-step-%d.txt' % index)).write_text(run.stdout+run.stderr, encoding='utf-8')
            results.append(dict(step=index, exit=run.returncode, tail=(run.stdout+run.stderr).splitlines()[-5:]))
            assert run.returncode == 0, run.stdout+run.stderr
        assert any((p/'software/ps/run_normal.py').read_bytes() == prior for p in app.glob('backup_3d_*'))
        for relative in protected:
            assert (app/relative).read_bytes() == ('PRESERVE:'+relative).encode('ascii')
        missing = temp/'empty receiver'
        missing.mkdir()
        rejected = subprocess.run([sys.executable, '-B', str(installer), '--destination', str(missing)],
                                  capture_output=True, text=True)
        assert rejected.returncode != 0 and not list(missing.iterdir())
        results.append(dict(missing_dependencies_rejected=True, protected_files=len(protected),
                            prior_source_backed_up=True, repeat_install=True))
    (evidence/'package-check.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(results, indent=2))
    print('THREE_D_PACKAGE_PASS HARDWARE_ACTIONS=0 TEMP_TREE_REMOVED=1')


if __name__ == '__main__':
    main()
