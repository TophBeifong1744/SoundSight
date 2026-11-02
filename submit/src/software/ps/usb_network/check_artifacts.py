#!/usr/bin/env python3
"""Offline CRC, ELF symbol-version and DT overlay checks. Never loads modules."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def fdt_properties(data):
    header = struct.unpack_from('>10I', data)
    assert header[0] == 0xd00dfeed and header[1] <= len(data)
    strings = data[header[3]:header[3]+header[8]]
    pos, stack, result = header[2], [], {}
    while True:
        token = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if token == 1:
            end = data.index(b'\0', pos)
            stack.append(data[pos:end].decode())
            pos = (end + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, off = struct.unpack_from('>2I', data, pos)
            pos += 8
            name = strings[off:strings.index(b'\0', off)].decode()
            result[('/' + '/'.join(stack[1:])).rstrip('/') + '/' + name] = data[pos:pos+size]
            pos = (pos + size + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            return result
        else:
            raise ValueError('invalid FDT token')


def elf_sections(data):
    assert data[:6] == b'\x7fELF\x01\x01', 'expected ELF32 little endian'
    assert struct.unpack_from('<H', data, 18)[0] == 40, 'expected ARM machine'
    assert struct.unpack_from('<H', data, 16)[0] == 1, 'expected relocatable module'
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count, names = struct.unpack_from('<3H', data, 46)
    sections = [struct.unpack_from('<10I', data, offset + i*size) for i in range(count)]
    section = sections[names]
    strings = data[section[4]:section[4]+section[5]]
    return {strings[s[0]:strings.index(b'\0', s[0])].decode(): data[s[4]:s[4]+s[5]]
            for s in sections}


def symbol_map(text):
    return {line.split()[1]: int(line.split()[0], 16)
            for line in text.splitlines() if line.strip()}


def check_kernel54_symbols(properties):
    """Reproduce this kernel's literal target+tail, unlike libfdt normalization."""
    exports = {}
    for key, value in properties.items():
        if not key.startswith('/__symbols__/'):
            continue
        fragment, tail = value.rstrip(b'\0').decode().split('/__overlay__', 1)
        target = properties[fragment + '/target-path'].rstrip(b'\0').decode()
        path = target + tail
        if '//' in path:
            raise ValueError('Linux 5.4 cannot resolve exported path: ' + path)
        exports[key.rsplit('/', 1)[1]] = path
    return exports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('artifacts', type=Path)
    args = parser.parse_args()
    output = args.artifacts
    with zipfile.ZipFile(args.inputs) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('manifest.json'))
        for item in manifest['files']:
            data = archive.read(item['path'])
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
        symbols = symbol_map(archive.read('kernel-build/Module.symvers').decode())
        symbols.update(symbol_map((output / 'new-Module.symvers').read_text()))
        original_config = archive.read('kernel/running.config').decode().splitlines()
        built_config = (output / 'built.config').read_text().splitlines()
        semantic = lambda lines: {l for l in lines if l.startswith('CONFIG_')
                                 and not l.startswith(('CONFIG_CC_VERSION_TEXT=', 'CONFIG_GCC_VERSION='))}
        assert semantic(original_config) == semantic(built_config), 'target kernel config changed'
        fit = fdt_properties(archive.read('boot/IMAGE.UB'))
        kernel = fit['/configurations/conf@1/kernel'].rstrip(b'\0').decode()
        dtb = fit['/configurations/conf@1/fdt'].rstrip(b'\0').decode()
        checked_hashes = []
        for name in (kernel, dtb):
            base = '/images/' + name
            blob = fit[base + '/data']
            for path, value in fit.items():
                if path.startswith(base + '/') and path.endswith('/algo'):
                    algo = value.rstrip(b'\0').decode()
                    expected = fit[path[:-4] + 'value']
                    if algo == 'sha1':
                        actual = hashlib.sha1(blob).digest()
                    elif algo == 'sha256':
                        actual = hashlib.sha256(blob).digest()
                    else:
                        import zlib
                        assert algo == 'crc32', algo
                        actual = struct.pack('>I', zlib.crc32(blob) & 0xffffffff)
                    assert actual == expected, path
                    checked_hashes.append(path)
        modules = []
        for name in ('u_ether.ko', 'usb_f_rndis.ko'):
            data = (output / name).read_bytes()
            sections = elf_sections(data)
            modinfo = sections['.modinfo'].decode().split('\0')
            version = next(l for l in modinfo if l.startswith('vermagic='))
            assert version == 'vermagic=5.4.0-xilinx-v2020.2 SMP preempt mod_unload modversions ARMv7 p2v8 ', version
            versions = sections['__versions']
            assert len(versions) % 64 == 0
            imports = []
            for offset in range(0, len(versions), 64):
                crc = struct.unpack_from('<I', versions, offset)[0]
                symbol = versions[offset+4:offset+64].split(b'\0')[0].decode()
                assert symbols[symbol] == crc, symbol
                imports.append(symbol)
            modules.append({'name': name, 'sha256': hashlib.sha256(data).hexdigest(),
                            'vermagic': version, 'versioned_imports': len(imports)})
        before = fdt_properties((output / 'base.dtb').read_bytes())
        after = fdt_properties((output / 'combined.dtb').read_bytes())
        exports = check_kernel54_symbols(fdt_properties((output / 'usb-pins-phy.dtbo').read_bytes()))
        assert exports['ss_usb_phy'] == '/amba/soundsight-usb-phy'
        allowed = '/amba/usb@e0002000/'
        changed = {key: {'before_hex': before[key].hex(), 'after_hex': after.get(key, b'').hex()}
                   for key in before if before[key] != after.get(key)}
        assert set(changed) <= {allowed + 'status'}, changed
        assert after[allowed + 'status'] == b'okay\0'
        assert after[allowed + 'dr_mode'] == b'peripheral\0'
        assert after['/amba/usb@e0003000/status'] == b'disabled\0'
        assert '/amba/soundsight-usb-phy/reset-gpios' not in after
        assert after['/amba/soundsight-usb-phy/compatible'] == b'usb-nop-xceiv\0'
        phy_ref = after[allowed + 'usb-phy']
        assert phy_ref == after['/amba/soundsight-usb-phy/phandle']
        pin_path = '/amba/slcr@f8000000/pinctrl@700/soundsight-usb0-pins'
        assert after[allowed + 'pinctrl-0'] == after[pin_path + '/phandle']
        assert after[pin_path + '/conf/io-standard'] == struct.pack('>I', 1)
        assert after['/amba/slcr@f8000000/pinctrl@700/soundsight-usb-reset-pin/conf/io-standard'] == struct.pack('>I', 3)
        report = {'input_sha256': hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
                  'input_files_verified': len(manifest['files']), 'collection_issues': manifest['issues'],
                  'fit_kernel': kernel, 'fit_fdt': dtb, 'fit_hashes_checked': checked_hashes,
                  'modules': modules, 'dt_existing_property_changes': changed,
                  'kernel54_symbol_exports': exports,
                  'status': 'OFFLINE_CHECKS_PASS; BOARD_RESULTS_RECORDED_SEPARATELY'}
        (output / 'checks.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({k: v for k, v in report.items() if k != 'collection_issues'}, indent=2))


if __name__ == '__main__':
    main()
