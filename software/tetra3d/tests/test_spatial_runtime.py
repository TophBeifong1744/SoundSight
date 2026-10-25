"""Deterministic software contracts; no hardware/ARM performance assertions."""
import copy
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux'))
from spatial_runtime import (DirectionFilterConfig, DirectionFilter3D,
                             DualAxisConfig, DualAxisTracker, angular_distance_deg)


IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def ray(yaw=0., pitch=0.):
    y, p = math.radians(yaw), math.radians(pitch)
    return (math.cos(p)*math.cos(y), math.cos(p)*math.sin(y), math.sin(p))


def result(yaw=0., pitch=0.):
    return dict(direction_valid=1, direction=ray(yaw, pitch))


def update(filt, seq, angle=0., pitch=0., t=None, **kw):
    stamp = seq*0.02 if t is None else t
    return filt.update(result(angle, pitch), timestamp_s=stamp, now_s=stamp,
                       sequence=seq, session_id='session', target_id='person', **kw)['filtered_direction']


def axis_config(**kw):
    values = dict(rotation=IDENTITY, yaw_limits_deg=(-180., 180.),
                  pitch_limits_deg=(-90., 90.), max_yaw_rate_deg_s=30.,
                  max_pitch_rate_deg_s=20., max_update_gap_s=1., target_timeout_s=1.)
    values.update(kw)
    return DualAxisConfig(**values)


def source(stamp, yaw=0., pitch=0., **kw):
    out = dict(valid=True, vector=ray(yaw, pitch), timestamp_s=stamp,
               valid_until_s=stamp+0.5, session_id='session', target_id='person')
    out.update(kw)
    return out


class DirectionTests(unittest.TestCase):
    def test_solver_vector_normalization_and_raw_preservation(self):
        filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
        original = dict(api_status=0, bridge_status=0, first_error=0, reason=0,
                        direction_valid=1, azimuth_valid=0, ux=0., uy=0., uz=2.,
                        nested={'value': [1, 2]}, servo_cmd_valid=0)
        saved = copy.deepcopy(original)
        packet = filt.update(original, timestamp_s=1., now_s=1., sequence=1,
                             session_id='s', target_id='t')
        self.assertEqual(original, saved)
        self.assertEqual(packet['raw_result'], original)
        self.assertIsNot(packet['raw_result']['nested'], original['nested'])
        out = packet['filtered_direction']
        self.assertTrue(out['valid'])
        self.assertEqual(out['vector'], (0., 0., 1.))
        self.assertIsNone(out['azimuth_deg'])
        self.assertEqual(out['elevation_deg'], 90.)

    def test_acquisition_needs_consecutive_consensus(self):
        filt = DirectionFilter3D()
        self.assertFalse(update(filt, 1)['valid'])
        self.assertFalse(update(filt, 2, 90)['valid'])
        self.assertFalse(update(filt, 3, 0)['valid'])
        self.assertFalse(update(filt, 4, 1)['valid'])
        self.assertTrue(update(filt, 5, -1)['valid'])

    def test_cross_180_and_both_poles(self):
        filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1, deadband_deg=0))
        update(filt, 1, 179)
        out = update(filt, 2, -179)
        self.assertGreater(abs(out['azimuth_deg']), 178)
        for pitch in (-90, 90):
            filt = DirectionFilter3D()
            for seq, yaw in enumerate((0, 120, -120), 1):
                out = update(filt, seq, yaw, pitch)
            self.assertTrue(out['valid'])
            self.assertIsNone(out['azimuth_deg'])
            self.assertAlmostEqual(out['elevation_deg'], pitch)

    def test_stationary_noise_smoothed_in_vector_space(self):
        rng = random.Random(1003)
        filt = DirectionFilter3D(DirectionFilterConfig(deadband_deg=0))
        raw_errors, filtered_errors = [], []
        for seq in range(1, 301):
            yaw, pitch = 40+rng.gauss(0, 2), 20+rng.gauss(0, 2)
            out = update(filt, seq, yaw, pitch)
            if seq > 20:
                raw_errors.append(angular_distance_deg(ray(yaw, pitch), ray(40, 20)))
                filtered_errors.append(angular_distance_deg(out['vector'], ray(40, 20)))
        rms_raw = math.sqrt(sum(x*x for x in raw_errors)/len(raw_errors))
        rms_filtered = math.sqrt(sum(x*x for x in filtered_errors)/len(filtered_errors))
        self.assertLess(rms_filtered, 0.5*rms_raw)

    def test_deadband_and_true_step_reacquisition(self):
        filt = DirectionFilter3D()
        for seq in range(1, 4):
            out = update(filt, seq)
        old_expiry = out['valid_until_s']
        for seq in (4, 5):
            out = update(filt, seq, 120)
            self.assertTrue(out['valid'])
            self.assertFalse(out['fresh'])
            self.assertEqual(out['valid_until_s'], old_expiry)
        out = update(filt, 6, 120)
        self.assertEqual(out['reason'], 'reacquired')
        self.assertLess(angular_distance_deg(out['vector'], ray(120)), 1e-6)
        previous = out['vector']
        for seq in range(7, 20):
            out = update(filt, seq, 121)
            self.assertEqual(out['vector'], previous)
            self.assertEqual(out['reason'], 'within_deadband')
            self.assertTrue(out['fresh'])

    def test_antipodal_step_can_reacquire(self):
        filt = DirectionFilter3D()
        for seq in range(1, 4):
            update(filt, seq)
        for seq in range(4, 7):
            out = update(filt, seq, 180)
        self.assertTrue(out['valid'])
        self.assertLess(angular_distance_deg(out['vector'], ray(180)), 1e-6)

    def test_single_outlier_not_accepted_or_refreshing_expiry(self):
        filt = DirectionFilter3D()
        for seq in range(1, 4):
            old = update(filt, seq)
        bad = update(filt, 4, 90)
        self.assertEqual(bad['vector'], old['vector'])
        self.assertEqual(bad['valid_until_s'], old['valid_until_s'])
        good = update(filt, 5, 1)
        self.assertTrue(good['fresh'])
        self.assertLess(angular_distance_deg(good['vector'], ray()), 3)

    def test_invalid_hold_has_fixed_expiry_then_no_vector(self):
        filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
        accepted = update(filt, 1, t=1.)
        for seq, stamp in enumerate((1.1, 1.2, 1.24), 2):
            out = filt.update({'direction_valid': 0}, timestamp_s=stamp, now_s=stamp,
                              sequence=seq, session_id='session', target_id='person')['filtered_direction']
            self.assertTrue(out['valid'])
            self.assertFalse(out['fresh'])
            self.assertEqual(out['valid_until_s'], accepted['valid_until_s'])
        out = filt.poll(now_s=1.25)
        self.assertFalse(out['valid'])
        self.assertIsNone(out['vector'])
        self.assertIsNone(out['azimuth_deg'])
        self.assertFalse(filt.poll(now_s=10.)['valid'])

    def test_future_stale_out_of_order_and_clock_reversal(self):
        for changes, expected in (
                ({'timestamp_s': 1.2}, 'future_timestamp'),
                ({'timestamp_s': .9, 'now_s': 1.1}, 'stale_input'),
                ({'sequence': 1}, 'out_of_order'),
                ({'timestamp_s': 1.}, 'out_of_order'),
                ({'now_s': .9}, 'clock_reversed')):
            with self.subTest(expected=expected):
                filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
                old = update(filt, 1, t=1.)
                args = dict(timestamp_s=1.1, now_s=1.1, sequence=2,
                            session_id='session', target_id='person')
                args.update(changes)
                out = filt.update(result(), **args)['filtered_direction']
                self.assertFalse(out['valid'])
                self.assertIsNone(out['vector'])
                self.assertEqual(out['reason'], expected)
                self.assertEqual(out['valid_until_s'], old['valid_until_s'])

    def test_clock_reversal_breaks_candidate_streak_without_rewinding_clock(self):
        for entry in ('update', 'poll'):
            with self.subTest(entry=entry):
                filt = DirectionFilter3D()
                self.assertFalse(update(filt, 1)['valid'])
                self.assertFalse(update(filt, 2)['valid'])
                if entry == 'update':
                    bad = filt.update(result(), timestamp_s=.03, now_s=.03,
                                      sequence=3, session_id='session',
                                      target_id='person')['filtered_direction']
                else:
                    bad = filt.poll(now_s=.03)
                self.assertFalse(bad['valid'])
                self.assertEqual(bad['reason'], 'clock_reversed')
                self.assertEqual(bad['state'], 'LOST')
                # Reversed input must not move the last legal time (.04) back.
                self.assertEqual(filt.poll(now_s=.035)['reason'], 'clock_reversed')
                self.assertFalse(update(filt, 3)['valid'])
                self.assertFalse(update(filt, 4)['valid'])
                self.assertTrue(update(filt, 5)['valid'])

    def test_context_change_clears_old_target_and_allows_sequence_restart(self):
        for changed in ('session_id', 'target_id'):
            filt = DirectionFilter3D()
            for seq in range(1, 4):
                update(filt, seq)
            args = dict(timestamp_s=.08, now_s=.08, sequence=1,
                        session_id='session', target_id='person')
            args[changed] = 'new'
            out = filt.update(result(90), **args)['filtered_direction']
            self.assertFalse(out['valid'])
            self.assertIsNone(out['vector'])
            self.assertIsNone(out['timestamp_s'])
            self.assertEqual(out[changed], 'new')

    def test_bad_vectors_and_solver_failures_rejected(self):
        samples = [dict(direction_valid=1, direction=v) for v in (
            (0, 0, 0), (math.nan, 0, 1), (math.inf, 1, 1), (True, 0, 1), (1, 2))]
        samples += [dict(result(), **{k: 1}) for k in ('api_status', 'bridge_status', 'first_error', 'reason')]
        samples += [dict(direction_valid='1', direction=(1, 0, 0)), {}]
        for packet in samples:
            filt = DirectionFilter3D()
            out = filt.update(packet, timestamp_s=1., now_s=1., sequence=1,
                              session_id='s', target_id='t')['filtered_direction']
            self.assertFalse(out['valid'])
            self.assertIsNone(out['vector'])

    def test_bad_point_or_gap_breaks_candidate_streak(self):
        filt = DirectionFilter3D()
        update(filt, 1)
        filt.update(result(), timestamp_s=.5, now_s=.5, sequence=2,
                    session_id='session', target_id='person')
        out = update(filt, 3, t=.52)
        self.assertFalse(out['valid'])
        self.assertTrue(update(filt, 4, t=.54)['valid'])
        filt = DirectionFilter3D()
        update(filt, 1)
        filt.update({'direction_valid': 0}, timestamp_s=.04, now_s=.04,
                    sequence=2, session_id='session', target_id='person')
        self.assertFalse(update(filt, 3)['valid'])
        self.assertFalse(update(filt, 4)['valid'])
        self.assertTrue(update(filt, 5)['valid'])

    def test_stale_new_context_cannot_republish_previous_target(self):
        filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
        update(filt, 1, t=1.)
        out = filt.update(result(), timestamp_s=.8, now_s=1.1, sequence=1,
                          session_id='new', target_id='person')['filtered_direction']
        self.assertFalse(out['valid'])
        polled = filt.poll(now_s=1.11)
        self.assertFalse(polled['valid'])
        self.assertIsNone(polled['vector'])

    def test_snapshot_sequence_must_match_input_envelope(self):
        filt = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
        packet = dict(result(), sequence=1)
        out = filt.update(packet, timestamp_s=1., now_s=1., sequence=2,
                          session_id='s', target_id='t')['filtered_direction']
        self.assertEqual(out['reason'], 'sequence_mismatch')
        self.assertIsNone(out['vector'])

    def test_candidate_and_expired_history_cannot_create_output_on_poll(self):
        filt = DirectionFilter3D()
        update(filt, 1)
        out = filt.poll(now_s=1.)
        self.assertEqual(out['state'], 'LOST')
        self.assertIsNone(out['vector'])

    def test_delayed_consecutive_frames_can_still_acquire(self):
        filt = DirectionFilter3D()
        for seq in range(1, 4):
            stamp = seq*.02
            out = filt.update(result(), timestamp_s=stamp, now_s=stamp+.14,
                              sequence=seq, session_id='s', target_id='t')['filtered_direction']
        self.assertTrue(out['valid'])
        self.assertAlmostEqual(out['age_s'], .14)
        self.assertAlmostEqual(out['valid_until_s'], .31)

    def test_configuration_and_metadata_validation(self):
        for kw in ({'hold_s': 0}, {'max_age_s': 1}, {'gate_deg': 180},
                   {'candidate_radius_deg': 90}, {'confirm_frames': True},
                   {'confirm_frames': 0}, {'smoothing_tau_s': math.nan},
                   {'deadband_deg': 35}, {'candidate_max_gap_s': -1}):
            with self.assertRaises(ValueError):
                DirectionFilterConfig(**kw)
        for kw in ({'sequence': True}, {'sequence': -1}, {'timestamp_s': math.nan},
                   {'now_s': math.inf}, {'session_id': ''}, {'target_id': None}):
            args = dict(timestamp_s=1., now_s=1., sequence=1, session_id='s', target_id='t')
            args.update(kw)
            with self.assertRaises(ValueError):
                DirectionFilter3D().update(result(), **args)


class AxisTests(unittest.TestCase):
    def tracker(self, **kw):
        return DualAxisTracker(axis_config(**kw), initial_yaw_deg=0.,
                               initial_pitch_deg=0., initial_time_s=0.)

    def test_disabled_by_default_and_explicit_initial_pose(self):
        tracker = self.tracker()
        out = tracker.update(source(.1, 90), now_s=.1)
        self.assertFalse(out['command_valid'])
        self.assertIsNone(out['yaw_deg'])
        out = tracker.update(source(.2, 90), now_s=.2, enable=True)
        self.assertAlmostEqual(out['yaw_deg'], 3.)
        with self.assertRaises(TypeError):
            DualAxisTracker(axis_config())
        with self.assertRaises(ValueError):
            DualAxisTracker(axis_config(), initial_yaw_deg=None,
                            initial_pitch_deg=0., initial_time_s=0.)

    def test_true_dt_velocity_limits(self):
        tracker = self.tracker()
        previous = (0., 0., 0.)
        for stamp in (.01, .05, .23, .3, .9):
            out = tracker.update(source(stamp, 90, 60), now_s=stamp, enable=True)
            old_t, old_y, old_p = previous
            self.assertTrue(out['command_valid'])
            self.assertLessEqual(abs(out['yaw_deg']-old_y), 30*(stamp-old_t)+1e-10)
            self.assertLessEqual(abs(out['pitch_deg']-old_p), 20*(stamp-old_t)+1e-10)
            previous = stamp, out['yaw_deg'], out['pitch_deg']
        self.assertAlmostEqual(out['yaw_deg'], 27.)
        self.assertAlmostEqual(out['pitch_deg'], 18.)

    def test_limits_and_no_shortcut_through_mechanical_stop(self):
        tracker = self.tracker(yaw_limits_deg=(-45, 45), pitch_limits_deg=(-30, 30),
                               max_yaw_rate_deg_s=1000., max_pitch_rate_deg_s=1000.)
        out = tracker.update(source(.1, 80, 60), now_s=.1, enable=True)
        self.assertEqual((out['yaw_deg'], out['pitch_deg']), (45., 30.))
        self.assertTrue(out['limit_clamped'])
        tracker = DualAxisTracker(axis_config(), initial_yaw_deg=179.,
                                  initial_pitch_deg=0., initial_time_s=0.)
        out = tracker.update(source(.1, -179), now_s=.1, enable=True)
        self.assertAlmostEqual(out['yaw_deg'], 176.)

    def test_mount_rotation(self):
        rotate_z90 = ((0., -1., 0.), (1., 0., 0.), (0., 0., 1.))
        tracker = self.tracker(rotation=rotate_z90, max_yaw_rate_deg_s=1000.)
        out = tracker.update(source(.1), now_s=.1, enable=True)
        self.assertAlmostEqual(out['yaw_deg'], 90.)
        self.assertAlmostEqual(out['pitch_deg'], 0.)

    def test_poles_hold_known_yaw_and_hysteretic_observable_reentry(self):
        for sign in (-1, 1):
            tracker = DualAxisTracker(axis_config(), initial_yaw_deg=30.,
                                      initial_pitch_deg=0., initial_time_s=0.)
            for stamp, yaw, pitch in ((.1, -150, 90), (.2, 150, 83), (.3, -150, 81)):
                out = tracker.update(source(stamp, yaw, sign*pitch), now_s=stamp, enable=True)
                self.assertTrue(out['pole_hold'])
                self.assertEqual(out['yaw_deg'], 30.)
            out = tracker.update(source(.4, 90, sign*79), now_s=.4, enable=True)
            self.assertFalse(out['pole_hold'])
            self.assertAlmostEqual(out['yaw_deg'], 33.)

    def test_stale_invalid_future_and_scheduling_gap_stop(self):
        for packet, now in ((source(.1, valid=False), .1),
                            (source(.2), .1), (source(0., valid_until_s=.1), .1),
                            (source(.1, vector=(0, 0, 0)), .1),
                            (source(.1, vector=(math.nan, 0, 1)), .1),
                            (source(.1, valid_until_s=math.inf), .1),
                            (source(.1, target_id=''), .1),
                            (source(2.), 2.)):
            out = self.tracker().update(packet, now_s=now, enable=True)
            self.assertFalse(out['command_valid'])
            self.assertIsNone(out['yaw_deg'])
            self.assertIsNone(out['pitch_deg'])

    def test_no_motion_budget_accumulates_while_invalid(self):
        tracker = self.tracker()
        tracker.update(source(.1, 90), now_s=.1, enable=True)
        tracker.update(source(.2, valid=False), now_s=.2, enable=True)
        out = tracker.update(source(.3, 90), now_s=.3, enable=True)
        self.assertAlmostEqual(out['yaw_deg'], 6.)

    def test_source_time_and_hold_expiry_cannot_go_back_or_extend(self):
        tracker = self.tracker()
        tracker.update(source(.1, 90), now_s=.1, enable=True)
        for packet, now in ((source(.09), .2), (source(.1, valid_until_s=.7), .3)):
            out = tracker.update(packet, now_s=now, enable=True)
            self.assertFalse(out['command_valid'])
        out = tracker.update(source(.1, 90), now_s=.4, enable=True)
        self.assertTrue(out['command_valid'])
        self.assertFalse(tracker.update(source(.1), now_s=.6, enable=True)['command_valid'])

    def test_same_observation_vector_is_immutable_during_hold(self):
        tracker = self.tracker()
        packet = source(.1, vector=(0., 1., 0.), fresh=True)
        first = tracker.update(packet, now_s=.1, enable=True)
        self.assertAlmostEqual(first['yaw_deg'], 3.)
        forged = dict(packet, vector=(0., -1., 0.), fresh=False)
        rejected = tracker.update(forged, now_s=.2, enable=True)
        self.assertFalse(rejected['command_valid'])
        self.assertEqual(rejected['reason'], 'source_vector_changed')
        self.assertIsNone(rejected['yaw_deg'])
        self.assertIsNone(rejected['pitch_deg'])
        # Same normalized vector is a legitimate repeated HOLD observation;
        # neither the rejected call nor HOLD rewrites its capture/expiry time.
        held = tracker.update(dict(packet, vector=(0., 2., 0.), fresh=False),
                              now_s=.3, enable=True)
        self.assertTrue(held['command_valid'])
        self.assertAlmostEqual(held['yaw_deg'], 6.)
        changed = tracker.update(source(.4, vector=(0., -1., 0.)),
                                 now_s=.4, enable=True)
        self.assertTrue(changed['command_valid'])
        self.assertAlmostEqual(changed['yaw_deg'], 3.)

    def test_context_change_retains_known_pose_not_old_pole(self):
        tracker = self.tracker(max_yaw_rate_deg_s=100.)
        tracker.update(source(.1, 0, 90), now_s=.1, enable=True)
        out = tracker.update(source(.2, 90, 83, target_id='new'), now_s=.2, enable=True)
        self.assertFalse(out['pole_hold'])
        self.assertAlmostEqual(out['yaw_deg'], 10.)

    def test_configuration_rejects_reflection_nonrotation_and_unsafe_ranges(self):
        for kw in ({'rotation': ((-1, 0, 0), (0, 1, 0), (0, 0, 1))},
                   {'rotation': ((1, 0, 0), (0, 2, 0), (0, 0, 1))},
                   {'rotation': ((1, 0),)}, {'rotation': None},
                   {'rotation': ((math.nan, 0, 0), (0, 1, 0), (0, 0, 1))},
                   {'yaw_limits_deg': (10, 10)}, {'yaw_limits_deg': (-400, 400)},
                   {'pitch_limits_deg': (-100, 90)}, {'max_yaw_rate_deg_s': 0},
                   {'max_pitch_rate_deg_s': math.inf}, {'pole_exit_deg': 86},
                   {'pole_enter_deg': 90}, {'target_timeout_s': -1}):
            with self.assertRaises(ValueError):
                axis_config(**kw)
        with self.assertRaises(ValueError):
            DualAxisTracker(axis_config(), initial_yaw_deg=181.,
                            initial_pitch_deg=0., initial_time_s=0.)

    def test_reproducible_chain_filter_to_axis_with_expiry(self):
        def run():
            filt, tracker, outputs = DirectionFilter3D(), self.tracker(), []
            for seq in range(1, 30):
                stamp = seq*.02
                packet = update(filt, seq, 179 if seq % 2 else -179, 25.)
                outputs.append(tracker.update(packet, now_s=stamp, enable=True))
            expired = filt.poll(now_s=.9)
            outputs.append(tracker.update(expired, now_s=.9, enable=True))
            return outputs
        a, b = run(), run()
        self.assertEqual(a, b)
        self.assertTrue(a[-2]['command_valid'])
        self.assertFalse(a[-1]['command_valid'])
        self.assertIsNone(a[-1]['yaw_deg'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
