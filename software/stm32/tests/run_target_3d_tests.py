"""D4 pure dual-axis mapping tests; optional ARMCC5 object compile, no device I/O."""
from pathlib import Path
import argparse
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
OUT=ROOT/'software/stm32/build/target-d4'
OUT.mkdir(parents=True,exist_ok=True)

def run(name,command):
    command=list(map(str,command));p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    log='COMMAND: '+subprocess.list2cmdline(command)+'\n'+p.stdout+p.stderr+f'\nEXIT_CODE: {p.returncode}\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if p.returncode:
        first=OUT/(name+'-first-failure.log')
        if not first.exists():first.write_text(log,encoding='utf-8')
        raise RuntimeError(name+' failed; '+str(OUT/(name+'.log')))
    return p.stdout

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--armcc');args=ap.parse_args()
    inc=['-Isoftware/common','-Isoftware/common/s1','-Isoftware/common/s1_3d']
    sources=['software/common/s1/doa_solver.c',*[f'software/common/s1_3d/{u}.c' for u in ('doa_solver_3d','doa_dispatch','doa_target_3d')],'software/stm32/tests/test_target_3d.c']
    run('compile',[gcc_executable(),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1','-DSS_DOA_PROFILE=1',*inc,*sources,'-lm','-o',OUT/'target.exe'])
    result=run('test',[OUT/'target.exe']);print(result,end='')
    if 'D4_RESULT,PASS' not in result or 'failures=0' not in result:raise RuntimeError('Missing pass result')
    if args.armcc:
        run('armcc-object',[args.armcc,'--cpu=Cortex-M4.fp.sp','--c99','--library_type=microlib','-O2','--strict','--diag_error=warning',*inc,'-c','software/common/s1_3d/doa_target_3d.c','-o',OUT/'doa_target_3d.o'])
        print('D4_ARMCC,PASS,OBJECT_ONLY,NOT_LINKED_OR_BOARD_TESTED')
    else:print('D4_ARMCC,SKIP,NO_COMPILER_SPECIFIED')
if __name__=='__main__':main()
