"""Tool discovery regression; creates fake files, never starts EDA."""
from pathlib import Path
import sys
import tempfile
import os
import shutil
import subprocess
import json
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import tool_config as cfg


class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='soundsight tools ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.a = self.root / 'local tools'
        self.b = self.root / 'environment tools'
        for root in (self.a, self.b):
            (root / 'bin').mkdir(parents=True)
            for name in ('vivado.bat', 'gcc.exe', 'xvlog.bat', 'xvhdl.bat', 'xelab.bat', 'xsim.bat'):
                (root / 'bin' / name).touch()

    def test_local_paths_with_spaces(self):
        local = {'VIVADO_ROOT': str(self.a), 'GCC_ROOT': str(self.a)}
        self.assertEqual(cfg.simulation_tools(cfg.vivado_root({}, local)), self.a)
        self.assertEqual(cfg.gcc_executable({}, local), self.a / 'bin/gcc.exe')

    def test_environment_overrides_local_including_alias(self):
        self.assertEqual(cfg.vivado_root({'VIVADO_ROOT': str(self.b)}, {'VIVADO_ROOT': str(self.a)}), self.b)
        self.assertEqual(cfg.gcc_executable({'GCC_ROOT': str(self.b)}, {'SS_GCC': str(self.a / 'bin/gcc.exe')}), self.b / 'bin/gcc.exe')

    def test_path_without_local_config(self):
        with patch.object(cfg.shutil, 'which', return_value=str(self.b / 'bin/vivado.bat')) as lookup:
            self.assertEqual(cfg.vivado_root({'PATH': 'provided-path'}, {}), self.b)
            lookup.assert_called_once_with('vivado.bat', path='provided-path')
        with patch.object(cfg.shutil, 'which', return_value=str(self.b / 'bin/gcc.exe')):
            self.assertEqual(cfg.gcc_executable({}, {}), self.b / 'bin/gcc.exe')

    def test_invalid_explicit_path_does_not_fall_back(self):
        with self.assertRaises(FileNotFoundError):
            cfg.vivado_root({'VIVADO_ROOT': str(self.root / 'missing')}, {'VIVADO_ROOT': str(self.a)})
        with self.assertRaises(FileNotFoundError):
            cfg.gcc_executable({'SS_GCC': str(self.root / 'missing.exe')}, {'GCC_ROOT': str(self.a)})

    def test_missing_tools_actionable(self):
        with patch.object(cfg.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, 'tools.local.env'):
                cfg.vivado_root({}, {})
            with self.assertRaisesRegex(FileNotFoundError, 'tools.local.env'):
                cfg.gcc_executable({}, {})

    def test_public_batch_in_fresh_copy_without_local_file(self):
        repo = Path(__file__).resolve().parents[2]
        fresh = self.root / 'fresh checkout'
        files = ('project/script/setting.bat', 'project/script/run.bat',
                 'simulation/script/run.bat', 'tools/run_vivado.py',
                 'tools/run_sim.py', 'tools/tool_config.py')
        for name in files:
            target = fresh / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, target)
        env = {key.upper(): value for key, value in os.environ.items()}
        for key in cfg.KEYS:
            env.pop(key, None)
        env['PATH'] = os.pathsep.join((str(Path(sys.executable).parent), str(self.a / 'bin'),
                                     str(Path(env['SYSTEMROOT']) / 'System32')))
        # Fake Vivado files ensure this test cannot launch real EDA.
        for name in ('project/script/run.bat', 'simulation/script/run.bat'):
            result = subprocess.run([env['COMSPEC'], '/d', '/c', str(fresh / name), '--check-tools'],
                                    cwd=self.root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(json.loads(result.stdout)['eda_started'])
        (fresh / 'tools.local.env').write_text('PYTHON_EXE=missing-python.exe\n', encoding='utf-8')
        result = subprocess.run([env['COMSPEC'], '/d', '/c', str(fresh / 'project/script/run.bat'), '--check-tools'],
                                cwd=self.root, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        env['PYTHON_EXE'] = sys.executable
        result = subprocess.run([env['COMSPEC'], '/d', '/c', str(fresh / 'project/script/run.bat'), '--check-tools'],
                                cwd=self.root, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_parser_and_missing_sim_tool(self):
        p = self.root / 'settings.env'
        p.write_text('# comment\nPYTHON_EXE=\nVIVADO_ROOT=' + str(self.a) + '\n', encoding='utf-8-sig')
        self.assertEqual(cfg.local_settings(p), {'VIVADO_ROOT': str(self.a)})
        self.assertEqual(cfg.local_settings(self.root / 'absent'), {})
        p.write_text('UNEXPECTED=value', encoding='utf-8')
        with self.assertRaises(ValueError):
            cfg.local_settings(p)
        (self.a / 'bin/xsim.bat').unlink()
        with self.assertRaises(FileNotFoundError):
            cfg.simulation_tools(self.a)


if __name__ == '__main__':
    unittest.main()
