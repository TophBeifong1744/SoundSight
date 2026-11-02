"""Host-only failure-boundary tests; no real hardware paths are used."""
import ast
import configparser
from contextlib import ExitStack, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'ps/usb_network/usb_network.py'
spec = importlib.util.spec_from_file_location('usb_runtime', str(SCRIPT))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
check_spec = importlib.util.spec_from_file_location('usb_artifact_checks', str(SCRIPT.parent / 'check_artifacts.py'))
artifact_checks = importlib.util.module_from_spec(check_spec)
check_spec.loader.exec_module(artifact_checks)


class USBNetworkTests(unittest.TestCase):
    def test_old_kernel_rule_rejects_actual_failed_candidate(self):
        old = SCRIPT.parents[3] / 'document/evidence/usb-network-preflight-20261102/phandle-failure/original-candidate.zip'
        with zipfile.ZipFile(old) as archive:
            props = artifact_checks.fdt_properties(archive.read('SoundSight_USB/usb-pins-phy.dtbo'))
        with self.assertRaisesRegex(ValueError, '//soundsight-usb-phy'):
            artifact_checks.check_kernel54_symbols(props)

    def test_raw_symbol_path_rejects_duplicate_slash(self):
        with tempfile.TemporaryDirectory(prefix='soundsight-usb-symbol-') as folder:
            tree = Path(folder)
            (tree / '__symbols__').mkdir()
            symbol = tree / '__symbols__/ss_usb_phy'
            symbol.write_bytes(b'//soundsight-usb-phy\0')
            with patch.object(runtime, 'DT', tree):
                with self.assertRaisesRegex(RuntimeError, 'invalid live symbol'):
                    runtime.validate_symbol('ss_usb_phy', '/amba/soundsight-usb-phy')
                symbol.write_bytes(b'/amba/soundsight-usb-phy\0')
                node = tree / 'amba/soundsight-usb-phy'
                node.mkdir(parents=True)
                (node / 'phandle').write_bytes(b'\0\0\0\x39')
                self.assertEqual(runtime.validate_symbol('ss_usb_phy', '/amba/soundsight-usb-phy'), b'\0\0\0\x39')

    def test_rejected_configfs_blob_is_not_success_even_with_applied_status(self):
        with tempfile.TemporaryDirectory(prefix='soundsight-usb-overlay-') as folder:
            root = Path(folder)
            (root / 'device-tree/overlays').mkdir(parents=True)
            (root / 'candidate.dtbo').write_bytes(b'fixture-fdt')
            original_write = Path.write_bytes
            def emulate_close_failure(path, data):
                if path.name == 'dtbo':
                    (path.parent / 'status').write_text('applied\n')
                    return original_write(path, b'')
                return original_write(path, data)
            with patch.multiple(runtime, HERE=root, CF=root), patch.object(Path, 'write_bytes', emulate_close_failure):
                with self.assertRaisesRegex(RuntimeError, 'overlay rejected by kernel'):
                    runtime.overlay('fixture', 'candidate.dtbo')

    def test_python38_syntax(self):
        ast.parse(SCRIPT.read_text(), feature_version=8)

    def test_start_requires_wiring_confirmation_before_any_preflight(self):
        with patch.object(runtime, 'preflight') as check:
            with self.assertRaisesRegex(RuntimeError, 'P4'):
                runtime.start('192.168.77.2/24', False)
            check.assert_not_called()

    def test_rejected_baseline_performs_no_writes_or_module_commands(self):
        with patch.object(runtime, 'preflight', side_effect=RuntimeError('mismatch')), \
                patch.object(runtime, 'write') as write, patch.object(runtime, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                runtime.start('192.168.77.2/24', True)
            write.assert_not_called()
            run.assert_not_called()

    def test_ip_boundary(self):
        self.assertEqual(str(runtime.validate_ip('192.168.77.2/24')), '192.168.77.2/24')
        for bad in ['192.168.77.0/24', '192.168.77.255/24', '127.0.0.1/24',
                    '169.254.1.2/24', '8.8.8.8/24', '10.0.0.1/8']:
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                runtime.validate_ip(bad)

    def install_fixture(self, root, stack):
        source = root / 'source'
        source.mkdir()
        (source / 'usb_network.py').write_bytes(b'fixture runtime')
        (source / 'package-manifest.json').write_text(json.dumps({'files': {
            'usb_network.py': hashlib.sha256(b'fixture runtime').hexdigest()}}))
        state = root / 'state.json'
        state.write_text(json.dumps({'stage': 'ready', 'board_ip': '192.168.77.2/24', 'udc': 'fixture'}))
        udc = root / 'udc/fixture'
        udc.mkdir(parents=True)
        (udc / 'state').write_text('configured')
        install = root / 'installed'
        unit = root / 'service'
        stack.enter_context(patch.multiple(runtime, HERE=source, STATE=state, UDC_ROOT=udc.parent,
                                          INSTALL=install, SERVICE_FILE=unit))
        stack.enter_context(patch.object(runtime.os, 'geteuid', return_value=0, create=True))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return install, unit

    def test_failed_enable_disables_and_can_retry_valid_installation(self):
        with tempfile.TemporaryDirectory(prefix='soundsight-usb-runtime-') as folder, ExitStack() as stack:
            install, unit = self.install_fixture(Path(folder), stack)
            commands = []
            def fail_enable(*args):
                commands.append(args)
                if args[1] == 'enable':
                    raise subprocess.CalledProcessError(1, args)
                return ''
            with patch.object(runtime, 'run', side_effect=fail_enable):
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.enable_service()
            self.assertIn(('systemctl', 'disable', runtime.SERVICE), commands)
            self.assertTrue(install.exists())
            before = unit.read_bytes()
            with patch.object(runtime, 'run', return_value='') as run:
                runtime.enable_service()
                run.assert_any_call('systemctl', 'enable', runtime.SERVICE)
            self.assertEqual(unit.read_bytes(), before)

    def test_service_waits_for_actual_boot_partition_owner(self):
        with tempfile.TemporaryDirectory(prefix='soundsight-usb-boot-order-') as folder, ExitStack() as stack:
            _, unit = self.install_fixture(Path(folder), stack)
            with patch.object(runtime, 'run', return_value=''):
                runtime.enable_service()
            generated = configparser.ConfigParser(interpolation=None)
            generated.read_string(unit.read_text())
            dropin = configparser.ConfigParser(interpolation=None)
            dropin.read(SCRIPT.parent / '10-bootpy.conf')
            for key in ('Requires', 'After'):
                self.assertIn('bootpy.service', generated['Unit'][key].split())
                self.assertEqual(dropin['Unit'][key], 'bootpy.service')
            self.assertEqual(generated['Service']['Type'], 'oneshot')

    def test_copy_failure_leaves_no_partial_install_and_foreign_unit_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix='soundsight-usb-runtime-') as folder, ExitStack() as stack:
            install, unit = self.install_fixture(Path(folder), stack)
            with patch.object(runtime.shutil, 'copytree', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    runtime.enable_service()
            self.assertFalse(install.exists())
            self.assertFalse(unit.exists())
            self.assertEqual(list(Path(folder).glob('.soundsight-usb-*')), [])
            unit.write_text('foreign service')
            with self.assertRaisesRegex(RuntimeError, 'service differs'):
                runtime.enable_service()
            self.assertEqual(unit.read_text(), 'foreign service')


if __name__ == '__main__':
    unittest.main()
