"""SoundSight board helper. Motion defaults OFF; run --horizontal-motion is explicit."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from ps_client import Solver, MAGIC, ABI, SYS, STATUS, FAULT, DROP, ACT
from run_capture import address_from_hwh, single_owner
from run_smp import validate_cpus
from volume_gate import LEVEL_ABI, LEVEL_CAP
from angle_filter import validate_window

ROOT = Path(__file__).resolve().parents[2]
LOCK = '/tmp/soundsight-ps-owner.lock'
SETTINGS = 'settings.local.json'
REFERENCE = Path('/proc/device-tree/amba/slcr@f8000000/clkc@100/ps-clk-frequency')


def threshold(value):
    value = int(value)
    if not 1 <= value <= 0xffffff:
        raise ValueError('Level must be in 1..16777215 PCM counts')
    return value


def get_settings(root=ROOT):
    path = root/SETTINGS
    settings = dict(min_level=7000, window_frames=20, min_valid=12)
    if path.exists():
        settings.update(json.loads(path.read_text(encoding='utf-8')))
    if type(settings['min_level']) is not int:
        raise ValueError('Saved min_level must be an integer; use: level 7000')
    threshold(settings['min_level'])
    validate_window(settings['window_frames'], settings['min_valid'])
    return settings


def get_level(root=ROOT):
    return get_settings(root)['min_level']


def save_settings(settings, root):
    # 替换单个本地设置文件，永不改RTL、ABI或已保存日志。
    fd, temporary = tempfile.mkstemp(prefix='.level-', dir=str(root))
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as handle:
            json.dump(settings, handle)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, root/SETTINGS)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def set_level(value, root=ROOT):
    value = threshold(value)
    settings = get_settings(root)
    settings['min_level'] = value
    save_settings(settings, root)
    print('MIN_LEVEL=', value, 'APPLIES_TO=NEXT_RUN', flush=True)


def set_filter(window_frames, min_valid, root=ROOT):
    validate_window(window_frames, min_valid)
    settings = get_settings(root)
    settings.update(window_frames=window_frames, min_valid=min_valid)
    save_settings(settings, root)
    print('WINDOW_FRAMES=%d MIN_VALID=%d APPLIES_TO=NEXT_RUN' % (window_frames, min_valid), flush=True)


def selected_filter(args, root=ROOT):
    settings = get_settings(root)
    window = getattr(args, 'window_frames', None)
    minimum = getattr(args, 'min_valid', None)
    return validate_window(settings['window_frames'] if window is None else window,
                           settings['min_valid'] if minimum is None else minimum)


def hwh_check(root=ROOT):
    bit, hwh = root/'soundsight.bit', root/'soundsight.hwh'
    for path in (bit, hwh):
        if not path.is_file() or not path.stat().st_size:
            raise FileNotFoundError('Missing bit/HWH: '+str(path))
    tree = ET.parse(hwh)
    for instance, kind in (('ps_link', 'bd_ps_link'), ('compute', 'bd_clean_compute')):
        found = [m for m in tree.iter('MODULE') if m.get('INSTANCE') == instance and m.get('MODTYPE') == kind]
        if len(found) != 1:
            raise RuntimeError('HWH must contain one '+instance)
        params = {p.get('NAME'): p.get('VALUE') for p in found[0].iter('PARAMETER')}
        if params.get('LEVEL_ENABLE') != '1':
            raise RuntimeError('Volume bitstream required: LEVEL_ENABLE=1 in '+instance)
        if instance == 'ps_link':
            if params.get('ACTUATOR_BOUND') == '1':
                from horizontal_motion import check_hwh
                try:
                    check_hwh(hwh, automatic_motion=False)
                except ValueError as exc:
                    raise RuntimeError('ACTUATOR_BOUND=1 requires the complete horizontal configuration: '+str(exc)) from exc
            elif params.get('ACTUATOR_BOUND') != '0':
                raise RuntimeError('Unknown actuator binding in HWH')
    return address_from_hwh(hwh)


def clock_check(slcr, clocks, reference):
    if abs(reference-33.333333) >= .001:
        raise RuntimeError('Unexpected PS reference clock; expected 33.333333 MHz')
    if slcr.read(0x108) != 0x30000:
        raise RuntimeError('Unexpected IO PLL; preserve state and inspect platform')
    if ((slcr.read(0x170) >> 4) & 3) not in (0, 1):
        raise RuntimeError('Unexpected FCLK0 source; preserve state')
    # PYNQ 2.7在这张旧镜像中默认按50MHz计算；只修当前进程的参考值。
    clocks._instance._ref_clk_mhz = reference


def clock_ready(slcr, clocks):
    if slcr.read(0x170) != 0x400400 or abs(clocks.fclk0_mhz-100) > .01:
        raise RuntimeError('FCLK0 is not the validated 100 MHz setting; do not read PL')
    if slcr.read(0x240) & 3:
        raise RuntimeError('PL bus/cold reset is asserted; do not read PL')


def device_state(ip):
    # 身份/能力先检查，之后才读设备状态；本函数无写操作。
    if ip.read(MAGIC) != 0x5a5a2026 or ip.read(ABI) != LEVEL_ABI:
        raise RuntimeError('PL ID/volume ABI mismatch; no register writes performed')
    status = int(ip.read(STATUS))
    if not status & LEVEL_CAP:
        raise RuntimeError('PL real-level capability is missing')
    return dict(status=status, fault=int(ip.read(FAULT)), drops=int(ip.read(DROP)),
                sys=int(ip.read(SYS)), actuator=int(ip.read(ACT)))


def require_idle(state):
    if state['status'] & 3:
        raise RuntimeError('OLD_FRAMES: use sudo sh soundsight.sh drain; do not reload or clear slots')
    if state['sys'] & 1 or state['status'] & 0x8000 or state['actuator'] & 1:
        raise RuntimeError('DEVICE_ACTIVE: stop the current capture owner before continuing')
    if state['fault'] & ~0x40:
        raise RuntimeError('DEVICE_FAULT=0x%x: use status, preserve logs and investigate; no automatic clear' % state['fault'])


def prepare_hardware(overlay, slcr, clocks, mmio, reference, base, size):
    """供真实PYNQ及离线模型共用；首次下载，已有同一overlay则只检查。"""
    clock_check(slcr, clocks, reference)
    if overlay.is_loaded():
        # 重跑prepare不能清掉旧槽或异常，也不能在运行中改时钟。
        print('OVERLAY_ALREADY_LOADED=1 DOWNLOAD_SKIPPED=1', flush=True)
    else:
        if getattr(overlay.device, 'bitfile_name', ''):
            raise RuntimeError('Another overlay is registered; preserve its state before switching designs')
        if 0 not in overlay.clock_dict:
            raise RuntimeError('HWH has no FCLK0 configuration')
        overlay.clock_dict[0].update(enable=1, divisor0=4, divisor1=4)
        slcr.write(0x008, 0xDF0D)
        print('DOWNLOAD_BEGIN', flush=True)
        overlay.download()
        if not overlay.is_loaded():
            raise RuntimeError('Overlay download was not confirmed')
    clock_ready(slcr, clocks)
    state = device_state(mmio(base, size))
    print('LOADED=True FCLK0_CTRL=0x%x FCLK0_MHz=%.6f FPGA_RST_CTRL=0x%x' %
          (slcr.read(0x170), clocks.fclk0_mhz, slcr.read(0x240)), flush=True)
    print('DEVICE_STATE=', json.dumps(state, sort_keys=True), flush=True)
    require_idle(state)
    return state


def load_api(root=ROOT):
    # 在第一次import pynq之前设置环境，解决sudo过滤XILINX_XRT的问题。
    os.environ.setdefault('XILINX_XRT', '/usr')
    from pynq import Overlay, MMIO, Clocks
    ref = int.from_bytes(REFERENCE.read_bytes(), 'big')/1e6
    overlay = Overlay(str(root/'soundsight.bit'), download=False)
    return overlay, MMIO(0xF8000000, 0x300), Clocks, MMIO, ref


def offline_checks(root=ROOT):
    names = ['test_normal.py', 'test_volume_gate.py', 'test_serial_english.py', 'test_board_tools.py', 'test_filter_controls.py', 'test_manual_servo.py']
    if any(m.get('INSTANCE') == 'audio_capture' for m in ET.parse(root/'soundsight.hwh').iter('MODULE')):
        names.append('test_pcm_capture.py')
    for name in names:
        print('OFFLINE_TEST=', name, flush=True)
        subprocess.run([sys.executable, '-B', str(root/'software/tests'/name)], cwd=root, check=True)
    Solver(root/'software/ps/libss_solver.so')
    print('ARM_LIBRARY_LOADED=1', flush=True)


def inspect_loaded(root=ROOT):
    base, size = hwh_check(root)
    overlay, slcr, clocks, mmio, ref = load_api(root)
    if not overlay.is_loaded():
        raise RuntimeError('NOT_PREPARED: run sudo sh soundsight.sh prepare first')
    clock_check(slcr, clocks, ref)
    clock_ready(slcr, clocks)
    return device_state(mmio(base, size))


def run_arguments(args, root=ROOT):
    if getattr(args, 'manual_angle', None) is not None:
        raise ValueError('Use separate calibration: sudo sh soundsight.sh servo-angle DEG --seconds 5')
    level = threshold(args.min_level) if args.min_level is not None else get_level(root)
    window, minimum = selected_filter(args, root)
    normal = args.operation == 'normal'
    count = args.frames if args.frames is not None else (0 if normal and args.mode == 'real' else 1000 if args.mode == 'real' else 1)
    if count < (0 if normal else 1) or (args.mode != 'real' and count != 1):
        raise ValueError('Invalid frame count: normal real allows 0; debug needs >=1; BIST needs 1')
    # 微秒时间+PID并仍由底层open(x)兜底，不删除旧结果解决重名。
    name = '%s-%s-%s-%s%s' % (args.operation, args.mode,
                             datetime.now().strftime('%Y%m%d-%H%M%S-%f'), os.getpid(),
                             '.json' if normal else '.jsonl')
    out = root/'logs'/name
    command = ['--operation', args.operation, '--hwh', str(root/'soundsight.hwh'),
               '--output', str(out), '--mode', args.mode, '--frames', str(count),
               '--min-level', str(level), '--clear-faults', '0x40',
               '--window-frames', str(window), '--min-valid', str(minimum)]
    if not normal: command += ['--angle-filter']
    if getattr(args, 'horizontal_motion', False):
        if not normal or args.mode != 'real':
            raise ValueError('Horizontal motion is available only in normal real mode')
        from horizontal_motion import load_calibration, check_hwh
        path = root/'horizontal.local.json'
        config = load_calibration(path)
        check_hwh(root/'soundsight.hwh')
        manual = getattr(args, 'manual_angle', None)
        if manual is not None and not config['min_deg'] <= manual <= config['max_deg']:
            raise ValueError('Manual angle is outside configured mechanical limits')
        command += ['--horizontal-motion', '--motion-config', str(path)]
        if manual is not None: command += ['--manual-angle', str(manual)]
    elif getattr(args, 'manual_angle', None) is not None:
        raise ValueError('--manual-angle requires --horizontal-motion')
    return command, out, level


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare', help='Offline tests, load bitstream if needed, set clocks and verify readiness')
    sub.add_parser('pcm-check', help='Read PCM capabilities/status; no DMA start or capture')
    pcm = sub.add_parser('pcm', help='Bounded four-mic DMA test; always no motion')
    pcm.add_argument('--blocks', type=int, default=1, help='1..1024 packets of 512 samples; default 1')
    sub.add_parser('speaker-check', help='Verify speaker assets and read PCM interface; no capture or motion')
    speaker = sub.add_parser('speaker', help='Bounded real-microphone identity diagnostic; no motion')
    speaker.add_argument('--window', type=float, choices=[1.,1.5,2.], help='Identity audio window; saved default is 1.5 seconds')
    speaker.add_argument('--seconds', type=float, default=10., help='Capture duration, window+1 through 10 seconds')
    speaker_config = sub.add_parser('speaker-config', help='Show/save 1, 1.5 or 2 second identity window; no hardware')
    speaker_config.add_argument('window', type=float, nargs='?', choices=[1.,1.5,2.])
    speaker_import = sub.add_parser('speaker-import', help='Copy validated personal settings from an old directory; never overwrite')
    speaker_import.add_argument('source', type=Path)
    level = sub.add_parser('level', help='Show or save the level threshold for the next run')
    level.add_argument('value', type=int, nargs='?')
    filt = sub.add_parser('filter', help='Show or save window frames and minimum valid/inlier count')
    filt.add_argument('window_frames', type=int, nargs='?')
    filt.add_argument('min_valid', type=int, nargs='?')
    calibration = sub.add_parser('servo-config', help='Show or save front_deg direction min_deg max_deg; never moves hardware')
    calibration.add_argument('values', type=int, nargs='*')
    geometry = sub.add_parser('servo-geometry', help='Fixed-array pivot X Y in cm; optional known horizontal source range')
    geometry.add_argument('values', type=float, nargs='*')
    geometry.add_argument('--source-range-cm', type=float)
    manual = sub.add_parser('servo-angle', help='Audio-independent horizontal calibration; explicit finite duration')
    manual.add_argument('angle', type=int)
    manual.add_argument('--seconds', type=float, default=5.0)
    run = sub.add_parser('run', help='Start no-motion capture using the saved or overridden threshold')
    run.add_argument('operation', choices=['normal', 'debug'], nargs='?', default='normal')
    run.add_argument('--min-level', type=int)
    run.add_argument('--frames', type=int)
    run.add_argument('--window-frames', type=int)
    run.add_argument('--min-valid', type=int)
    run.add_argument('--mode', choices=['real', 'bist-pass', 'bist-reject'], default='real')
    run.add_argument('--horizontal-motion', action='store_true', help='Enable horizontal motion for this run only')
    run.add_argument('--manual-angle', type=int, help='Deprecated; use servo-angle for audio-independent calibration')
    sub.add_parser('status', help='Read loaded device state; never download or clear faults')
    sub.add_parser('drain', help='STOP and save existing slots to a new debug log; no new capture')
    args = p.parse_args(argv)
    try:
        if args.command == 'speaker-config':
            from speaker_settings import get_window, set_window
            with single_owner(LOCK):
                selected = get_window(ROOT) if args.window is None else set_window(ROOT,args.window)
            print('SPEAKER_WINDOW_SECONDS=%g APPLIES_TO=NEXT_RUN MOTION_COMMANDS=0'%selected,flush=True)
            return 0
        if args.command == 'speaker-import':
            from speaker_settings import import_settings
            with single_owner(LOCK):result=import_settings(args.source,ROOT)
            print('SPEAKER_SETTINGS_IMPORT='+json.dumps(result,sort_keys=True),flush=True)
            return 0
        if args.command == 'speaker-check':
            from speaker_settings import verify_assets
            verify_assets(ROOT/'software/ps/speaker_core')
            print('SPEAKER_ASSETS_OK=1 RECOGNITION_QUALIFIED=0',flush=True)
            from run_pcm import main as pcm_main
            return pcm_main(check_only=True,root=ROOT)
        if args.command == 'speaker':
            from live_speaker import main as speaker_main
            return speaker_main(ROOT,args.window,args.seconds)
        if args.command in ('pcm-check', 'pcm'):
            from run_pcm import main as pcm_main
            return pcm_main(check_only=args.command == 'pcm-check',
                            blocks=getattr(args, 'blocks', 1), root=ROOT)
        if args.command in ('servo-config', 'servo-geometry'):
            from horizontal_motion import validate_calibration, load_calibration, validate_geometry
            path = ROOT/'horizontal.local.json'
            if not args.values:
                if getattr(args, 'source_range_cm', None) is not None:
                    raise ValueError('Provide pivot X Y with --source-range-cm')
                print('HORIZONTAL_CONFIG=', load_calibration(path)); return 0
            if args.command == 'servo-config' and len(args.values) != 4:
                raise ValueError('Use: servo-config FRONT_DEG DIRECTION MIN_DEG MAX_DEG')
            if args.command == 'servo-geometry' and len(args.values) != 2:
                raise ValueError('Use: servo-geometry X_CM Y_CM [--source-range-cm R_CM]')
            with single_owner(LOCK):
                # Read/update under the same ownership lock. Changing servo
                # calibration must not silently erase the mounting geometry.
                if args.command == 'servo-config':
                    config = load_calibration(path) if path.exists() else {}
                    config.update(zip(('front_deg', 'direction', 'min_deg', 'max_deg'), args.values))
                else:
                    config = load_calibration(path)
                    config['geometry'] = validate_geometry(dict(pivot_x_cm=args.values[0],
                        pivot_y_cm=args.values[1], source_range_cm=args.source_range_cm))
                config = validate_calibration(config)
                # Parameters are not an enable switch; changes apply next run.
                fd, tmp = tempfile.mkstemp(prefix='.horizontal-', dir=str(ROOT))
                try:
                    with os.fdopen(fd, 'w', encoding='ascii') as handle:
                        json.dump(config, handle); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
                    os.chmod(tmp, 0o644); os.replace(tmp, path)
                finally:
                    if os.path.exists(tmp): os.unlink(tmp)
            print('HORIZONTAL_CONFIG=', config, 'SERVO=OFF APPLIES_TO=NEXT_RUN')
            finite_range = config.get('geometry', {}).get('source_range_cm') is not None
            print('AIM_MODE=', 'USER_SUPPLIED_RANGE' if finite_range else 'DIRECTION_ONLY_NO_PARALLAX_CORRECTION')
            return 0
        if args.command == 'level' and args.value is None:
            print('MIN_LEVEL=', get_level(), 'UNITS=MEAN_ABS_PCM_COUNTS'); return 0
        if args.command == 'filter':
            if args.window_frames is None and args.min_valid is None:
                settings = get_settings()
                print('WINDOW_FRAMES=%d MIN_VALID=%d' % (settings['window_frames'], settings['min_valid']))
                return 0
            if args.window_frames is None or args.min_valid is None:
                raise ValueError('Use: filter WINDOW_FRAMES MIN_VALID')
        if not hasattr(os, 'geteuid') or os.geteuid() != 0:
            raise RuntimeError('Use sudo sh soundsight.sh '+args.command)
        if args.command == 'level':
            with single_owner(LOCK): set_level(args.value)
            return 0
        if args.command == 'filter':
            with single_owner(LOCK): set_filter(args.window_frames, args.min_valid)
            return 0
        if platform.machine() not in ('armv7l', 'armv7'):
            raise RuntimeError('This board helper requires the Zynq ARMv7 PYNQ runtime')
        validate_cpus(0, 1)
        if args.command == 'servo-angle':
            from horizontal_motion import load_calibration
            from manual_servo import calibrate, validate_request
            config = load_calibration(ROOT/'horizontal.local.json')
            validate_request(config, args.angle, args.seconds)
            with single_owner(LOCK):
                base, size = hwh_check()
                overlay, slcr, clocks, mmio, ref = load_api()
                if not overlay.is_loaded():
                    raise RuntimeError('NOT_PREPARED: run prepare first')
                clock_check(slcr, clocks, ref); clock_ready(slcr, clocks)
                # Print before ARM, then keep the heartbeat free of serial/SD I/O.
                print('MANUAL_CALIBRATION TARGET=%ddeg SECONDS=%s AUDIO=OFF' %
                      (args.angle, args.seconds), flush=True)
                try:
                    result = calibrate(mmio(base, size), config, args.angle, args.seconds)
                except KeyboardInterrupt:
                    print('MANUAL_STOPPED_BY_USER', flush=True); return 0
            print('MANUAL_RESULT=', json.dumps(result, sort_keys=True), flush=True)
            return 0
        if args.command == 'prepare':
            with single_owner(LOCK):
                base, size = hwh_check()
                get_level()  # 本地配置坏了，先报错，不先下载。
                offline_checks()
                overlay, slcr, clocks, mmio, ref = load_api()
                prepare_hardware(overlay, slcr, clocks, mmio, ref, base, size)
            print('READY_FOR_DEBUG MIN_LEVEL=%d SERVO=OFF' % get_level(), flush=True)
            is_audio = any(m.get('INSTANCE') == 'audio_capture'
                           for m in ET.parse(ROOT/'soundsight.hwh').iter('MODULE'))
            print('NEXT: sudo sh soundsight.sh ' + ('pcm-check' if is_audio else 'run normal'), flush=True)
            return 0
        # 仅短暂持锁检查。实际采集随后使用原worker锁，竞争失败会在MMIO前拒绝。
        command = out = None
        if args.command == 'run': command, out, selected = run_arguments(args)
        with single_owner(LOCK):
            state = inspect_loaded()
            print('DEVICE_STATE=', json.dumps(state, sort_keys=True), flush=True)
            if args.command == 'status': return 0
            if args.command == 'run': require_idle(state)
        (ROOT/'logs').mkdir(exist_ok=True)
        if args.command == 'drain':
            window, minimum = selected_filter(args)
            out = ROOT/'logs'/('drain-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.jsonl')
            command = ['--operation', 'debug', '--hwh', str(ROOT/'soundsight.hwh'),
                       '--output', str(out), '--drain-existing', '--min-level', str(get_level()), '--angle-filter',
                       '--window-frames', str(window), '--min-valid', str(minimum)]
        else:
            print('MIN_LEVEL=', selected, 'SERVO=HORIZONTAL_REQUESTED' if args.horizontal_motion else 'SERVO=OFF', flush=True)
            print('WINDOW_FRAMES=%d MIN_VALID=%d' % selected_filter(args), flush=True)
        print('OUTPUT=', out, flush=True)
        # 不调用子进程外壳，Ctrl+C仍由原采集入口处理；不自动清其它故障。
        from run_device import main as capture
        return capture(command)
    except (Exception, KeyboardInterrupt) as exc:
        print('STOP:', str(exc).encode('ascii', 'backslashreplace').decode('ascii'), file=sys.stderr, flush=True)
        print('HELP: see document/pynq-board-helper.md; preserve logs on unexpected faults.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
