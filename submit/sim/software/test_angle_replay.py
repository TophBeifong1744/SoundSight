"""Independent expected edge cases for the offline estimator, no hardware access."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[2] / 'tools' / 'replay_pynq_angle_filter.py'
spec = importlib.util.spec_from_file_location('angle_replay', path)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def frames(angles, start=1):
    return [{'frame': {'sequence': start+i}, 'result': {
        'direction_valid': a is not None, 'angle_q8': round(a*256) if a is not None else 0}}
        for i, a in enumerate(angles)]


class AngleReplayTests(unittest.TestCase):
    def test_branch_cut(self):
        e = r.estimate([179]*10 + [-179]*10)
        self.assertAlmostEqual(e['arithmetic'], 0)
        self.assertAlmostEqual(abs(e['filtered']), 180)

    def test_two_spikes(self):
        e = r.estimate([-13]*18 + [-90]*2)
        self.assertAlmostEqual(e['arithmetic'], -20.7)
        self.assertAlmostEqual(e['filtered'], -13)
        self.assertEqual(e['inlier_count'], 18)

    def test_equal_modes_rejected(self):
        self.assertIsNone(r.estimate([-20]*10 + [80]*10)['filtered'])

    def test_inlier_minimum_and_majority(self):
        self.assertIsNone(r.estimate([-13]*11 + [-80])['filtered'])
        self.assertIsNone(r.estimate([-13]*12 + [-80]*8)['filtered'])
        self.assertAlmostEqual(r.estimate([-13]*14 + [-80]*6)['filtered'], -13)

    def test_invalid_and_incomplete_no_target(self):
        for f in (frames([None]*20), frames([-13]*11 + [None]*9), frames([-13]*19)):
            self.assertFalse(r.replay(f)[0]['emitted'])
            self.assertIsNone(r.replay(f)[0]['filtered'])

    def test_new_direction_not_rejected_by_old_target(self):
        w = r.replay(frames([-13]*20 + [80]*20))
        self.assertTrue(w[1]['emitted'])
        self.assertAlmostEqual(w[1]['filtered'], 80)

    def test_deadband_relative_to_last_emitted_target(self):
        w = r.replay(frames([-13]*20 + [-11]*20 + [-9]*20))
        self.assertEqual([x['emitted'] for x in w], [True, False, True])
        self.assertAlmostEqual(w[1]['held_target'], -13)
        self.assertAlmostEqual(w[2]['held_target'], -9)

    def test_rejected_window_not_a_fresh_command(self):
        w = r.replay(frames([-13]*20 + [None]*20))
        self.assertFalse(w[1]['emitted'])
        self.assertIsNone(w[1]['filtered'])
        self.assertAlmostEqual(w[1]['held_target'], -13)

    def test_no_lookahead_and_end_frame_emission(self):
        prefix = frames([-13]*20)
        self.assertEqual(r.replay(prefix)[0], r.replay(prefix + frames([80]*20,21))[0])
        self.assertEqual(r.replay(prefix)[0]['last_sequence'], 20)

    def test_opposing_mean_is_undefined(self):
        self.assertIsNone(r.circular_mean([0,180]))


if __name__ == '__main__':
    unittest.main()
