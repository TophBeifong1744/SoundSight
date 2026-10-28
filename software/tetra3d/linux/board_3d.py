"""PYNQ 3-D helper. Explicit modes, default no motion, one device owner."""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'software/ps'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import board_tools
from angle_filter import validate_window
from run_capture import address_from_hwh, single_owner
from solver_3d import Solver3D, read_json
from motion_3d import DualAxis, STATE, MASKS, calibration, selected_calibration, pointing_geometry, manual

LOCK = '/tmp/soundsight-ps-owner.lock'


def check_hwh(path):
    """Validate metadata before touching extension addresses on older hardware."""
    base, size = address_from_hwh(path, 'ps_link')
    rows = [m for m in ET.parse(path).iter('MODULE') if m.get('INSTANCE') == 'ps_link']
    if len(rows) != 1:
        raise ValueError('Expected exactly one ps_link module')
    params = {p.get('NAME'): p.get('VALUE') for p in rows[0].iter('PARAMETER')}
    for key, expected in (('DUAL_AXIS_ENABLE', 1), ('AUDIO_ENABLE', 1),
                          ('LEVEL_ENABLE', 1), ('ACTUATOR_BOUND', 1),
                          ('CLK_FREQ_HZ', 61440000), ('SERVO_MAX', 360)):
        if key not in params or int(params[key], 0) != expected:
            raise ValueError('HWH does not describe the new dual-axis candidate: '+key)
    return base, size


def load_config(root=ROOT):
    path = root/'servo3d.local.json'
    return read_json(path.read_text(encoding='utf-8')) if path.exists() else {}


def save_config(config, root=ROOT):
    # Local user calibration is never replaced by the software update package.
    fd, name = tempfile.mkstemp(prefix='.servo3d-', suffix='.tmp', dir=str(root))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(config, out, indent=2, allow_nan=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, str(root/'servo3d.local.json'))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def offline(root=ROOT):
    # A fresh 3-D directory also needs the legacy library used by startup
    # checks and raw-frame recovery. Never depend on a .so in an older app.
    subprocess.run(['sh', str(root/'software/ps/build_solver.sh')], check=True)
    board_tools.Solver(root/'software/ps/libss_solver.so')
    subprocess.run(['sh', str(root/'software/tetra3d/linux/build_solver_3d.sh')], check=True)
    geometry = read_json((root/'software/tetra3d/core/tetra40-nominal.json').read_text(encoding='utf-8'))
    Solver3D(root/'software/tetra3d/linux/libss_solver_3d.so', geometry)
    subprocess.run([sys.executable, '-B', str(root/'software/tetra3d/tests/test_online_3d.py')], check=True)
    print('THREE_D_OFFLINE_OK=1 HARDWARE_ACTIONS=0', flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('check', help='Native solver build and offline tests; no hardware')
    sub.add_parser('prepare', help='Offline checks, then explicit bit load and clock preparation')
    sub.add_parser('status', help='Read state of already prepared hardware')
    sub.add_parser('drain', help='STOP and save existing raw frames with the legacy recovery helper; no 3D/motion')
    sub.add_parser('speaker-check', help='Validate models, selected enrollment and trial settings; no hardware')
    speaker_cfg = sub.add_parser('speaker-config', help='Trial score gate; null/missing threshold denies permission')
    speaker_cfg.add_argument('threshold', nargs='?', type=float)
    speaker_cfg.add_argument('--ttl', type=float)
    speaker_cfg.add_argument('--disable', action='store_true')
    speaker_import = sub.add_parser('speaker-import', help='Preserve/import real target from previous application; no enrollment')
    speaker_import.add_argument('source', type=Path)
    level = sub.add_parser('level')
    level.add_argument('value', nargs='?', type=int)
    filt = sub.add_parser('filter')
    filt.add_argument('window_frames', nargs='?', type=int)
    filt.add_argument('min_valid', nargs='?', type=int)
    cal = sub.add_parser('servo-config', help='Axis FRONT DIRECTION MIN MAX; saves only, no movement')
    cal.add_argument('axis', choices=['horizontal', 'vertical'])
    cal.add_argument('values', nargs='*', type=int)
    geom = sub.add_parser('servo-geometry', help='Pivot XYZ centimetres; optional KNOWN source range')
    geom.add_argument('values', nargs='*', type=float)
    geom.add_argument('--source-range-cm', type=float)
    man = sub.add_parser('manual', help='Explicit sound-independent finite motion; Ctrl+C revokes')
    man.add_argument('--horizontal', type=int)
    man.add_argument('--vertical', type=int)
    man.add_argument('--seconds', type=float, default=3.)
    for name, help_text in (('run', 'Angle-only measurement; --axes automatically uses speaker-gated following'),
                            ('speaker', 'Combined voiceprint and 3-D; --axes explicitly enables gated following')):
        run = sub.add_parser(name, help=help_text)
        run.add_argument('--axes', choices=list(MASKS), default='off')
        run.add_argument('--frames', type=int, default=0)
        run.add_argument('--debug', action='store_true', help='Keep at most 1000 frames in RAM; save after STOP')
        run.add_argument('--geometry', type=Path, default=ROOT/'software/tetra3d/core/tetra40-nominal.json')
        run.add_argument('--min-level', type=int)
        run.add_argument('--window-frames', type=int)
        run.add_argument('--min-valid', type=int)
        if name == 'speaker':
            run.add_argument('--seconds', type=float, default=0., help='0 until Ctrl+C; bounded run otherwise')
    return p


def run_options(args, root=ROOT):
    # Existing users may type run --axes. Route that automatic movement through
    # the same speaker gate; only manual calibration is sound-independent.
    if args.command == 'run' and args.axes != 'off':
        args.command, args.seconds = 'speaker', 0.
    if args.frames < 0 or args.debug and not 1 <= args.frames <= 1000:
        raise ValueError('Normal: frames>=0; debug: explicitly select 1..1000 frames')
    settings = board_tools.get_settings(root)
    args.min_level = board_tools.threshold(args.min_level if args.min_level is not None else settings['min_level'])
    args.window_frames, args.min_valid = validate_window(
        args.window_frames if args.window_frames is not None else settings['window_frames'],
        args.min_valid if args.min_valid is not None else settings['min_valid'])
    args.geometry = read_json(args.geometry.read_text(encoding='utf-8'))
    args.library = str(root/'software/tetra3d/linux/libss_solver_3d.so')
    Solver3D(args.library, args.geometry)  # Validate geometry/library before any write.
    args.calibration = load_config(root)
    args.axis_mask = MASKS[args.axes]
    if args.axis_mask:
        selected_calibration(args.calibration, args.axis_mask)
        pointing_geometry(args.calibration.get('pointing', {}))
    args.motion_requested = bool(args.axis_mask)
    args.hwh, args.ip = str(root/'soundsight.hwh'), 'ps_link'
    args.mode, args.clear_faults = 'real', 0x40
    args.host_cpu, args.worker_cpu, args.lock_file = 0, 1, LOCK
    args.output = str(root/'logs'/('three-d-%s-%s.json' % (
        datetime.now().strftime('%Y%m%d-%H%M%S-%f'), os.getpid())))
    return args


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command in ('speaker-config', 'speaker-import', 'speaker-check'):
            from speaker_follow_setup import configure, import_profile, check
            with single_owner(LOCK):
                if args.command == 'speaker-config':
                    result = configure(ROOT, args.threshold, args.ttl, args.disable)
                elif args.command == 'speaker-import':
                    result = import_profile(ROOT, args.source)
                else:
                    result = check(ROOT)
            print('SPEAKER_CONFIG='+json.dumps(result, allow_nan=False)+' HARDWARE_ACTIONS=0 APPLIES_TO_NEXT_SESSION=1', flush=True)
            return 0
        if args.command == 'check':
            offline()
            return 0
        if args.command in ('level', 'filter'):
            command = [args.command]
            values = [args.value] if args.command == 'level' else [args.window_frames, args.min_valid]
            command += [str(v) for v in values if v is not None]
            return board_tools.main(command)
        if args.command in ('servo-config', 'servo-geometry'):
            with single_owner(LOCK):
                config = load_config()
                if args.command == 'servo-config':
                    if args.values:
                        if len(args.values) != 4:
                            raise ValueError('Use servo-config AXIS FRONT DIRECTION MIN MAX')
                        config[args.axis] = calibration(dict(zip(
                            ('front_deg', 'direction', 'min_deg', 'max_deg'), args.values)),
                            360 if args.axis == 'horizontal' else 220)
                        save_config(config)
                    print('SERVO_CONFIG='+json.dumps(config.get(args.axis)), flush=True)
                else:
                    if args.values:
                        if len(args.values) != 3:
                            raise ValueError('Provide pivot X Y Z in centimetres')
                        config['pointing'] = pointing_geometry(dict(
                            zip(('pivot_x_cm', 'pivot_y_cm', 'pivot_z_cm'), args.values),
                            source_range_cm=args.source_range_cm))
                        save_config(config)
                    elif args.source_range_cm is not None:
                        raise ValueError('Provide XYZ with the known source range')
                    print('POINTING_GEOMETRY='+json.dumps(config.get('pointing', pointing_geometry({}))), flush=True)
            print('HARDWARE_ACTIONS=0 APPLIES_TO=NEXT_RUN')
            return 0
        check_hwh(ROOT/'soundsight.hwh')
        if args.command == 'prepare':
            offline()
            result = board_tools.main(['prepare'])
            if result:
                return result
            args.command = 'status'
        if args.command == 'drain':
            # Raw preservation only: this helper's old planar result is not 3-D evidence.
            return board_tools.main(['drain'])
        if args.command in ('status', 'manual'):
            with single_owner(LOCK):
                state = board_tools.inspect_loaded()
                base, size = check_hwh(ROOT/'soundsight.hwh')
                from pynq import MMIO
                ip = MMIO(base, size)
                axes = DualAxis(ip)
                axes.identify()
                if args.command == 'status':
                    state['dual_axis'] = axes.read(STATE)
                    print('DEVICE_STATE='+json.dumps(state), flush=True)
                    return 0
                targets = {name: getattr(args, name) for name in ('horizontal', 'vertical')
                           if getattr(args, name) is not None}
                print('MANUAL_RESULT='+json.dumps(manual(ip, load_config(), targets, args.seconds)), flush=True)
                return 0
        if args.command == 'speaker' and (not math.isfinite(args.seconds) or args.seconds < 0):
            raise ValueError('Speaker duration must be finite and nonnegative')
        args = run_options(args)
        if args.command == 'speaker':
            from speaker_runtime_3d import run as run_speaker
            return run_speaker(args, ROOT)
        # Read-only preflight under the same lock; worker re-identifies and owns all writes.
        with single_owner(LOCK):
            board_tools.inspect_loaded()
        (ROOT/'logs').mkdir(exist_ok=True)
        print('AXES=%s MIN_LEVEL=%s WINDOW=%s MIN_VALID=%s GEOMETRY=%s CHANNEL_ORDER_UNVERIFIED_UNTIL_MEASURED' %
              (args.axes, args.min_level, args.window_frames, args.min_valid, args.geometry['source_id']), flush=True)
        from runtime_3d import run
        return run(args)
    except (Exception, KeyboardInterrupt) as exc:
        print('STOP: %s: %s' % (type(exc).__name__, exc), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
