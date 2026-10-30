"""Directed statistics/permission/launcher regression and actual update install."""
import json
from pathlib import Path
import subprocess
import sys

from check_speaker_ttl import ROOT, TESTS, check_increment


def main():
    evidence = ROOT/'document/evidence/speaker-statistics-20261030'
    evidence.mkdir(parents=True, exist_ok=True)
    results = []
    tests = ('software/tests/test_speaker_statistics.py',
             'software/tests/test_three_d_launcher.py', *TESTS)
    for name in tests:
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
