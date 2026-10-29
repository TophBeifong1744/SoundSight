"""Package the complete source recipe, excluding machine state and old reports."""
from pathlib import Path
import argparse
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FIXED = '''LICENSE
project/script/rebuild_ps_3d.bat
project/script/rebuild_ps_3d.tcl
project/script/setting.bat
project/script/ps_3d_sources.txt
project/ip/ps_3d_fft.tcl
project/bd/ps_3d_export.tcl
tools/rebuild_ps_3d.py
tools/rebuild_ps_3d_cli.tcl
tools/tool_config.py
tools/package_vivado_ps_3d.py
tools.local.env.example
document/vivado-ps-3d-rebuild.md'''.splitlines()
CONSTRAINTS = ['spi_ila_debug.xdc', 'board_pins.xdc', 'interface_timing.xdc',
               'horizontal_reserved.xdc', 'dual_axis_output_timing.xdc']


def payload(root=ROOT):
    sources = [s.strip() for s in (root/'project/script/ps_3d_sources.txt').read_text().splitlines()
               if s.strip() and not s.startswith('#')]
    if len(sources) != 32 or len(set(sources)) != 32:
        raise ValueError('Expected 31 unique RTL sources plus one memory file')
    names = FIXED + sources + ['project/sdc/ps/'+s for s in CONSTRAINTS]
    result = {}
    for name in names:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Nonportable member name')
        data = (root/name).read_bytes()
        text = data.decode('utf-8-sig')
        if re.search(r'(?i)[a-z]:[/\\]|\\\\[A-Za-z0-9_.-]+\\|/(?:home|Users)/', text):
            raise ValueError('Absolute machine path in '+name)
        result[name] = data
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_vivado_ps_3d.zip')
    args = parser.parse_args()
    files = payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, 'w', ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr('SoundSight_Vivado_PS_3D/'+name, data)
        archive.writestr('SoundSight_Vivado_PS_3D/FILES.txt', '\n'.join(files)+'\n')
    with ZipFile(args.output) as archive:
        assert archive.testzip() is None
    print('PORTABLE_FILES='+str(len(files))+' ZIP_CRC=PASS MACHINE_PATHS=0')


if __name__ == '__main__':
    main()
