"""Run the new shell through the established real-shell environment matrix."""
import shlex
import unittest
from test_launcher import LauncherTests, ROOT


class ThreeDLauncherTests(LauncherTests):
    def setUp(self):
        super().setUp()
        script = (ROOT/'soundsight-3d.sh').read_text(encoding='utf-8')
        script = script.replace('/usr/local/share/pynq-venv/bin/python3', self.venv.as_posix())
        script = script.replace('check_python '+self.venv.as_posix(),
                                'check_python '+shlex.quote(self.venv.as_posix()))
        (self.app/'soundsight.sh').write_bytes(script.encode('utf-8'))
        helper = self.app/'software/tetra3d/linux/board_3d.py'
        helper.parent.mkdir(parents=True)
        helper.write_bytes((self.app/'software/ps/board_tools.py').read_bytes())

    def test_package_launcher_uses_lf(self):
        self.assertNotIn(b'\r', (ROOT/'soundsight-3d.sh').read_bytes())

    def test_check_needs_no_pynq_but_manual_does(self):
        self.interpreter(self.venv, good=False)
        self.helper(self.run_entry('check'))
        self.interpreter(self.bin/'python3', good=False)
        result = self.run_entry('manual', '--vertical', '110')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('HELPER=', result.stdout)


if __name__ == '__main__':
    unittest.main(defaultTest='ThreeDLauncherTests', verbosity=2)
