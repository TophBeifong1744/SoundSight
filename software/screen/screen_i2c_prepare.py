"""Explicit S2 Linux I2C check/apply; never downloads a bitstream or resets PS."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import time

from linux_i2c import DT_ROOT, TARGET, LinuxI2C, node_details, read_property


@contextmanager
def exclusive(path):
    import fcntl
    with open(path, 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def snapshot():
    # 错误时仍保存真实运行 DT/sysfs 线索，不发起 I2C 探测事务。
    node = DT_ROOT/TARGET.lstrip('/')
    result = dict(kernel=platform.release(), machine=platform.machine(), target=TARGET,
                  dt_present=node.is_dir(), configfs_overlay_dir=Path('/sys/kernel/config/device-tree/overlays').is_dir(),
                  i2c_dev_class=Path('/sys/class/i2c-dev').is_dir(),
                  kernel_components={name: Path(path).exists() for name, path in
                                     (('i2c_dev_module', '/sys/module/i2c_dev'),
                                      ('i2c_cadence_module', '/sys/module/i2c_cadence'),
                                      ('cadence_platform_driver', '/sys/bus/platform/drivers/cdns-i2c'))},
                  dt_properties={}, adapters=[], platforms=[])
    if node.is_dir():
        for name in ('reg', 'compatible', 'status', 'clocks', 'clock-frequency', 'interrupts', 'pinctrl-names', 'pinctrl-0', 'resets'):
            value = read_property(node, name)
            result['dt_properties'][name] = value.hex()
    for adapter in Path('/sys/class/i2c-adapter').glob('i2c-*'):
        result['adapters'].append(dict(path=str(adapter.resolve()), name=read_property(adapter, 'name').decode(errors='replace').strip()))
    for device in Path('/sys/bus/platform/devices').glob('*'):
        if 'e0004' in device.name:
            result['platforms'].append(dict(path=str(device.resolve()),
                                           driver=str((device/'driver').resolve()) if (device/'driver').exists() else None))
    return result


def check_bus():
    bus = LinuxI2C()
    try:
        return dict(adapter=bus.details, abi=bus.abi, transfer_performed=False,
                    timeout='Cadence kernel driver default; adapter timeout/retries unchanged')
    finally:
        bus.close()


def safe_snapshot():
    try:
        return snapshot()
    except Exception as exc:
        return dict(snapshot_error='%s: %s' % (type(exc).__name__, exc))


def apply_overlay(root):
    info = node_details()
    if info['status'] in ('okay', 'ok'):
        if info['clock_frequency'] != [100000]:
            raise RuntimeError('PS_I2C_ENABLED_WRONG_FREQUENCY: no automatic rebind or live property overwrite')
        return dict(action='already_enabled', **check_bus())
    if info['status'] != 'disabled':
        raise RuntimeError('PS_I2C_UNKNOWN_DT_STATUS: '+info['status'])
    node = Path(info['node'])
    bound = [str(p) for p in Path('/sys/bus/platform/devices').glob('*')
             if (p/'of_node').exists() and (p/'of_node').resolve() == node]
    if bound:
        raise RuntimeError('PS_I2C_DISABLED_BUT_PLATFORM_PRESENT: '+str(bound))
    if not Path('/sys/kernel/config/device-tree/overlays').is_dir():
        raise RuntimeError('PS_I2C_CONFIGFS_UNAVAILABLE: no mount/install attempted')
    blob = root/'software/screen/ps_i2c0_enable.dtbo'
    if not blob.is_file():
        raise RuntimeError('PS_I2C_DTBO_MISSING: install the matched precompiled package; no downloads')
    from pynq.devicetree import DeviceTreeSegment
    segment = DeviceTreeSegment(str(blob))
    if Path(segment.sysfs_dir).exists():
        raise RuntimeError('PS_I2C_OVERLAY_PATH_ALREADY_EXISTS: preserve it and inspect, no overwrite/remove')
    # 先持有采集与 IIC 所有权；设备树只改既有节点的 status 和 clock-frequency。
    with exclusive('/tmp/soundsight-ps-owner.lock'), exclusive('/tmp/soundsight-ps-i2c0-owner.lock'):
        segment.insert()
    # 给内核/udev 有限时间建立 adapter 与字符设备；此处只轮询 sysfs，不发触摸事务。
    last = None
    until = time.monotonic() + 3.
    while time.monotonic() < until:
        try:
            return dict(action='overlay_applied', overlay=segment.sysfs_dir, **check_bus())
        except (OSError, RuntimeError, ValueError) as exc:
            last = exc
            time.sleep(.1)
    raise RuntimeError('PS_I2C_OVERLAY_APPLIED_BUT_NOT_READY: %s; overlay retained, no rollback/unbind' % last)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'apply'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    report = dict(command=args.command, before=safe_snapshot(), success=False)
    root = args.root.resolve()
    result = 1
    try:
        if os.name != 'posix':
            raise RuntimeError('Linux/PYNQ required')
        from hardware import open_overlay
        with exclusive('/tmp/soundsight-screen-owner.lock'):
            # 检查安装/重启/已加载 S2 身份及原 PS 空闲状态，不 prepare 或下载位流。
            open_overlay(root)
            report['result'] = apply_overlay(root) if args.command == 'apply' else check_bus()
        report['success'], result = True, 0
    except Exception as exc:
        report['error'] = '%s: %s' % (type(exc).__name__, exc)
    finally:
        report['after'] = safe_snapshot()
        try:
            logs = root/'logs'
            logs.mkdir(exist_ok=True)
            path = logs/('screen-i2c-%s-%s-%d.json' % (args.command, datetime.now().strftime('%Y%m%d-%H%M%S-%f'), os.getpid()))
            with path.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2, ensure_ascii=True)
                stream.write('\n')
            report['saved_report'] = str(path)
        except OSError as exc:
            report['save_error'] = str(exc)
            result = 1
        print('SCREEN_I2C_SETUP='+json.dumps(report, ensure_ascii=True, sort_keys=True), flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
