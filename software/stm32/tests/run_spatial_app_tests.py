"""D1 3D diagnostic application and board orchestration models; no hardware I/O."""
from pathlib import Path
import subprocess,sys,re
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
OUT=ROOT/'software/stm32/build/spatial-d1'
OUT.mkdir(parents=True,exist_ok=True)
def run(name,cmd,expected_exit=0):
    cmd=list(map(str,cmd));p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    log='COMMAND: '+subprocess.list2cmdline(cmd)+'\n'+p.stdout+p.stderr+f'\nEXIT_CODE: {p.returncode}\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if (expected_exit==0 and p.returncode!=0) or (expected_exit!=0 and p.returncode==0):
        first=OUT/(name+'-first-failure.log')
        if not first.exists():first.write_text(log,encoding='utf-8')
        raise RuntimeError(f'{name}: unexpected exit {p.returncode}')
    return p.stdout+p.stderr
inc=['-Isoftware/common','-Isoftware/common/s1','-Isoftware/common/s1_3d','-Isoftware/stm32/include']
base=[gcc_executable(),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1','-DSS_DOA_PROFILE=1',*inc]
sources=['software/common/s1/doa_solver.c','software/common/s1_3d/doa_solver_3d.c','software/common/s1_3d/doa_dispatch.c',*[f'software/stm32/src/{u}.c' for u in ('fpga_link','ss_runtime','ss_motion','ss_app','ss_spatial')]]
run('compile-app',base+sources+['software/stm32/tests/test_ss_spatial.c','-lm','-o',OUT/'app.exe'])
s=run('app',[OUT/'app.exe']);print(s,end='')
if not re.search(r'D1_RESULT,PASS,checks=\d+,failures=0',s):raise RuntimeError('Missing D1 result')
rejected=run('compile-motion-rejected',base+['-DSS_ENABLE_MOTION_WRITES=1','-c','software/stm32/src/ss_spatial.c','-o',OUT/'forbidden.o'],expected_exit=1)
if 'Three-dimensional diagnostic build must keep motion writes disabled' not in rejected:raise RuntimeError('Wrong compile rejection')
user='software/stm32/keil/soundsight_f407/User'
run('compile-board-model',base+['-Isoftware/stm32/tests/mock_hal','-I'+user]+sources+[user+'/soundsight_selftest.c','software/stm32/tests/test_selftest_host.c','-lm','-o',OUT/'board.exe'])
for mode,expected in [('board','pass=16,fail=0,skip=11'),('live','pass=35,fail=0,skip=4'),('no_peer','pass=16,fail=1,skip=10'),('commands','D1_COMMANDS,PASS')]:
    s=run('board-'+mode,[OUT/'board.exe',mode])
    if expected not in s or 'failures=0' not in s:raise RuntimeError('Unexpected 3D board model: '+mode)
    print('D1_BOARD_MODEL,'+mode+',EXPECTED_RESULT_OK,NOT_BOARD_MEASUREMENT')
print('D1_SUITE,PASS,live_profile_gate_closed,motion_compile_rejected')
