"""CF1 snapshot-gap policy regressions; synthetic PCM, no board actions."""
import copy
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
for folder in ('software/ps', 'software/ps/speaker_core', 'software/tests',
               'software/tetra3d/linux', 'software/tetra3d/tests'):
    sys.path.insert(0, str(ROOT/folder))
import test_cf1 as cf1
from filter_3d import SpatialFilter
from runtime_3d import State3D, display
from direction_diagnostics import DirectionDiagnostics
from client_3d import ThreeDClient
from test_online_3d import result as numeric_result, config


def observation(i, previous=None, now=10., valid=True):
    frame = cf1.frame(i)
    r = numeric_result(30, 20, valid)
    r.update(frontend='CF1A', source_completed_at=now, norm=1., residual_rms_samples=.1,
        pcm_continuity=dict(policy='CF1_PCM_GAPS_V1', epoch=7, sample_start=i*512,
            sequence=i+1, verified=previous is not None,
            previous_start=None if previous is None else previous*512,
            previous_sequence=None if previous is None else previous+1))
    return frame, r


class PCMGapTests(unittest.TestCase):
    def test_real_frontend_skipping_every_other_snapshot_produces_groups(self):
        source = cf1.NumericTests()
        pcm, _ = source.plane(30, 20, blocks=96)
        solver = source.solver()
        old = SpatialFilter(5, 2)
        new = SpatialFilter(5, 2, True, clock=lambda: 10.)
        old_groups = new_groups = bridged = 0
        for i in range(96):
            solver.accept_packet(*cf1.packet(i, pcm[i*512:(i+1)*512]))
            if i % 2 != 1:
                continue
            fr = cf1.frame(i-1)
            result = solver.solve(fr)
            old_groups += int(old.apply(fr, result, 12000)['direction_output']['valid'])
            row = new.apply(fr, result, 12000)
            bridged += int(row['angle_filter']['gap_bridged'])
            if row['direction_output']['valid']:
                new_groups += 1
                self.assertAlmostEqual(row['direction_output']['azimuth_deg'], 30, delta=2)
                self.assertAlmostEqual(row['direction_output']['elevation_deg'], 20, delta=2)
                self.assertEqual(row['angle_filter']['frame_count'], 5)
        self.assertEqual(old_groups, 0)
        self.assertGreater(new_groups, 3)
        self.assertGreater(bridged, 30)
        print('SYNTHETIC_GAP_COMPARISON old_groups=%d new_groups=%d bridged=%d' %
              (old_groups, new_groups, bridged))

    def test_frontend_missing_or_clipped_intermediate_block_cannot_prove_link(self):
        source = cf1.NumericTests(); pcm, _ = source.plane(30, blocks=20)
        for missing in (False, True):
            solver = source.solver()
            for i in range(20):
                solver.accept_packet(*cf1.packet(i, pcm[i*512:(i+1)*512], clipped=(i == 17 and not missing)))
                if i == 16:
                    solver.solve(cf1.frame(15))
            if missing:
                del solver.blocks[17*512]
            r = solver.solve(cf1.frame(18))
            self.assertFalse(r['pcm_continuity']['verified'])
            self.assertEqual(r['history_frames'], 1)

    def test_unverified_epoch_reverse_long_gap_and_missing_proof_reset(self):
        for case in ('unverified', 'epoch', 'reverse', 'long', 'missing', 'wrong_previous'):
            with self.subTest(case=case):
                filt = SpatialFilter(5, 2, True, clock=lambda: 10.)
                filt.apply(*observation(10), 12000)
                fr, r = observation(12, 10)
                if case == 'unverified': r['pcm_continuity']['verified'] = False
                if case == 'epoch':
                    fr['audio']['epoch'] = r['pcm_continuity']['epoch'] = 8
                if case == 'reverse': fr, r = observation(9, 10)
                if case == 'long': fr, r = observation(27, 10)
                if case == 'missing': del r['pcm_continuity']
                if case == 'wrong_previous': r['pcm_continuity']['previous_sequence'] = 2
                row = filt.apply(fr, r, 12000)
                self.assertTrue(row['angle_filter']['reset_reason'])
                self.assertFalse(row['direction_output']['valid'])
                self.assertLessEqual(row['angle_filter']['frame_count'], 1)

    def test_stale_future_and_whole_group_age_limits(self):
        for stale in (9., 10.1):
            filt = SpatialFilter(5, 2, True, clock=lambda: 10.)
            row = filt.apply(*observation(0, now=stale), 12000)
            self.assertEqual(row['direction_output']['reason'], 'pcm_window_stale')
        for clock_advance, source_step in ((.2, 2), (.01, 15)):
            now = [10.]
            filt = SpatialFilter(10, 2, True, clock=lambda: now[0])
            previous = None; resets = []
            for n in range(8):
                i = n*source_step
                row = filt.apply(*observation(i, previous, now=now[0]), 12000)
                resets.append(row['angle_filter']['reset_reason'])
                previous = i; now[0] += clock_advance
            self.assertIn('window_age_limit', resets)

    def test_low_volume_fault_and_norm_residual_still_reject(self):
        for kind in ('quiet', 'fault', 'norm', 'residual'):
            filt = SpatialFilter(3, 2, True, clock=lambda: 10.)
            previous = None
            for i in (0, 2, 4):
                fr, r = observation(i, previous)
                if kind == 'quiet': fr['energy'] = 1
                if kind == 'fault': fr['fault'] = 8
                if kind in ('norm', 'residual'):
                    r.update(direction_valid=0, reason=4 if kind == 'norm' else 3)
                row = filt.apply(fr, r, 12000)
                previous = i
            self.assertFalse(row['direction_output']['valid'])
            self.assertEqual(row['angle_filter']['valid_count'], 0)

    def test_minimum_consensus_and_deadband_unchanged(self):
        filt = SpatialFilter(3, 2, True, clock=lambda: 10.)
        previous = None
        for group, headings in enumerate(((30, 30, 100), (31, 31, 100), (0, 100, -100))):
            for n, az in enumerate(headings):
                i = (group*3+n)*2
                fr, r = observation(i, previous)
                r.update(numeric_result(az, 20))
                row = filt.apply(fr, r, 12000); previous = i
            self.assertEqual(row['direction_output']['valid'], group < 2)
            self.assertEqual(row['direction_output']['updated'], group == 0)
        filt = SpatialFilter(3, 3, True, clock=lambda: 10.)
        for i in range(3):
            fr, r = observation(i*2, None if i == 0 else (i-1)*2, valid=i != 1)
            row = filt.apply(fr, r, 12000)
        self.assertFalse(row['direction_output']['valid'])

    def test_permission_and_raw_hardware_pairs_still_block_motion(self):
        for permission in (False, True):
            ip = Mock(); ip.read.return_value = 0
            solver = Mock(); solver.requires_pcm = True
            client = ThreeDClient(ip, solver, 12000, 1, 1, 3, verified_pcm_gaps=True)
            client.frame_stale = lambda: False
            client.axes = Mock(); client.axes.read.return_value = 0
            client.speaker_permission = Mock()
            client.speaker_permission.snapshot.return_value = dict(permit=permission, reason='DENIED')
            fr, r = observation(0)
            fr['words'] = [0]*30
            row = dict(frame=fr, result=r)
            filt = SpatialFilter(1, 1, True, clock=lambda: 10.)
            row.update(filt.apply(fr, r, 12000))
            self.assertTrue(row['direction_output']['valid'])
            client.apply_motion(row)
            self.assertFalse(row['motion']['committed'])
            client.axes.commit.assert_not_called()
            self.assertEqual(row['motion']['reason'],
                'INSUFFICIENT_RAW_PAIRS_FOR_HARDWARE_FOLLOW' if permission else 'SPEAKER_DENIED')

    def test_verified_gap_group_can_reach_dual_axis_commit_with_permission(self):
        ip = Mock(); ip.read.return_value = 0
        solver = Mock(); solver.requires_pcm = True
        client = ThreeDClient(ip, solver, 12000, 5, 2, 3, config(), verified_pcm_gaps=True)
        client.axes = Mock(); client.axes.read.return_value = 0
        client.axes.arm.side_effect = lambda follow, permit_check: permit_check()
        client.axes.commit.side_effect = lambda target, sequence, permit_check: permit_check()
        client.speaker_permission = Mock()
        client.speaker_permission.allowed.return_value = True
        client.speaker_permission.snapshot.return_value = dict(permit=True, reason='PASS')
        filt = SpatialFilter(5, 2, True, clock=lambda: 10.)
        for n in range(5):
            fr, r = observation(n*2, None if n == 0 else (n-1)*2)
            client.frame_read_started_at = time.monotonic()
            row = dict(frame=fr, result=r)
            row.update(filt.apply(fr, r, 12000))
            client.apply_motion(row)
        self.assertTrue(row['motion']['committed'])
        self.assertEqual(row['motion']['targets'], {'horizontal': 210, 'vertical': 130})
        self.assertEqual(client.axes.commit.call_count, 1)

    def test_diagnostics_bounded_exclude_tail_and_expose_raw_reject(self):
        state = State3D(direction_diagnostics=True)
        filt = SpatialFilter(3, 2, True, clock=lambda: 10.)
        for n in range(3000):
            fr, r = observation(n*2, None if n == 0 else (n-1)*2, valid=False)
            r.update(reason=4, norm=.38, residual_rms_samples=.28)
            row = dict(frame=fr, result=r)
            row.update(filt.apply(fr, r, 12000))
            state.accept(row)
        state.tail = True; state.accept(row)
        data = state.snapshot('stopped')['direction_diagnostics']
        self.assertEqual(data['frames'], 3000)
        self.assertEqual(data['bridged_gaps'], 2999)
        self.assertEqual(data['completed_groups'], 1000)
        self.assertEqual(data['accepted_groups'], 0)
        self.assertEqual(len(data['by_solver_reason']['NORM']['examples']), 2)
        self.assertAlmostEqual(data['by_solver_reason']['NORM']['norm']['minimum'], .38)
        self.assertNotIn('direction_diagnostics', state.snapshot())
        self.assertIn('RAW_REASON=NORM', display(state.snapshot()))
        self.assertLess(len(json.dumps(data)), 6000)
        table = {}
        for i in range(10000): DirectionDiagnostics.count(table, str(i))
        self.assertLessEqual(len(table), 25)
        self.assertEqual(sum(table.values()), 10000)


if __name__ == '__main__': unittest.main(verbosity=2)
