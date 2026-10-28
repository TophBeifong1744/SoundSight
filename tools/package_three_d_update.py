"""Build a small 3-D software increment, without bit/HWH or private voice assets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'release/output/soundsight_3d_software_update.zip'


def selected():
    names = ['soundsight-3d.sh', 'software/ps/run_normal.py',
             'software/ps/speaker_permission.py',
             'software/ps/run_capture.py', 'software/ps/horizontal_motion.py',
             'software/ps/board_tools.py',
             'software/ps/build_solver.sh', 'software/ps/ss_solver_bridge.c',
             'document/pynq-three-d-dual-axis.md', 'document/ps-dual-axis-interface.md',
             'document/pynq-three-d-sd.md',
             'software/common/fpga_stm32_abi_frozen.h',
             'software/common/s1/doa_solver.h', 'software/common/s1/doa_solver.c']
    for folder in ('software/tetra3d/core', 'software/tetra3d/linux', 'software/tetra3d/tests'):
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).iterdir()
                     if p.is_file() and p.suffix in ('.py', '.c', '.h', '.json', '.sh'))
    return sorted(set(names))


def main():
    names = selected()
    for name in names+['tools/install_three_d_update.py']:
        p = ROOT/name
        if p.suffix == '.py':
            ast.parse(p.read_text(encoding='utf-8'), feature_version=(3,8))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, 'w', ZIP_DEFLATED) as z:
        z.write(ROOT/'tools/install_three_d_update.py', 'soundsight_3d_software_update/install.py')
        for name in names:
            z.write(ROOT/name, 'soundsight_3d_software_update/files/'+name)
        z.writestr('soundsight_3d_software_update/README.txt',
                   'Software increment only. No bit/HWH, private voice assets, user settings or board action.\n'
                   'Read files/document/pynq-three-d-dual-axis.md before installation.\n'
                   'Use only with the new dual-axis candidate after user implementation/timing checks.\n'
                   'Angle-only and manual control are standalone; automatic following also requires B speaker runtime/assets.\n')
    with ZipFile(OUT) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(names)+2
    print('THREE_D_UPDATE=%s FILES=%d BYTES=%d BIT_HWH=NOT_INCLUDED' % (OUT,len(names),OUT.stat().st_size))


if __name__ == '__main__':
    main()
