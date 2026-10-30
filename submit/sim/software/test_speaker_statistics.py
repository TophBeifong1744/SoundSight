"""Opt-in whole-session score accounting, persistence and offline short command."""
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for folder in ('software/ps', 'software/tests', 'software/tetra3d/linux'):
    sys.path.insert(0, str(ROOT/folder))
from speaker_statistics import SpeakerStatistics, save_last, show_last, LAST_FILE
from test_speaker_follow import PipelineTests
import board_3d


class StatisticsTests(unittest.TestCase):
    def test_whole_session_exceeds_32_rows_and_has_exact_threshold(self):
        stats = SpeakerStatistics(.65)
        for i in range(100):
            stats.observe(.65 if i < 60 else .2, 1. if i < 50 else 3.)
        result = stats.snapshot()
        self.assertEqual(result['successful_calculations'], 100)
        self.assertEqual(result['threshold_passes'], 60)
        self.assertEqual(result['total_compute_seconds'], 200.)
        self.assertEqual(result['average_compute_seconds'], 2.)
        self.assertEqual(result['max_compute_seconds'], 3.)

    def test_skipped_invalid_failed_values_not_in_denominator(self):
        stats = SpeakerStatistics(.5)
        for score, seconds in ((None, .1), (float('nan'), 2.), (2., 2.),
                               (True, 2.), (.9, float('inf')), (.9, -1.)):
            stats.observe(score, seconds)
        stats.observe(.2, 4.)
        result = stats.snapshot()
        self.assertEqual(result['successful_calculations'], 1)
        self.assertEqual(result['threshold_passes'], 0)
        self.assertEqual(result['average_compute_seconds'], 4.)

    def test_zero_and_missing_threshold_are_not_false_zeros(self):
        stats = SpeakerStatistics(None)
        self.assertIsNone(stats.snapshot()['average_compute_seconds'])
        self.assertIsNone(stats.snapshot()['max_compute_seconds'])
        stats.observe(.8, 2.)
        self.assertEqual(stats.snapshot()['successful_calculations'], 1)
        self.assertIsNone(stats.snapshot()['threshold_passes'])

    def test_inference_wiring_and_disabled_behavior(self):
        helper = PipelineTests()
        disabled, baseline = helper.infer()
        enabled, rows = helper.infer(collect_statistics=True)
        self.assertIsNone(disabled.statistics)
        self.assertEqual(rows, baseline)
        self.assertEqual(enabled.statistics.snapshot()['successful_calculations'], 1)
        self.assertAlmostEqual(enabled.statistics.snapshot()['average_compute_seconds'], 3.2)
        enabled.input_done = threading.Event()
        enabled.threads = []
        enabled.front_blocks = enabled.partial_samples = enabled.accepted = 0
        enabled.max_lag = 0.
        self.assertEqual(enabled.finish(True)['statistics']['threshold_passes'], 1)
        bad, rows = helper.infer(frames=99, collect_statistics=True)
        self.assertIsNotNone(bad.error)
        self.assertEqual(bad.statistics.snapshot()['successful_calculations'], 0)

    def test_constant_space_and_no_io_in_hot_path(self):
        stats = SpeakerStatistics(.5)
        fields = set(vars(stats))
        with patch('builtins.open', side_effect=AssertionError('No writes while running')), \
                patch('os.fsync', side_effect=AssertionError('No sync while running')):
            for _ in range(100000):
                stats.observe(.8, .01)
        self.assertEqual(set(vars(stats)), fields)
        self.assertTrue(all(not isinstance(x, (list, dict, tuple)) for x in vars(stats).values()))
        self.assertEqual(stats.snapshot()['successful_calculations'], 100000)

    def test_cli_is_explicit_and_stats_reader_does_not_open_hardware(self):
        self.assertFalse(board_3d.parser().parse_args(['speaker']).speaker_stats)
        self.assertTrue(board_3d.parser().parse_args(['speaker', '--speaker-stats']).speaker_stats)
        with tempfile.TemporaryDirectory() as tmp, patch.object(board_3d, 'ROOT', Path(tmp)), \
                patch.object(board_3d, 'check_hwh', side_effect=AssertionError('No hardware')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(board_3d.main(['speaker-stats']), 0)
            self.assertIn('NO_SAVED_SESSION', output.getvalue())

    def report(self, result='PASS'):
        stats = SpeakerStatistics(.5)
        stats.observe(.9, 3.)
        return dict(result=result, error=None if result == 'PASS' else 'test fault',
                    settings=dict(target_id='user2'), speaker_worker=dict(statistics=stats.snapshot()))

    def test_save_and_read_last_not_last_enabled_or_largest_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_last(root, self.report(), root/'logs/speaker-3d-20990101.json', True)
            with redirect_stdout(io.StringIO()) as output:
                show_last(root)
            self.assertIn('SUCCESSFUL=1 PASSED=1 AVG_SECONDS=3.000000 MAX_SECONDS=3.000000', output.getvalue())
            # A subsequent session with statistics disabled must not show old counts.
            save_last(root, {}, root/'logs/speaker-3d-20210101.json', False)
            with redirect_stdout(io.StringIO()) as output:
                show_last(root)
            self.assertIn('STATS_DISABLED_FOR_LAST_SESSION', output.getvalue())
            value = json.loads((root/'logs'/LAST_FILE).read_text())
            self.assertEqual(value['report'], 'logs/speaker-3d-20210101.json')
            self.assertIsNone(value['statistics'])

    def test_worker_failure_preserves_available_counts_or_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = save_last(root, self.report('FAIL'), root/'logs/run.json', True)
            self.assertTrue(value['available'])
            self.assertEqual(value['session_result'], 'FAIL')
            value = save_last(root, dict(result='FAIL'), root/'logs/failed.json', True)
            self.assertFalse(value['available'])
            with redirect_stdout(io.StringIO()) as output:
                show_last(root)
            self.assertIn('STATS_UNAVAILABLE', output.getvalue())

    def test_failed_atomic_replace_keeps_previous_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_last(root, self.report(), root/'logs/old.json', True)
            before = (root/'logs'/LAST_FILE).read_bytes()
            with patch('speaker_statistics.os.replace', side_effect=OSError('test')):
                with self.assertRaises(OSError):
                    save_last(root, {}, root/'logs/new.json', False)
            self.assertEqual((root/'logs'/LAST_FILE).read_bytes(), before)
            self.assertEqual(list((root/'logs').glob('.speaker-stats-*')), [])


if __name__ == '__main__':
    unittest.main(defaultTest='StatisticsTests')
