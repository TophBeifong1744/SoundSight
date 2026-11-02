#!/usr/bin/env python3
"""Navigator Zynq USB network candidate. Explicit start changes USB hardware only.

Run check first. No bit/HWH, BOOT.BIN, IMAGE.UB, reboot or motor operations.
Runtime overlays are deliberately never removed; normal reboot is recovery.
"""
import argparse
import gzip
import hashlib
import ipaddress
import json
import mmap
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
DT = Path('/sys/firmware/devicetree/base')
CF = Path('/sys/kernel/config')
STATE = Path('/run/soundsight-usb-network.json')
UDC_ROOT = Path('/sys/class/udc')
PLATFORM = Path('/sys/bus/platform/devices')
GADGET = CF / 'usb_gadget/soundsight'
USB0 = DT / 'amba/usb@e0002000'
SERVICE = 'soundsight-usb-network.service'
SERVICE_FILE = Path('/etc/systemd/system') / SERVICE
INSTALL = Path('/opt/soundsight-usb-network')


def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, timeout=20).stdout


def write(path, value):
    Path(path).write_text(str(value), encoding='ascii')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_for(predicate, message, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError(message)


def text_property(path):
    return Path(path).read_bytes().rstrip(b'\0').decode('ascii')


def read_mio():
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
                       offset=0xf8000000) as page:
            return {i: struct.unpack_from('<I', page, 0x700 + 4*i)[0]
                    for i in [9] + list(range(28, 40))}
    finally:
        os.close(fd)


def expected_mio():
    return {i: (0x600 if i == 9 else 0x205 if i in (29, 31, 36) else 0x204)
            for i in [9] + list(range(28, 40))}


def validate_ip(value):
    interface = ipaddress.IPv4Interface(value)
    require(interface.network.prefixlen == 24 and interface.ip.is_private
            and not interface.ip.is_loopback and not interface.ip.is_link_local
            and interface.ip not in (interface.network.network_address, interface.network.broadcast_address),
            'use a private, usable IPv4 address with /24 prefix')
    return interface


def preflight(board_ip):
    require(sys.platform == 'linux' and os.geteuid() == 0, 'run on PYNQ with sudo')
    meta = json.loads((HERE / 'package-manifest.json').read_text())
    require(os.uname().release == meta['kernel_release'], 'kernel release differs from collected board')
    require(digest('/lib/modules/' + os.uname().release + '/build/Module.symvers') == meta['symvers_sha256'],
            'kernel symbol table differs from collected board')
    with gzip.open('/proc/config.gz', 'rb') as stream:
        require(hashlib.sha256(stream.read()).hexdigest() == meta['config_sha256'], 'kernel config differs')
    for name, sha in meta['files'].items():
        path = HERE / name
        require(path.resolve().is_relative_to(HERE) if hasattr(path, 'is_relative_to') else
                os.path.commonpath([str(HERE), str(path.resolve())]) == str(HERE), 'invalid package path')
        require(digest(path) == sha, 'package checksum mismatch: ' + name)
    for name, sha in meta['boot_files'].items():
        require(digest(Path('/boot') / name) == sha, 'boot baseline changed: ' + name)
    require(not STATE.exists(), 'already started or partial state exists; use status / normal reboot')
    require(text_property(USB0 / 'status') == 'disabled', 'USB0 already enabled; do not change another setup')
    require(text_property(DT / 'amba/usb@e0003000/status') == 'disabled', 'unexpected USB1 setup')
    require(not list(UDC_ROOT.glob('*')), 'another USB device controller is already registered')
    mio = read_mio()
    require(mio == {i: 0x1601 if i == 9 else 0x1201 for i in mio},
            'MIO state differs from collected board: ' + str(mio))
    require(not GADGET.exists(), 'existing soundsight gadget; normal reboot before retry')
    for name in ('soundsight-usb-pins', 'soundsight-usb-controller'):
        require(not (CF / 'device-tree/overlays' / name).exists(), 'partial overlay exists; normal reboot before retry')
    for name in ('u_ether', 'usb_f_rndis'):
        require(not (Path('/sys/module') / name).exists(), 'another network gadget module is already loaded: ' + name)
    require(not list(CF.glob('usb_gadget/*')), 'another gadget configuration exists')
    interface = validate_ip(board_ip)
    for route in json.loads(run('ip', '-j', '-4', 'route', 'show', 'table', 'all')):
        dest = route.get('dst', 'default')
        if dest != 'default':
            require(not interface.network.overlaps(ipaddress.IPv4Network(dest, strict=False)),
                    'USB subnet conflicts with existing route ' + dest)
    # Verify SSH unit exists before doing any hardware configuration.
    run('systemctl', 'cat', 'ssh.service')
    print('CHECK_OK: matching kernel/boot inputs; USB0 disabled; MIO baseline matches; revision=' +
          meta.get('revision', 'legacy'), flush=True)
    return meta


def validate_symbol(symbol, expected_path):
    # Do not normalize with pathlib first: // is significant to Linux 5.4 OF.
    actual = (DT / '__symbols__' / symbol).read_bytes()
    require(actual == expected_path.encode('ascii') + b'\0',
            'invalid live symbol ' + symbol + ': ' + repr(actual))
    phandle = (DT / expected_path.lstrip('/') / 'phandle').read_bytes()
    require(len(phandle) == 4 and struct.unpack('>I', phandle)[0] not in (0, 0xffffffff),
            'invalid live phandle for ' + symbol)
    return phandle


def phy_driver_bound():
    expected = DT / 'amba/soundsight-usb-phy'
    return any((device / 'of_node').resolve() == expected and (device / 'driver').exists()
               for device in PLATFORM.iterdir())


def overlay(name, filename):
    directory = CF / 'device-tree/overlays' / name
    directory.mkdir()
    payload = (HERE / filename).read_bytes()
    (directory / 'dtbo').write_bytes(payload)
    # This kernel applies at configfs close and may hide the error behind an
    # "applied" status. Failed create clears its stored DTBO to zero bytes.
    require((directory / 'dtbo').read_bytes() == payload,
            'overlay rejected by kernel: ' + name + '; save dmesg and reboot')
    require((directory / 'status').read_text().strip() == 'applied', 'overlay not applied: ' + name)


def start(board_ip, confirmed):
    require(confirmed, 'power off, select P4 SLAVE (1-3 / 2-4), retain DC power, then pass --confirm-slave')
    preflight(board_ip)
    # Preserve a failure marker; subsequent calls must not re-pulse an active USB link.
    write(STATE, json.dumps({'stage': 'starting', 'board_ip': board_ip}))
    try:
        run('modprobe', 'libcomposite')
        run('insmod', str(HERE / 'modules/u_ether.ko'))
        run('insmod', str(HERE / 'modules/usb_f_rndis.ko'))
        if not os.path.ismount(str(CF)):
            run('mount', '-t', 'configfs', 'none', str(CF))
        require((CF / 'device-tree/overlays').is_dir(), 'DT configfs overlay support unavailable')
        overlay('soundsight-usb-pins', 'usb-pins-phy.dtbo')
        wait_for(phy_driver_bound,
                 'NOP PHY did not bind; collect dmesg and reboot')
        phy_phandle = validate_symbol('ss_usb_phy', '/amba/soundsight-usb-phy')
        pins_phandle = validate_symbol('ss_usb0_pins', '/amba/slcr@f8000000/pinctrl@700/soundsight-usb0-pins')
        require(read_mio()[9] == 0x600, 'RESET MIO pinctrl readback failed')
        chips = [p for p in Path('/sys/class/gpio').glob('gpiochip*')
                 if (p / 'device/of_node').resolve() == DT / 'amba/gpio@e000a000']
        require(len(chips) == 1, 'cannot identify Zynq GPIO controller')
        number = int((chips[0] / 'base').read_text()) + 9
        gpio = Path('/sys/class/gpio') / ('gpio' + str(number))
        require(not gpio.exists(), 'GPIO9 is already exported; do not take over another owner')
        write('/sys/class/gpio/export', number)
        wait_for(lambda: (gpio / 'direction').exists(), 'GPIO export timeout')
        write(gpio / 'active_low', 0)
        write(gpio / 'direction', 'low')
        require((gpio / 'value').read_text().strip() == '0', 'reset low readback failed')
        time.sleep(0.020)
        write(gpio / 'value', 1)
        require((gpio / 'value').read_text().strip() == '1', 'reset release readback failed')
        time.sleep(0.100)  # Board RESETB uses 1.5k/10uF RC, not a direct GPIO wire.
        overlay('soundsight-usb-controller', 'usb-controller.dtbo')
        for prop, expected in {'status': b'okay\0', 'dr_mode': b'peripheral\0',
                               'usb-phy': phy_phandle, 'pinctrl-0': pins_phandle}.items():
            require((USB0 / prop).read_bytes() == expected, 'USB0 live property mismatch: ' + prop)
        wait_for(lambda: bool(list(UDC_ROOT.glob('*'))), 'no UDC after USB0 enable; collect dmesg and reboot')
        udcs = list(UDC_ROOT.glob('*'))
        require(len(udcs) == 1 and 'e0002000' in str(udcs[0].resolve()), 'unexpected UDC')
        require(read_mio() == expected_mio(), 'USB MIO pinctrl readback failed')
        GADGET.mkdir()
        for name, value in {'idVendor': '0x1d6b', 'idProduct': '0x0104',
                            'bcdUSB': '0x0200', 'bcdDevice': '0x0100',
                            'bDeviceClass': '0xef', 'bDeviceSubClass': '0x02',
                            'bDeviceProtocol': '0x01'}.items():
            write(GADGET / name, value)
        serial_match = re.search(r'^Serial\s*:\s*(\S+)', Path('/proc/cpuinfo').read_text(), re.M)
        require(serial_match is not None, 'no CPU serial for stable network identity')
        serial = serial_match.group(1)
        mac = list(hashlib.sha256(('soundsight-usb-' + serial).encode()).digest()[:6])
        mac[0] = 0x02
        host = mac[:]
        host[-1] ^= 1
        strings = GADGET / 'strings/0x409'
        strings.mkdir()
        for name, value in {'manufacturer': 'SoundSight', 'product': 'USB Network', 'serialnumber': serial}.items():
            write(strings / name, value)
        config = GADGET / 'configs/c.1'
        config.mkdir()
        (config / 'strings/0x409').mkdir()
        write(config / 'strings/0x409/configuration', 'RNDIS')
        write(config / 'bmAttributes', '0xc0')  # Self-powered, retain board DC supply.
        write(config / 'MaxPower', '2')
        function = GADGET / 'functions/rndis.usb0'
        function.mkdir()
        for name, value in {'dev_addr': ':'.join('%02x' % b for b in mac),
                            'host_addr': ':'.join('%02x' % b for b in host),
                            'class': 'e0', 'subclass': '01', 'protocol': '03'}.items():
            write(function / name, value)
            if name in ('class', 'subclass', 'protocol'):
                require(int((function / name).read_text().strip(), 16) == int(value, 16),
                        'RNDIS descriptor readback failed: ' + name)
        write(function / 'os_desc/interface.rndis/compatible_id', 'RNDIS')
        write(function / 'os_desc/interface.rndis/sub_compatible_id', '5162001')
        write(GADGET / 'os_desc/use', 1)
        write(GADGET / 'os_desc/b_vendor_code', '0xcd')
        write(GADGET / 'os_desc/qw_sign', 'MSFT100')
        (config / 'rndis.usb0').symlink_to(function)
        (GADGET / 'os_desc/c.1').symlink_to(config)
        write(GADGET / 'UDC', udcs[0].name)
        interface = (function / 'ifname').read_text().strip()
        require(re.fullmatch(r'[A-Za-z0-9_.-]{1,15}', interface) is not None, 'invalid USB interface name')
        wait_for(lambda: (Path('/sys/class/net') / interface).exists(), 'USB network interface absent')
        run('ip', 'address', 'replace', board_ip, 'dev', interface)
        run('ip', 'link', 'set', interface, 'up')
        run('systemctl', 'start', 'ssh.service')
        write(STATE, json.dumps({'stage': 'ready', 'board_ip': board_ip, 'interface': interface,
                                 'udc': udcs[0].name, 'gpio': number}))
        print('USB_READY board=' + board_ip + ' interface=' + interface)
        print('Host enumeration, SSH and SFTP still require Windows verification.')
    except Exception as exc:
        print('USB_START_FAILED: ' + str(exc), file=sys.stderr)
        print('Keep UART connected. Save dmesg; normal reboot restores runtime changes. No online overlay removal.', file=sys.stderr)
        raise


def enable_service():
    require(os.geteuid() == 0, 'use sudo')
    state = json.loads(STATE.read_text())
    require(state['stage'] == 'ready', 'complete manual start and Windows tests first')
    require((UDC_ROOT / state['udc'] / 'state').read_text().strip() == 'configured',
            'Windows has not configured the USB device')
    unit = ('[Unit]\nDescription=SoundSight USB RNDIS network\n'
            'Requires=bootpy.service\n'
            'After=local-fs.target systemd-modules-load.service bootpy.service\nWants=ssh.service\n'
            '[Service]\nType=oneshot\nRemainAfterExit=yes\nTimeoutStartSec=30\n'
            'ExecStart=/usr/bin/python3 /opt/soundsight-usb-network/usb_network.py start --confirm-slave --board-ip=' +
            str(validate_ip(state['board_ip'])) + '\n[Install]\nWantedBy=multi-user.target\n')
    # Existing matching installations can resume after an interrupted systemctl
    # operation. Foreign/modified installations are never overwritten.
    manifest_bytes = (HERE / 'package-manifest.json').read_bytes()
    payload = json.loads(manifest_bytes)['files']
    def verify_install(directory):
        require((directory / 'package-manifest.json').read_bytes() == manifest_bytes,
                'existing installation belongs to another package')
        for name, sha in payload.items():
            require(digest(directory / name) == sha, 'installed payload differs: ' + name)
    if SERVICE_FILE.exists():
        require(SERVICE_FILE.read_text() == unit, 'existing service differs; do not overwrite')
    if INSTALL.exists():
        verify_install(INSTALL)
    else:
        with tempfile.TemporaryDirectory(prefix='.soundsight-usb-', dir=str(INSTALL.parent)) as temporary:
            staged = Path(temporary) / 'payload'
            shutil.copytree(str(HERE), str(staged), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            verify_install(staged)
            staged.rename(INSTALL)
    if not SERVICE_FILE.exists():
        created = False
        try:
            with SERVICE_FILE.open('x', encoding='ascii') as stream:
                created = True
                stream.write(unit)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            if created:
                SERVICE_FILE.unlink()
            raise
    run('systemctl', 'daemon-reload')
    try:
        run('systemctl', 'enable', SERVICE)
    except subprocess.SubprocessError:
        # The payload remains intact for retry, but failed enable must not leave
        # an intentionally unverified service scheduled for the next boot.
        run('systemctl', 'disable', SERVICE)
        raise
    print('ENABLED_FOR_NEXT_BOOT. No reboot performed. Keep P4 in SLAVE mode.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'start', 'status', 'enable-service', 'disable-service'])
    parser.add_argument('--board-ip', default='192.168.77.2/24')
    parser.add_argument('--confirm-slave', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            preflight(args.board_ip)
        elif args.action == 'start':
            start(args.board_ip, args.confirm_slave)
        elif args.action == 'status':
            print(STATE.read_text() if STATE.exists() else 'NOT_STARTED_THIS_BOOT')
            for udc in UDC_ROOT.glob('*'):
                print(udc.name, (udc / 'state').read_text().strip())
        elif args.action == 'enable-service':
            enable_service()
        else:
            require(os.geteuid() == 0, 'use sudo')
            run('systemctl', 'disable', SERVICE)
            print('DISABLED_FOR_NEXT_BOOT. Normal reboot restores runtime USB state.')
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
