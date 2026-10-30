"""Build the software-only companion to the LAT1 FPGA update; no hardware action."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'software/tetra3d/linux/client_3d.py',
    'software/tests/test_latest_result.py',
    'document/ps-latest-result.md',
)


def main():
    output = ROOT/'release/output/soundsight_latest_result_update.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'soundsight_latest_result_update/'
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        z.write(ROOT/'tools/install_three_d_update.py', prefix+'install.py')
        for name in FILES:
            z.write(ROOT/name, prefix+'files/'+name)
        z.writestr(prefix+'README.txt',
            'Software increment for the existing SoundSight_PYNQ_3D_Speaker installation.\n'
            'See files/document/ps-latest-result.md. No bit/HWH or private profiles included.\n'
            'Install this companion before running the new LAT1 FPGA bitstream.\n'
            'Old bitstreams retain their old full-queue behavior.\n')
    with ZipFile(output) as z:
        assert z.testzip() is None
    print('PACKAGE='+str(output))
    print('BIT_HWH_INCLUDED=0 HARDWARE_ACTIONS=0')


if __name__ == '__main__':
    main()
