"""Compile each selectable solver profile against existing frozen inputs."""
from pathlib import Path
import sys, subprocess
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
COMMON=ROOT/'software/common'
OUT=ROOT/'software/stm32/build/tetra3d'
OUT.mkdir(parents=True,exist_ok=True)
base=[str(gcc_executable()),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1','-I'+str(COMMON),'-I'+str(COMMON/'s1'),'-I'+str(COMMON/'s1_3d')]
sources=[COMMON/'s1/doa_solver.c',COMMON/'s1_3d/doa_solver_3d.c',COMMON/'s1_3d/doa_dispatch.c',ROOT/'software/stm32/tests/test_doa_3d.c']
for profile in (0,1):
    exe=OUT/f'test_3d_profile{profile}.exe'
    for name,cmd in [('compile',base+[f'-DSS_DOA_PROFILE={profile}',*map(str,sources),'-lm','-o',str(exe)]),('run',[str(exe)])]:
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        (OUT/f'{name}-{profile}.log').write_text('COMMAND: '+subprocess.list2cmdline(cmd)+'\n'+p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:
            print(p.stdout+p.stderr);raise SystemExit(p.returncode)
        if name=='run':print(p.stdout)
