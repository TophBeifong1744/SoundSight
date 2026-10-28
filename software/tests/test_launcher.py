"""用真实POSIX shell和Python执行入口；替换板端路径/模块，不接触硬件。"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHELL = os.environ.get('SOUNDSIGHT_TEST_SH') or (shutil.which('sh') if os.name != 'nt' else None)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        if not SHELL:
            self.fail('Set SOUNDSIGHT_TEST_SH to a POSIX shell (Git bash on Windows)')
        self.temp = tempfile.TemporaryDirectory(prefix='soundsight launcher ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root/'app with spaces'
        (self.app/'software/ps').mkdir(parents=True)
        self.bin = self.root/'bin'; self.bin.mkdir()
        self.good = self.root/'good'; (self.good/'pynq').mkdir(parents=True)
        (self.good/'pynq/__init__.py').write_text(
            'class NeverHardware:\n'
            ' def __init__(self,*a,**k): raise AssertionError("NO_HARDWARE_ALLOWED")\n'
            'Overlay = MMIO = Clocks = NeverHardware\n', encoding='ascii')
        self.bad = self.root/'bad'; (self.bad/'pynq').mkdir(parents=True)
        (self.bad/'pynq/__init__.py').write_text('raise ImportError("TEST_MISSING_PYNQ")\n', encoding='ascii')
        self.venv = self.root/'venv python'
        # 只替换测试机不存在的板端路径；选择、探测、exec均执行原shell源码。
        script = (ROOT/'soundsight.sh').read_text(encoding='utf-8')
        script = script.replace('/usr/local/share/pynq-venv/bin/python3', self.venv.as_posix())
        # 原路径没有空格；测试替身故意含空格，保留一个完整shell参数。
        script = script.replace('check_python '+self.venv.as_posix(), 'check_python '+shlex.quote(self.venv.as_posix()))
        (self.app/'soundsight.sh').write_bytes(script.encode('utf-8'))
        (self.app/'software/ps/board_tools.py').write_text(
            'import json,os,sys\n'
            'print("HELPER="+json.dumps(dict(args=sys.argv[1:],cwd=os.getcwd(),'
            'selected=os.environ.get("TEST_SELECTED"),home=os.environ.get("PYTHONHOME"),'
            'xrt=os.environ.get("XILINX_XRT"),override=os.environ.get("PYNQ_PYTHON"),'
            'path_before=os.environ.get("TEST_PATH_BEFORE"))))\n', encoding='ascii')
        self.env = os.environ.copy()
        for key in ('PYNQ_PYTHON', 'PYTHONHOME', 'PYTHONPATH'):
            self.env.pop(key, None)
        # Windows Git shell自己的路径转换后再设置PATH，避免Windows冒号分隔冲突。
        self.env['SS_TEST_BIN'] = self.bin.as_posix()
        self.env['SS_TEST_APP'] = self.app.as_posix()
        self.env['SS_TEST_PYTHON'] = sys.executable.replace('\\', '/')
        self.env['MSYS2_ENV_CONV_EXCL'] = 'XILINX_XRT'

    def interpreter(self, path, good=True, label='venv'):
        site = self.good if good else self.bad
        path.write_bytes(('#!/bin/sh\n'
                        'export TEST_PATH_BEFORE="${PYTHONPATH-unset}"\n'
                        'export TEST_SELECTED='+shlex.quote(label)+'\n'
                        'export PYTHONPATH='+shlex.quote(site.as_posix())+'\n'
                        'exec "$SS_TEST_PYTHON" "$@"\n').encode('ascii'))
        path.chmod(0o755)

    def run_entry(self, *args):
        return subprocess.run([SHELL, '-c',
                               'if command -v cygpath >/dev/null 2>&1; then SS_TEST_BIN=$(cygpath -u "$SS_TEST_BIN"); fi; '
                               'PATH="$SS_TEST_BIN:$PATH"; export PATH; sh "$SS_TEST_APP/soundsight.sh" "$@"',
                               'launcher-test', *args], env=self.env, cwd=self.root,
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def helper(self, result):
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith('HELPER=')))

    def test_venv_preferred_and_arguments_forwarded(self):
        self.interpreter(self.venv)
        self.interpreter(self.bin/'python3', label='system')
        result = self.run_entry('run', 'normal', '--min-level', '5000')
        data = self.helper(result)
        self.assertEqual(data['selected'], 'venv')
        self.assertEqual(data['args'], ['run','normal','--min-level','5000'])
        self.assertEqual(Path(data['cwd']).resolve(), self.app.resolve())
        self.assertIn('PYNQ_IMPORT_OK=1', result.stdout)
        self.assertIn('PYTHON_EXE=', result.stdout)

    def test_missing_venv_falls_back_to_verified_system(self):
        self.interpreter(self.bin/'python3', label='system')
        self.assertEqual(self.helper(self.run_entry('prepare'))['selected'], 'system')

    def test_executable_without_pynq_is_not_accepted(self):
        self.interpreter(self.venv, good=False)
        self.interpreter(self.bin/'python3', label='system')
        result = self.run_entry('prepare')
        self.assertEqual(self.helper(result)['selected'], 'system')
        self.assertIn('PYTHON_PROBE_FAILED=', result.stderr)

    def test_no_working_pynq_stops_before_helper(self):
        self.interpreter(self.venv, good=False)
        self.interpreter(self.bin/'python3', good=False)
        result = self.run_entry('prepare')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('HELPER=', result.stdout)
        self.assertIn('No board helper started', result.stderr)

    def test_explicit_override_with_spaces(self):
        override = self.root/'custom python'
        self.interpreter(override, label='override')
        self.env['PYNQ_PYTHON'] = override.as_posix()
        self.assertEqual(self.helper(self.run_entry('status'))['selected'], 'override')

    def test_missing_override_falls_back_with_notice(self):
        self.interpreter(self.venv)
        self.env['PYNQ_PYTHON'] = (self.root/'missing').as_posix()
        result = self.run_entry('prepare')
        self.assertEqual(self.helper(result)['selected'], 'venv')
        self.assertIn('IGNORING_STALE_PYNQ_PYTHON=', result.stderr)

    def test_board_python38_override_recovers_for_every_hardware_command(self):
        self.interpreter(self.bin/'python3.8', good=False, label='stale')
        self.interpreter(self.venv)
        self.env['PYNQ_PYTHON'] = 'python3.8'
        for args in [('prepare',), ('run','normal'), ('run','debug'), ('status',), ('drain',)]:
            with self.subTest(args=args):
                result = self.run_entry(*args)
                data = self.helper(result)
                self.assertEqual(data['selected'], 'venv')
                self.assertEqual(data['override'], self.venv.as_posix())
                self.assertEqual(data['args'], list(args))
                self.assertIn('IGNORING_STALE_PYNQ_PYTHON=python3.8 AUTO_DETECT=1', result.stderr)
                self.assertIn('PYNQ_IMPORT_OK=1', result.stdout)

    def test_stale_override_and_bad_venv_fall_back_to_system(self):
        self.env['PYNQ_PYTHON'] = 'python3.8'
        self.interpreter(self.bin/'python3.8', good=False)
        self.interpreter(self.venv, good=False)
        self.interpreter(self.bin/'python3', label='system')
        data = self.helper(self.run_entry('prepare'))
        self.assertEqual(data['selected'], 'system')
        self.assertEqual(data['override'], 'python3')

    def test_stale_override_with_no_working_environment_still_stops(self):
        self.env['PYNQ_PYTHON'] = 'python3.8'
        self.interpreter(self.bin/'python3.8', good=False)
        self.interpreter(self.venv, good=False)
        self.interpreter(self.bin/'python3', good=False)
        result = self.run_entry('prepare')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('HELPER=', result.stdout)
        self.assertIn('No board helper started', result.stderr)

    def test_polluted_python_environment_removed_and_xrt_set(self):
        self.interpreter(self.venv)
        self.env.update(PYTHONHOME='/nonexistent-home', PYTHONPATH='/wrong-library')
        self.env.pop('XILINX_XRT', None)
        data = self.helper(self.run_entry('prepare'))
        self.assertIsNone(data['home'])
        self.assertEqual(data['path_before'], 'unset')
        self.assertEqual(data['xrt'], '/usr')

    def test_level_and_help_do_not_require_pynq(self):
        self.interpreter(self.venv, good=False)
        for args in [('level',), ('level','6000'), ('filter',), ('filter','10','6'),
                     ('servo-geometry',), ('servo-geometry','10','-5','--source-range-cm','200'),
                     ('run','--help')]:
            result = self.run_entry(*args)
            self.helper(result)
            self.assertNotIn('PYNQ_IMPORT_OK', result.stdout)

    def test_package_launcher_uses_lf(self):
        self.assertNotIn(b'\r', (ROOT/'soundsight.sh').read_bytes())


if __name__ == '__main__': unittest.main()
