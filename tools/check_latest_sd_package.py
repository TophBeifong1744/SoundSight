"""Check the final LAT1 SD ZIP after relocation, without board access."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',type=Path,default=ROOT/'project/reports/ps_3d/latest_result')
    evidence=parser.parse_args().evidence
    evidence.mkdir(parents=True,exist_ok=True)
    archive=ROOT/'release/output/soundsight_pynq_3d_speaker.zip'
    work=ROOT/'simulation/work';work.mkdir(parents=True,exist_ok=True)
    results=[];logs=[]
    with TemporaryDirectory(prefix='latest sd ',dir=work) as tmp:
        app=Path(tmp)/'SoundSight_PYNQ_3D_Speaker';app.mkdir()
        private=['settings.local.json','servo3d.local.json','speaker-follow.local.json',
                 'speaker-target.local.json','speaker-profiles/toph/profile.json','logs/existing.json']
        for name in private:
            p=app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'{"preserved":true}\n')
        with ZipFile(archive) as z:
            assert z.testzip() is None
            assert not any(n.endswith('.local.json') or '/speaker-profiles/' in n for n in z.namelist())
            assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
            z.extractall(tmp)
        for name in private:assert (app/name).read_bytes()==b'{"preserved":true}\n',name
        receipt=json.loads((app/'reports/user-build-receipt.json').read_text())
        for kind in ('bit','hwh'):
            assert hashlib.sha256((app/('soundsight.'+kind)).read_bytes()).hexdigest()==receipt['artifacts'][kind]['sha256']
        for p in (app/'software').rglob('*.py'):
            rel=p.relative_to(app)
            if (ROOT/rel).is_file():assert p.read_bytes()==(ROOT/rel).read_bytes(),str(rel)
        for test in ('software/tests/test_latest_result.py','software/tetra3d/tests/test_online_3d.py',
                     'software/tests/test_speaker_follow.py','software/tests/test_speaker_display.py',
                     'software/tests/test_speaker_enrollment.py','software/tests/test_speaker_statistics.py'):
            run=subprocess.run([sys.executable,'-B',test],cwd=app,capture_output=True,text=True)
            logs.append(test+'\n'+run.stdout+run.stderr)
            results.append(dict(test=test,exit=run.returncode))
            if run.returncode:raise RuntimeError(logs[-1])
    (evidence/'sd-package-tests.log').write_text('\n'.join(logs),encoding='utf-8')
    result=dict(result='PASS',private_files_preserved=6,bit_hwh_equal=True,tests=results,
                hardware_actions=0,zip_bytes=archive.stat().st_size,
                zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (evidence/'sd-package-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
