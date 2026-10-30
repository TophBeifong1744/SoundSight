"""隔离目录验证安装备份/路径边界；不操作用户真实安装目录。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
from install_normal_update import install
import install_normal_update as updater


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'update'
        self.dest = self.root/'installed'
        self.source.mkdir(); self.dest.mkdir()
        for name in ('soundsight.bit', 'soundsight.hwh', 'software/ps/libss_solver.so', 'old-test.jsonl'):
            p = self.dest/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'KEEP')
        self.names = ['software/ps/run_buffered.py', 'software/ps/run_normal.py']
        (self.dest/self.names[0]).write_bytes(b'OLD_B_CODE')
        for name in self.names:
            p = self.source/'payload'/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'NEW')
        (self.source/'FILES.json').write_text(json.dumps(self.names))

    def tearDown(self): self.temp.cleanup()

    def test_backup_only_replaced_files_preserves_hardware_library_logs(self):
        backup = install(self.source, self.dest)
        self.assertEqual((backup/self.names[0]).read_bytes(), b'OLD_B_CODE')
        self.assertEqual(json.loads((backup/'added-files.json').read_text()), [self.names[1]])
        for name in self.names: self.assertEqual((self.dest/name).read_bytes(), b'NEW')
        for name in ('soundsight.bit', 'soundsight.hwh', 'software/ps/libss_solver.so', 'old-test.jsonl'):
            self.assertEqual((self.dest/name).read_bytes(), b'KEEP')

    def test_missing_payload_refused_before_replacement(self):
        (self.source/'payload'/self.names[1]).unlink()
        with self.assertRaises(ValueError): install(self.source, self.dest)
        self.assertEqual((self.dest/self.names[0]).read_bytes(), b'OLD_B_CODE')
        self.assertEqual(list(self.dest.glob('backup*')), [])

    def test_traversal_and_hardware_update_refused(self):
        for path in ('../escape.py', '/tmp/escape.py', 'soundsight.bit', 'C:/escape.py'):
            (self.source/'FILES.json').write_text(json.dumps([path]))
            with self.assertRaises(ValueError): install(self.source, self.dest)

    def test_root_launcher_allowed_and_local_settings_preserved(self):
        (self.dest/'settings.local.json').write_bytes(b'{"min_level":4500}')
        (self.source/'payload/soundsight.sh').write_bytes(b'#!/bin/sh\n')
        (self.source/'FILES.json').write_text(json.dumps(self.names+['soundsight.sh']))
        install(self.source, self.dest)
        self.assertEqual((self.dest/'soundsight.sh').read_bytes(), b'#!/bin/sh\n')
        self.assertEqual((self.dest/'settings.local.json').read_bytes(), b'{"min_level":4500}')

    def test_prepare_is_opt_in_and_runs_after_installer_lock_is_closed(self):
        for prepare in (False, True):
            file = mock_open()
            fake_fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *a: None)
            def launch(command):
                file().__exit__.assert_called_once()
                self.assertEqual(command, ['sh',str(self.dest.resolve()/'soundsight.sh'),'prepare'])
                return 0
            with patch.dict(sys.modules, {'fcntl':fake_fcntl}), patch('builtins.open',file), \
                 patch.object(updater,'install') as core, \
                 patch.object(updater.argparse.ArgumentParser,'parse_args',return_value=SimpleNamespace(destination=self.dest,prepare=prepare)), \
                 patch.object(updater.subprocess,'call',side_effect=launch) as call:
                if prepare:
                    with self.assertRaises(SystemExit) as result: updater.main()
                    self.assertEqual(result.exception.code,0)
                    call.assert_called_once()
                else:
                    updater.main(); call.assert_not_called()
                core.assert_called_once()


if __name__ == '__main__': unittest.main()
