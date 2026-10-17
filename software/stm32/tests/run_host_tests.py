"""Rebuild migrated S1/S2 and selftest models; never contacts hardware."""
from pathlib import Path
import subprocess, sys, re
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from tool_config import gcc_executable
STM = ROOT / 'software/stm32'
COMMON = ROOT / 'software/common'
OUT = STM / 'build/host'
OUT.mkdir(parents=True, exist_ok=True)
BASE = [str(gcc_executable()), '-std=c99', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Wshadow', '-Werror', '-pedantic', '-D__USE_MINGW_ANSI_STDIO=1', '-I'+str(COMMON), '-I'+str(COMMON/'s1'), '-I'+str(COMMON/'s1_3d'), '-I'+str(STM/'include')]

def run(name, cmd):
    p = subprocess.run([str(v) for v in cmd], cwd=ROOT, capture_output=True, text=True)
    (OUT / (name+'.log')).write_text('COMMAND: '+subprocess.list2cmdline([str(v) for v in cmd])+'\n'+p.stdout+p.stderr, encoding='utf-8')
    if p.returncode:
        raise RuntimeError(f'{name}: exit {p.returncode}; see {OUT / (name+".log")}')
    return p.stdout

solver = COMMON / 's1/doa_solver.c'
link = STM / 'src/fpga_link.c'
run('compile-s1', BASE+[solver, COMMON/'s1/test_doa_solver.c', '-lm', '-o', OUT/'s1.exe'])
run('compile-s2', BASE+[solver, link, STM/'tests/test_fpga_link.c', '-lm', '-o', OUT/'s2.exe'])
for name, checks in [('s1',4705), ('s2',15980)]:
    output=run(name, [OUT/(name+'.exe')])
    expected=f'RESULT,PASS,checks={checks},failures=0'
    if expected not in output: raise RuntimeError(f'{name}: missing {expected}')
    print(expected)
user=STM/'keil/soundsight_f407/User'
run('compile-selftest', BASE+['-I'+str(STM/'tests/mock_hal'), '-I'+str(user), solver, link, STM/'src/ss_runtime.c', STM/'src/ss_motion.c', STM/'src/ss_app.c', user/'soundsight_selftest.c', STM/'tests/test_selftest_host.c', '-lm', '-o', OUT/'selftest.exe'])
expected={'board':(13,0,11,0), 'live':(32,0,4,302), 'no_peer':(13,1,10,1), 'dead_tick':(12,1,11,0), 'bad_config':(12,1,11,0)}
for mode,(passed,failed,skipped,transfers) in expected.items():
    output=run('host-'+mode,[OUT/'selftest.exe',mode])
    counts=f'pass={passed},fail={failed},skip={skipped},'
    if counts not in output or f'physical_model_transfers={transfers},forbidden_writes=0' not in output:
        raise RuntimeError(f'{mode}: unexpected classification or bus side effect')
    if failed and 'result=FAIL,NOT_SYSTEM_ACCEPTANCE' not in output:
        raise RuntimeError(f'{mode}: failure was hidden')
    print(f'HOST_MODEL,{mode},EXPECTED_COUNTS_OK,NOT_BOARD_MEASUREMENT')
output=run('host-commands',[OUT/'selftest.exe','commands'])
if 'COMMAND_TESTS,PASS' not in output or 'failures=0' not in output: raise RuntimeError('commands failed')
print('P3_COMMANDS,PASS,nonblocking_stream,STOP_ack,busy_config,no_motion')
print('MIGRATION_HOST_TESTS,PASS,5_SELFTEST_SCENARIOS')
