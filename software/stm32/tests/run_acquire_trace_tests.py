"""P4 acquisition diagnostics; PC only, no hardware or ARM build."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
OUT=ROOT/'software/stm32/build/acquire-trace'
OUT.mkdir(parents=True,exist_ok=True)

def run(name,cmd):
    p=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True)
    log='COMMAND: '+subprocess.list2cmdline([str(x) for x in cmd])+'\n'+p.stdout+p.stderr+'\nEXIT_CODE: '+str(p.returncode)+'\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if p.returncode:
        first=OUT/(name+'-first-failure.log')
        if not first.exists(): first.write_text(log,encoding='utf-8')
        raise RuntimeError(name+' failed; '+str(OUT))
    return p.stdout

print(run('regression',[sys.executable,'software/stm32/tests/run_start_trace_tests.py']))
run('compile',[gcc_executable(),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1',
 '-Isoftware/common','-Isoftware/common/s1','-Isoftware/stm32/include',
 'software/common/s1/doa_solver.c','software/stm32/src/fpga_link.c','software/stm32/tests/test_acquire_trace.c','-lm','-o',OUT/'trace.exe'])
print(run('trace',[OUT/'trace.exe']))
out=run('uart-bad-acquire',[ROOT/'software/stm32/build/host/selftest.exe','bad_acquire'])
required=['FIRMWARE_DIAG,P4_ACQUIRE_V3',
 'DATA,ACQUIRE_FORMAT,check=6,addr=0x0C,pair=3,word=0x664F1A00,snapshot=0x00017F39,frame=2',
 'DATA,ACQUIRE,status=8','last_error=8,recovery=1',
 'DATA,SAFETY,INVALID_READBACK,values_not_reported','pass=20,fail=3,skip=5,','forbidden_writes=0']
if any(s not in out for s in required) or 'DATA,TIMEOUT_TEST' in out:
    raise RuntimeError('UART diagnosis/classification failed: '+str(OUT/'uart-bad-acquire.log'))
print('ACQUIRE_TRACE_UART,PASS,second_BIST_pair3_rejection,no_timeout_injection')
