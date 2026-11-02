"""Copy the complete S2 recipe to a fresh directory; never start EDA or hardware."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def prepare(output):
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Refusing to overwrite existing work')
    if not str(output).isascii() or len(str(output).encode()) > 78:
        raise ValueError('Choose an ASCII output path of at most 78 bytes for Vivado')
    manifest = json.loads((ROOT/'project/screen_s2/source-map.json').read_text('utf-8'))
    payload=[]
    for row in manifest['files']:
        for key in ('source','destination'):
            p=PurePosixPath(row[key])
            if p.is_absolute() or '..' in p.parts or '\\' in row[key] or ':' in row[key]:
                raise ValueError('Unsafe manifest path')
        data=(ROOT/row['source']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('S2 source changed: '+row['source'])
        payload.append((row['destination'],data))
    output.mkdir(parents=True,exist_ok=True)
    for name,data in payload:
        p=output/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
    (output/'reports').mkdir(exist_ok=True)
    (output/'output').mkdir(exist_ok=True)
    # No sender-specific installation path. Default is project creation only.
    (output/'build.bat').write_bytes(b'''@echo off\r\nsetlocal\r\nif defined XILINX_VIVADO set "PATH=%XILINX_VIVADO%\\bin;%PATH%"\r\nwhere vivado.bat >nul 2>nul\r\nif errorlevel 1 exit /b 2\r\npushd "%~dp0"\r\nif "%~1"=="" goto prepare\r\nif "%~1"=="synth" goto build\r\nif "%~1"=="route" goto build\r\necho Usage: build.bat [synth or route]\r\npopd\r\nexit /b 2\r\n:prepare\r\ncall vivado.bat -mode batch -source project.tcl -log prepare.log -journal prepare.jou\r\ngoto done\r\n:build\r\ncall vivado.bat -mode batch -source build.tcl -log build.log -journal build.jou -tclargs %1\r\n:done\r\nset "ss_exit=%ERRORLEVEL%"\r\npopd\r\nexit /b %ss_exit%\r\n''')
    (output/'README.md').write_text(
        '# S2 hardware recipe\n\nVivado 2025.2, xc7z020clg400-2. '
        'Set XILINX_VIVADO or put vivado.bat on PATH.\n'
        '`build.bat` creates the project/BD/IP only. '
        '`build.bat synth` or `build.bat route` explicitly starts synthesis/implementation. '
        'Use a fresh copy for each invocation; existing project/par is rejected.\n'
        'No EDA was run by this preparation tool. Prior S2 reports describe the original candidate; '
        'this repository packaging change has only offline validation.\n',encoding='utf-8')
    print('S2_PREPARED files='+str(len(payload))+' EDA_STARTED=0 HARDWARE_ACCESSED=0')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
