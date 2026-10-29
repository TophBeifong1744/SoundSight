"""Package the user's completed 3-D build and its standalone PYNQ software.

Read external hardware files only. No Vivado, board actions, voice assets,
personal settings, or precompiled host/ARM libraries are included.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from package_three_d_update import selected

ROOT = Path(__file__).resolve().parents[1]
BOARD = 'SoundSight_PYNQ_3D'
EVIDENCE = ROOT/'project/reports/ps_3d/w16'


def payload():
    names = set(selected())
    # Explicit dependency closure for startup, measurement, and frame recovery.
    # B's voiceprint runtime/assets remain in its own application directory.
    modules = ('angle_filter board_tools horizontal_motion manual_servo pcm_capture '
               'ps_client ram_queue recover_ram run_buffered run_capture run_device '
               'run_normal run_pcm run_smp volume_gate').split()
    names.update('software/ps/'+n+'.py' for n in modules)
    tests = ('test_normal test_volume_gate test_serial_english test_board_tools '
             'test_filter_controls test_manual_servo test_pcm_capture '
             'test_online_angle_filter').split()
    names.update('software/tests/'+n+'.py' for n in tests)
    names.update(['software/ps/build_solver.sh', 'software/ps/ss_solver_bridge.c',
                  'tools/install_normal_update.py', 'soundsight.sh', 'LICENSE',
                  'document/pynq-three-d-sd.md', 'document/pynq-board-helper.md',
                  'document/pynq-w16-update.md'])
    return {n: ROOT/n for n in sorted(names)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_pynq_3d.zip')
    args = p.parse_args()
    receipt = json.loads((EVIDENCE/'user-build-receipt.json').read_text('utf-8'))
    review = json.loads((EVIDENCE/'hardware-review.json').read_text('utf-8'))
    if review['result'] != 'SCOPED_PASS':
        raise ValueError('Read the current hardware review before board packaging')
    files = payload()
    for kind in ('bit', 'hwh'):
        record = receipt['artifacts'][kind]
        path = Path(record['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Hardware changed after receipt: '+kind)
        files['soundsight.'+kind] = path
    files['reports/hardware-review.json'] = EVIDENCE/'hardware-review.json'
    for name in ('audit_status.txt', 'timing_summary.rpt', 'cdc.rpt',
                 'servo_pwm_max.rpt', 'servo_vertical_pwm_max.rpt'):
        files['reports/'+name] = EVIDENCE/'supplemental'/name
    for name, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        if name.endswith('.py'):
            ast.parse(path.read_text('utf-8-sig'), feature_version=(3, 8))
        if name.endswith('.sh') and b'\r' in path.read_bytes():
            raise ValueError('Shell entry must have LF newlines: '+name)
    source = dict(board_directory=BOARD, hardware=receipt['artifacts'],
                  hardware_review=review['result'], default_motion=False,
                  software='Current repository working tree; source, not host binaries',
                  arm_3d='NOT_RUN', physical_channel_order='USER_CONFIRMATION_PENDING',
                  mechanical_calibration='NOT_RUN', speaker_assets='NOT_INCLUDED',
                  xsa='Not needed by this PYNQ Overlay application; not included')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, 'w', ZIP_DEFLATED) as z:
        for name, path in sorted(files.items()):
            z.write(path, BOARD+'/'+name)
        z.writestr(BOARD+'/SOURCE.json', json.dumps(source, ensure_ascii=False, indent=2)+'\n')
        z.writestr(BOARD+'/README.md', '# SoundSight PYNQ 3D\n\n'
                   '先阅读 [SD卡安装与首次运行](document/pynq-three-d-sd.md)。\n\n'
                   'Independent directory; matching bit/HWH included. Motion defaults OFF.\n'
                   'No private voiceprint assets or existing user settings included.\n')
        z.writestr(BOARD+'/FILES.txt', '\n'.join(sorted(files))+'\nSOURCE.json\nREADME.md\nFILES.txt\n')
    with ZipFile(args.output) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(files)+3
        for name, path in files.items():
            assert z.read(BOARD+'/'+name) == path.read_bytes(), name
    print('THREE_D_BOARD_PACKAGE=%s FILES=%d BYTES=%d HARDWARE_ACTIONS=0' %
          (args.output, len(files)+3, args.output.stat().st_size))


if __name__ == '__main__':
    main()
