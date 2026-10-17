"""只准备/打开独立SoundSight工程，或生成IP输出；不提供自动综合/实现/下载动作。"""
from pathlib import Path
import argparse, os, subprocess, time

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('prepare','open','outputs'),nargs='?',default='prepare')
    ap.add_argument('variant',choices=('stm32','ps'),nargs='?',default='stm32')
    args=ap.parse_args()
    toolroot=Path(os.environ.get('VIVADO_ROOT','F:/AMD/2025.2/Vivado'))
    out=ROOT/('project/par' if args.variant=='stm32' else 'variants/pl_ps/project/par')
    log=out/'_launcher'/time.strftime('%Y%m%d_%H%M%S');log.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE'):env.pop(key,None)
    env['PATH']=str(toolroot/'bin')+os.pathsep+env.get('PATH','')
    argv=['-mode','gui' if args.action=='open' else 'batch','-notrace','-source',str(ROOT/'tools/vivado_cli.tcl'),
          '-log',str(log/'vivado.log'),'-journal',str(log/'vivado.jou'),'-tclargs',args.action,args.variant]
    for value in argv:
        if any(c in value for c in '\n\r"%&|<>^'):raise ValueError('Unsupported Windows batch argument')
    bat=log/'launch.bat';bat.write_text('@echo off\ncall vivado '+' '.join('"'+a+'"' for a in argv)+'\nexit /b %errorlevel%\n','utf-8')
    command=[os.environ.get('COMSPEC','C:/Windows/System32/cmd.exe'),'/d','/c',str(bat)]
    if args.action=='open':
        subprocess.Popen(command,cwd=out,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        print('VIVADO_GUI_STARTED',out);return 0
    result=subprocess.run(command,cwd=out,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    print('VIVADO_PREPARATION_EXIT',result.returncode,'LOG',log)
    return result.returncode

if __name__=='__main__':raise SystemExit(main())
