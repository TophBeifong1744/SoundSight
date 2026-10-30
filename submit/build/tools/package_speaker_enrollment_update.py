"""Small software-only update for an already installed 3-D speaker application."""
import ast
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'soundsight-3d.sh',
    'software/ps/run_pcm.py',
    'software/ps/speaker_targets.py',
    'software/ps/speaker_enrollment.py',
    'software/ps/speaker_follow_setup.py',
    'software/ps/live_speaker_follow.py',
    'software/ps/speaker_permission.py',
    'software/ps/speaker_process.py',
    'software/tetra3d/linux/client_3d.py',
    'software/tests/test_speaker_follow.py',
    'software/tests/test_latest_result.py',
    'document/pynq-speaker-ttl-update.md',
    'software/tetra3d/linux/board_3d.py',
    'software/tetra3d/linux/speaker_runtime_3d.py',
    'software/tests/test_speaker_enrollment.py',
    'software/tests/test_speaker_display.py',
    'document/pynq-speaker-enrollment.md',
    'document/pynq-speaker-3d.md',
    'document/evidence/speaker-enrollment-20261029/board-result.md',
    'software/ps/speaker_statistics.py',
    'software/tests/test_speaker_statistics.py',
    'document/pynq-speaker-statistics.md',
)


def main():
    out = ROOT/'release/output/soundsight_enrollment_update.zip'
    prefix = 'soundsight_enrollment_update/'
    contents = {prefix+'files/'+n: (ROOT/n).read_bytes() for n in FILES}
    contents[prefix+'install.py'] = (ROOT/'tools/install_three_d_update.py').read_bytes()
    contents[prefix+'README.md'] = (ROOT/'document/pynq-speaker-statistics.md').read_bytes()
    for name, data in contents.items():
        if name.endswith('.py'): ast.parse(data.decode('utf-8-sig'), feature_version=(3, 8))
        if name.endswith('.sh') and b'\r' in data: raise ValueError('Shell must use LF')
    with ZipFile(out, 'w', ZIP_DEFLATED) as z:
        for name, data in contents.items(): z.writestr(name, data)
    with ZipFile(out) as z:
        assert z.testzip() is None
        for name, data in contents.items(): assert z.read(name) == data
    print('ENROLLMENT_UPDATE='+str(out)+' FILES='+str(len(FILES))+' HARDWARE_ACTIONS=0')


if __name__ == '__main__':
    main()
