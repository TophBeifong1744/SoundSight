import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
shutil.copytree(ROOT/'runtime', ROOT/'verification/runtime', dirs_exist_ok=True)
env = dict(os.environ, CF1_TEST_LIBRARY=str(ROOT.parent/'ss-c-3d-analysis-20261101/reference/solver.dll'))
tests = ['software/tetra3d/tests/test_online_3d.py',
         'software/tetra3d/tests/test_follow_sound.py',
         'software/tests/test_speaker_follow.py',
         'software/tests/test_speaker_display.py',
         'software/tetra3d/tests/test_cf1.py']
for test in tests:
    run = subprocess.run([sys.executable, str(ROOT/'verification/run_host.py'), str(ROOT/'verification/runtime'/test)],
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (ROOT/'verification'/Path(test).with_suffix('.log').name).write_bytes(run.stdout)
    print(test, 'EXIT='+str(run.returncode), flush=True)
    if run.returncode:
        print(run.stdout.decode(errors='replace'))
        raise SystemExit(run.returncode)
