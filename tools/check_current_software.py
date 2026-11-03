"""Build the native C solver and run public-input host tests, without hardware."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TESTS=['software/tetra3d/tests/test_online_3d.py',
       'software/tetra3d/tests/test_follow_sound.py',
       'software/tests/test_speaker_follow.py',
       'software/tests/test_speaker_display.py',
       'software/tetra3d/tests/test_cf1.py',
       'software/tests/test_screen_product.py']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cc',default=os.environ.get('CC','gcc'))
    args=p.parse_args(); out=args.output.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('Refusing to overwrite existing work')
    cc=shutil.which(args.cc)
    if not cc: raise ValueError('C compiler not found: '+args.cc)
    out.mkdir(parents=True,exist_ok=True)
    library=out/('solver.dll' if os.name=='nt' else 'libss_solver_3d.so')
    common=ROOT/'software/common';core=ROOT/'software/tetra3d/core'
    cmd=[cc,'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-shared']
    if os.name!='nt':cmd.append('-fPIC')
    for include in [common,common/'s1',core]:cmd+=['-I',str(include)]
    cmd += [str(ROOT/'software/tetra3d/linux/ss_solver_3d_bridge.c'),str(common/'s1/doa_solver.c')]
    cmd += [str(core/n) for n in ['doa_solver_3d.c','doa_geometry.c','doa_target_3d.c']]
    cmd += ['-lm','-o',str(library)]
    env=os.environ.copy()
    for k in ('PYTHONPATH','PYTHONHOME','PYTHONUSERBASE'):env.pop(k,None)
    env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',CF1_TEST_LIBRARY=str(library))
    # Compiler runtime DLLs may live beside gcc on Windows.
    env['PATH']=str(Path(cc).parent)+os.pathsep+env.get('PATH','')
    build=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
    (out/'compile.log').write_text(build.stdout+build.stderr,encoding='utf-8')
    if build.returncode: raise RuntimeError(build.stdout+build.stderr)
    launcher=out/'run_host.py'
    launcher.write_text('import os,sys,types,runpy\nfrom pathlib import Path\n'
        'if os.name=="nt": sys.modules["resource"]=types.ModuleType("resource")\n'
        'path=Path(sys.argv[1]).resolve()\nsys.path.insert(0,str(path.parent))\n'
        'sys.argv=[str(path)]+sys.argv[2:]\nrunpy.run_path(str(path),run_name="__main__")\n',encoding='utf-8')
    results=[]
    for test in TESTS:
        run=subprocess.run([sys.executable,'-B',str(launcher),str(ROOT/test)],cwd=ROOT,env=env,
                           capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        log=run.stdout+run.stderr
        (out/(Path(test).stem+'.log')).write_text(log,encoding='utf-8')
        results.append(dict(test=test,exit=run.returncode,output=log))
        print(test+' EXIT='+str(run.returncode),flush=True)
    result=dict(scope='HOST_SYNTHETIC_AND_LOGIC_REGRESSION',native_library='BUILT_FROM_INCLUDED_SOURCE',
                windows_resource_import_shim=os.name=='nt',eda='NOT_RUN',hardware='NOT_RUN',tests=results)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return int(any(x['exit'] for x in results))

if __name__=='__main__':raise SystemExit(main())
