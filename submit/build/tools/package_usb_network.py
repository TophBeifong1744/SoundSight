#!/usr/bin/env python3
"""Package reviewed USB-only sources and built artifacts; no board operations."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'software/ps/usb_network'
BUILD = ROOT / 'software/build/usb-network'
INPUT = ROOT / 'document/evidence/usb-network-preflight-20261102/board-inputs.zip'


def main():
    report = json.loads((BUILD / 'checks.json').read_text())
    assert report['status'].startswith('OFFLINE_CHECKS_PASS')
    files = {}
    for path in SOURCE.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(SOURCE).as_posix()] = path.read_bytes()
    for name in ('u_ether.ko', 'usb_f_rndis.ko'):
        data = (BUILD / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == next(m['sha256'] for m in report['modules'] if m['name'] == name)
        files['modules/' + name] = data
    for name in ('usb-pins-phy.dtbo', 'usb-controller.dtbo'):
        files[name] = (BUILD / name).read_bytes()
    files['README.md'] = (ROOT / 'document/pynq-usb-network.md').read_bytes()
    files['offline-checks.json'] = (BUILD / 'checks.json').read_bytes()
    with zipfile.ZipFile(INPUT) as archive:
        manifest = {'revision': 'usb-boot-order-v3', 'kernel_release': '5.4.0-xilinx-v2020.2',
                    'config_sha256': hashlib.sha256(archive.read('kernel/running.config')).hexdigest(),
                    'symvers_sha256': hashlib.sha256(archive.read('kernel-build/Module.symvers')).hexdigest(),
                    'boot_files': {name: hashlib.sha256(archive.read('boot/' + name)).hexdigest()
                                   for name in ('BOOT.BIN', 'BOOT.SCR', 'IMAGE.UB')},
                    'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
                    'status': 'BOARD_CONFIRMED_V2_WITH_BOOTPY_DROPIN; V3_FRESH_INSTALL_NOT_TESTED',
                    'board_evidence': 'document/evidence/usb-network-preflight-20261102/board-success.md',
                    'application_bit_hwh': 'current B-modified files preserved; not collected or verified'}
    files['package-manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = ROOT / 'release/output/soundsight_usb_network.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            assert not name.lower().endswith(('.bit', '.hwh', 'image.ub', 'boot.bin', 'boot.scr'))
            archive.writestr('SoundSight_USB/' + name, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, sha in manifest['files'].items():
            assert hashlib.sha256(archive.read('SoundSight_USB/' + name)).hexdigest() == sha
    print(json.dumps({'output': str(output), 'bytes': output.stat().st_size,
                      'files': len(files), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
