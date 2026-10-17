"""P1 register-model tests, optional AC5 object compile; no device access."""
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
                        help='Optional ARM Compiler 5 executable; compile P1 object only')
    args = parser.parse_args()
    out = ROOT / 'software/stm32/build/runtime-p1'
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
    run('compile-runtime', [gcc_executable(), '-std=c99', '-O2', '-Wall', '-Wextra',
        '-Wconversion', '-Wshadow', '-Werror', '-pedantic', '-D__USE_MINGW_ANSI_STDIO=1',
        *includes, 'software/common/s1/doa_solver.c', 'software/stm32/src/fpga_link.c',
        'software/stm32/src/ss_runtime.c', 'software/stm32/tests/test_ss_runtime.c',
        '-lm', '-o', out / 'runtime.exe'])
    result = run('runtime', [out / 'runtime.exe'])
    if not re.search(r'^P1_RESULT,PASS,checks=[1-9][0-9]*,failures=0$', result, re.M):
        raise RuntimeError('Missing P1 pass record')
    print(result, end='')
    if args.armcc:
        run('compile-armcc', [args.armcc, '--cpu=Cortex-M4.fp.sp', '--c99',
            '--library_type=microlib', '-O2', '--strict', '--diag_error=warning',
            *includes, '-c', 'software/stm32/src/ss_runtime.c', '-o', out / 'ss_runtime.o'])
        print('P1_ARMCC,OBJECT_COMPILE_PASS,NOT_LINKED_OR_BOARD_TESTED')
    else:
        print('P1_ARMCC,SKIP,NO_COMPILER_SPECIFIED')


if __name__ == '__main__':
    main()
