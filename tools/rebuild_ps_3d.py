"""只重建最新三维工程和IP HDL；不运行综合、实现或硬件动作。"""
import argparse
import os
from pathlib import Path
import subprocess
import shutil
from datetime import datetime
from tool_config import vivado_root

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'project/par', help='New empty work directory; defaults to project/par')
    parser.add_argument('--check-tools', action='store_true', help='Resolve tools only; no project/hardware action')
    args = parser.parse_args()
    tool = vivado_root()
    if args.check_tools:
        print('VIVADO_FOUND=1 EDA_STARTED=0')
        return 0
    output = args.output.resolve()
    if not str(output).isascii():
        raise ValueError('Vivado FFT generation requires an ASCII output path; source-package path may contain Unicode')
    if len(str(output).encode('utf-8')) > 78:
        raise ValueError('Vivado Windows path limit: choose an output path of at most 78 UTF-8 bytes')
    if output.exists() and (not output.is_dir() or any(p.name != '_launcher' for p in output.iterdir())):
        raise ValueError('Output contains existing work; choose a new empty directory')
    log = output/'_launcher'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    log.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE'): env.pop(key, None)
    env['PATH'] = str(tool/'bin')+os.pathsep+env.get('PATH', '')
    resolved = shutil.which('vivado.bat', path=env['PATH'])
    if not resolved or Path(resolved).resolve() != (tool/'bin/vivado.bat').resolve():
        raise RuntimeError('Canonical vivado command does not match selected tool root')
    argv = ['-mode', 'batch', '-notrace', '-source', str(ROOT/'tools/rebuild_ps_3d_cli.tcl'),
            '-log', str(log/'vivado.log'), '-journal', str(log/'vivado.jou'), '-tclargs', str(output)]
    for value in argv:
        if any(c in value for c in '\r\n"%&|<>^!'): raise ValueError('Unsupported Windows batch path character')
    launch = log/'launch.bat'
    launch.write_text('@echo off\nchcp 65001 >nul\ncall vivado '+' '.join('"'+a+'"' for a in argv)+'\nexit /b %errorlevel%\n', encoding='utf-8')
    result = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(launch)],
                            cwd=log, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    print('PS_3D_PREPARE_EXIT='+str(result.returncode))
    print('LOG='+str(log/'vivado.log'))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
