"""项目串口消息保持ASCII英文；中文注释和不参与CLI的说明可保留。"""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'software/ps'))
import run_normal


class SerialEnglishTests(unittest.TestCase):
    def test_all_runtime_string_literals_are_ascii(self):
        paths = list((ROOT/'software/ps').glob('*.py')) + [ROOT/'tools/install_normal_update.py']
        for path in paths:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            docs = {id(node.body[0].value) for node in ast.walk(tree)
                    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                    and node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                    self.assertTrue(node.value.isascii(), '%s:%s %r' % (path.name, node.lineno, node.value))

    def test_cli_help_ascii_and_no_hardware_import(self):
        commands = [('run_device.py', '--operation', 'normal'),
                    ('run_device.py', '--operation', 'debug'), ('run_capture.py',),
                    ('run_smp.py',), ('recover_ram.py',), ('board_tools.py',)]
        for command in commands:
            result = subprocess.run([sys.executable, '-B', str(ROOT/'software/ps'/command[0]),
                                     *command[1:], '--help'], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.isascii(), command)
            self.assertTrue(result.stderr.isascii(), command)

    def test_every_display_reason_ascii_including_angle_unit(self):
        self.assertTrue(run_normal.display_line(None, 1).isascii())
        for reason in run_normal.REASON_TEXT:
            state = dict(phase='running', latest=dict(sequence=2, level=9000, at=1,
                         output=dict(valid=False, reason=reason)), window=None)
            self.assertTrue(run_normal.display_line(state, 1).isascii())
        state['latest']['output'] = dict(valid=True, angle_deg=-12.34)
        self.assertIn('ANGLE=-12.34 deg SERVO=OFF', run_normal.display_line(state, 1))
        state['latest']['output'] = dict(valid=False, reason='collecting_window')
        state['window'] = dict(angle_deg=-12.34, at=1)
        self.assertTrue(run_normal.display_line(state, 1).isascii())
        self.assertIn('HISTORY_ONLY', run_normal.display_line(state, 1))


if __name__ == '__main__': unittest.main()
