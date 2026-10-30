"""Acoustic-only CLI routing and actual client regressions; no hardware access."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
for folder in ('software/ps', 'software/tests', 'software/tetra3d/linux', 'software/tetra3d/tests'):
    sys.path.insert(0, str(ROOT/folder))
import board_3d
import runtime_3d
from test_online_3d import config, AxisModel, result
from client_3d import ThreeDClient
import motion_3d


class FollowSoundTests(unittest.TestCase):
    def options(self, words, calibration=None):
        with patch.object(board_3d, 'Solver3D'), patch.object(
                board_3d, 'load_config', return_value=config() if calibration is None else calibration):
            return board_3d.run_options(board_3d.parser().parse_args(words))

    def test_axes_default_off(self):
        a = self.options(['follow-sound', '--min-level', '7000'], {})
        self.assertEqual((a.command, a.axis_mask, a.motion_requested), ('follow-sound', 0, False))

    def test_explicit_axes_keep_acoustic_route(self):
        for axes, mask in motion_3d.MASKS.items():
            a = self.options(['follow-sound', '--axes', axes, '--min-level', '7000', '--frames', '100'])
            self.assertEqual((a.command, a.axis_mask, a.frames), ('follow-sound', mask, 100))

    def test_existing_run_axes_still_speaker_gated(self):
        a = self.options(['run', '--axes', 'both', '--min-level', '7000'])
        self.assertEqual((a.command, a.seconds), ('speaker', 0.))
        a = self.options(['speaker', '--axes', 'both', '--seconds', '30', '--min-level', '7000'])
        self.assertEqual((a.command, a.seconds), ('speaker', 30.))

    def test_missing_calibration_blocks_motion(self):
        for c in ({}, {'horizontal': config()['horizontal']}):
            with self.assertRaises((KeyError, ValueError)):
                self.options(['follow-sound', '--axes', 'both', '--min-level', '7000'], c)

    def test_bad_limits_and_invalid_frames_rejected(self):
        c = config(); c['vertical']['min_deg'] = 221
        with self.assertRaises(ValueError):
            self.options(['follow-sound', '--axes', 'both', '--min-level', '7000'], c)
        for extra in (['--frames', '-1'], ['--debug'], ['--debug', '--frames', '1001']):
            with self.assertRaises(ValueError):
                self.options(['follow-sound']+extra)

    def test_main_uses_existing_runtime_and_status_preflight(self):
        # Execute main routing, not just parser; prohibit any speaker runtime import.
        original_import = __import__
        def checked_import(name, *args, **kwargs):
            if name in ('speaker_runtime_3d', 'speaker_process', 'live_speaker_follow'):
                raise AssertionError('Acoustic mode started speaker runtime')
            return original_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temp, patch.object(board_3d, 'ROOT', Path(temp)), \
                patch.object(board_3d, 'Solver3D'), \
                patch.object(board_3d, 'load_config', return_value=config()), \
                patch.object(board_3d, 'check_hwh'), \
                patch.object(board_3d, 'single_owner', return_value=contextlib.nullcontext()), \
                patch.object(board_3d.board_tools, 'inspect_loaded') as inspect, \
                patch.object(runtime_3d, 'run', return_value=0) as run, \
                patch('builtins.__import__', side_effect=checked_import), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(board_3d.main(['follow-sound', '--axes', 'both', '--frames', '100', '--min-level', '7000',
                                           '--geometry', str(ROOT/'software/tetra3d/core/tetra40-nominal.json')]), 0)
            inspect.assert_called_once()
            self.assertEqual(run.call_args[0][0].axis_mask, 3)
            self.assertIn('IDENTITY_GATE=OFF', output.getvalue())

    def test_real_client_still_requires_filtered_direction_and_stops(self):
        device = AxisModel()
        class Solver:
            def solve(self, frame):
                return result()
        client = ThreeDClient(device, Solver(), 7000, 3, 3, 3, config())
        self.assertIsNone(client.speaker_permission)
        client.start(clear_faults=0x40)
        records = []
        for _ in range(2): client.record_one(records.append)
        self.assertFalse(any(r['motion']['committed'] for r in records))
        client.record_one(records.append)
        self.assertTrue(records[-1]['motion']['committed'])
        client.stop_direction_output()
        self.assertFalse(device.reg[motion_3d.STATE] & 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
