"""只打包当前PS软件与必要自测，不接触用户外部Vivado工程或SD卡。"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TESTS = ('test_normal.py', 'test_normal_update.py', 'test_buffered.py', 'test_sd_batch.py',
         'test_online_angle_filter.py', 'test_volume_gate.py', 'test_smp.py',
         'test_serial_english.py', 'test_board_tools.py', 'test_launcher.py', 'test_filter_controls.py',
         'test_horizontal_motion.py', 'test_manual_servo.py')


def build(output):
    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'software/ps').glob('*.py'))
    files += ['software/tests/'+name for name in TESTS]
    files += ['document/pynq-normal-mode.md', 'document/pynq-board-helper.md', 'document/pynq-horizontal.md',
              'document/ps-manual-calibration.md', 'document/pynq-manual-status-fix.md',
              'tools/install_normal_update.py', 'soundsight.sh']
    prefix = 'soundsight_normal_update/'
    if b'\r' in (ROOT/'soundsight.sh').read_bytes():
        raise ValueError('soundsight.sh must use LF line endings before packaging')
    with ZipFile(output, 'x', ZIP_DEFLATED) as z:
        for name in files: z.write(ROOT/name, prefix+'payload/'+name)
        z.write(ROOT/'tools/install_normal_update.py', prefix+'install.py')
        z.writestr(prefix+'FILES.json', json.dumps(files, indent=2)+'\n')
        z.write(ROOT/'document/pynq-normal-mode.md', prefix+'README.md')
    with ZipFile(output) as z:
        assert z.testzip() is None
        for name in files: assert z.read(prefix+'payload/'+name) == (ROOT/name).read_bytes()
    print('NORMAL_UPDATE=', output, 'PAYLOAD_FILES=', len(files), 'BIT_CHANGED=False')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_normal_update.zip')
    build(parser.parse_args().output)
