"""P4 trace tests; no hardware or ARM build. Run existing host tests first."""
from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
OUT=ROOT/'software/stm32/build/start-trace'
OUT.mkdir(parents=True,exist_ok=True)
def run(name, cmd):
    p=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True)
    log='COMMAND: '+subprocess.list2cmdline([str(x) for x in cmd])+'\n'+p.stdout+p.stderr+'\nEXIT_CODE: '+str(p.returncode)+'\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if p.returncode:
        first=OUT/(name+'-first-failure.log')
        if not first.exists(): first.write_text(log,encoding='utf-8')
        raise RuntimeError(name+' failed; '+str(OUT))
    return p.stdout
print(run('host-regression',[sys.executable,'software/stm32/tests/run_host_tests.py']))
run('compile',[gcc_executable(),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1',
 '-Isoftware/common','-Isoftware/common/s1','-Isoftware/stm32/include',
 'software/common/s1/doa_solver.c','software/stm32/src/fpga_link.c','software/stm32/tests/test_start_trace.c','-lm','-o',OUT/'trace.exe'])
print(run('trace',[OUT/'trace.exe']))
out=run('bad-start',[ROOT/'software/stm32/build/host/selftest.exe','bad_start'])
required=['step=11,op=R,addr=0x04,expected=0x0000000A,mask=0xFFFFFFFF,actual_valid=1,actual=0x00000008,bus_status=0,result=10,recovery=1',
 'DATA,SAFETY_READ_STATUS,act=12,watchdog=12,fault=12,last_error=10,recovery=1',
 'DATA,SAFETY,INVALID_READBACK,values_not_reported','pass=14,fail=3,skip=5,','forbidden_writes=0']
if any(s not in out for s in required) or 'DATA,SAFETY,act=0' in out:
    raise RuntimeError('bad-start output failed; see '+str(OUT/'bad-start.log'))
print('START_TRACE_UART,PASS,mode_readback_failure_and_invalid_safety_values_visible')
