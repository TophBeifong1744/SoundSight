"""P3 app integration tests, optional AC5 object compile; no device access."""
from pathlib import Path
import argparse
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from tool_config import gcc_executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--armcc', default=os.environ.get('SS_ARMCC'),
                        help='Optional ARM Compiler 5 executable; compile S2/P1/P2/app objects only')
    args = parser.parse_args()
    out = ROOT / 'software/stm32/build/integration-p3'
    out.mkdir(parents=True, exist_ok=True)

    def run(name, cmd):
        cmd = [str(v) for v in cmd]
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        log = 'COMMAND: ' + subprocess.list2cmdline(cmd) + '\n' + p.stdout + p.stderr
        log += f'\nEXIT_CODE: {p.returncode}\n'
        (out / (name + '.log')).write_text(log, encoding='utf-8')
        if p.returncode:
            # Preserve the first failure even if a later run succeeds.
            first = out / (name + '-first-failure.log')
            if not first.exists():
                first.write_text(log, encoding='utf-8')
            raise RuntimeError(f'{name} failed; see {out / (name + ".log")}')
        return p.stdout

    includes = ['-Isoftware/common', '-Isoftware/common/s1', '-Isoftware/common/s1_3d', '-Isoftware/stm32/include']
    for gate in (0, 1):
        flags = [f'-DSS_ENABLE_MOTION_WRITES={gate}'] if gate else []
        sources = ['software/common/s1/doa_solver.c', 'software/stm32/src/fpga_link.c',
                   'software/stm32/src/ss_motion.c', 'software/stm32/src/ss_runtime.c', 'software/stm32/src/ss_app.c', 'software/stm32/tests/test_ss_app.c']
        run(f'compile-app-{gate}', [gcc_executable(), '-std=c99', '-O2', '-Wall', '-Wextra',
            '-Wconversion', '-Wshadow', '-Werror', '-pedantic', '-D__USE_MINGW_ANSI_STDIO=1',
            *flags, *includes, *sources, '-lm', '-o', out / f'app-{gate}.exe'])
        result = run(f'app-{gate}', [out / f'app-{gate}.exe'])
        if not re.search(rf'^P3_RESULT,PASS,gate={gate},checks=[1-9][0-9]*,failures=0$', result, re.M):
            raise RuntimeError('Missing P3 pass record')
        print(result, end='')
        if args.armcc:
            for unit in ('fpga_link', 'ss_motion', 'ss_runtime', 'ss_app'):
                run(f'armcc-{unit}-{gate}', [args.armcc, '--cpu=Cortex-M4.fp.sp', '--c99',
                    '--library_type=microlib', '-O2', '--strict', '--diag_error=warning',
                    *flags, *includes, '-c', f'software/stm32/src/{unit}.c',
                    '-o', out / f'{unit}-{gate}.o'])
            print(f'P3_ARMCC,gate={gate},OBJECT_COMPILE_PASS,NOT_LINKED_OR_BOARD_TESTED')
        else:
            print(f'P3_ARMCC,gate={gate},SKIP,NO_COMPILER_SPECIFIED')



if __name__ == '__main__':
    main()
