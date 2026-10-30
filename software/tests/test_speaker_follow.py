"""Delayed identity gate and joint ownership tests; no PYNQ or hardware."""
import json
from collections import deque
import array
import math
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
for folder in ('software/ps', 'software/tests', 'software/tetra3d/linux', 'software/tetra3d/tests'):
    sys.path.insert(0, str(ROOT/folder))
from speaker_permission import SpeakerPermission, settings, load_settings
from speaker_follow_setup import configure
from live_speaker_follow import LatestEvents, FollowSpeaker
from stream_bench import Latest
from speaker_capture_3d import capture_joint
from test_pcm_capture import Audio, DMA, Clock
from test_online_3d import AxisModel, config as calibration, result as solved
from client_3d import ThreeDClient
from runtime_3d import State3D
from ps_client import FAULT
import ps_client as hw
import motion_3d
import board_3d


class GateTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.
        self.gate = SpeakerPermission(settings(.65, 3.), lambda: self.now)
        self.gate.start(7)
        self.voice()

    def voice(self, active=True, epoch=1):
        self.gate.event(dict(kind='voice', epoch=7, voice_epoch=epoch, active=active, at=self.now))

    def result(self, score=.65, **extra):
        value = dict(kind='result', epoch=7, voice_epoch=1, completed_at=self.now,
                     score=score, usable=True, start_sample16=16000)
        value.update(extra)
        self.gate.event(value)

    def test_exact_score_threshold_and_time_boundary(self):
        self.result()
        self.assertTrue(self.gate.allowed())
        self.now = 12.999
        self.voice()
        self.assertTrue(self.gate.allowed())
        self.now = 13.
        self.voice()
        self.assertFalse(self.gate.allowed())
        self.assertEqual(self.gate.reason, 'EXPIRED')

    def test_inference_in_progress_does_not_extend_or_remove_previous_pass(self):
        self.result(.8)
        for n in range(1, 7):
            self.now = 10.+n*.4
            self.voice()
            self.assertTrue(self.gate.allowed())
            self.assertEqual(self.gate.expires_at, 13.)

    def test_completion_time_not_receipt_time(self):
        self.now = 13.1
        self.voice()
        self.result(.9, completed_at=10.)
        self.assertFalse(self.gate.allowed())

    def test_new_low_score_preserves_old_pass_without_refresh(self):
        self.result(.9)
        self.now += .1
        self.result(.64999)
        self.assertTrue(self.gate.allowed())
        self.assertEqual(self.gate.expires_at, 13.)

    def test_unconfigured_cannot_grant_even_high_score(self):
        self.gate = SpeakerPermission(settings(), lambda: self.now)
        self.gate.start(7)
        self.voice(); self.result(1.)
        self.assertFalse(self.gate.allowed())
        self.assertEqual(self.gate.reason, 'UNCONFIGURED')

    def test_silence_new_speech_and_low_volume_preserve_ttl(self):
        self.result(.9)
        self.now += .01
        self.voice(False, 2)
        self.gate.quiet(20000)
        self.assertTrue(self.gate.allowed())
        self.assertEqual(self.gate.expires_at, 13.)
        self.voice(True, 3)
        # The old speech segment's result still refreshes from completion.
        self.result(.9, voice_epoch=1, start_sample16=0)
        self.assertTrue(self.gate.allowed())
        self.assertEqual(self.gate.expires_at, 13.01)

    def test_voice_heartbeat_age_is_not_a_second_expiry(self):
        self.result(.9)
        self.now += .501
        self.assertTrue(self.gate.allowed())
        self.now = 13.
        self.assertFalse(self.gate.allowed())

    def test_refresh_then_low_and_no_score_expire_at_last_pass(self):
        self.result(.9)
        self.now = 12.9
        self.result(.7)
        self.assertEqual(self.gate.expires_at, 15.9)
        self.now = 14.
        self.result(.2)
        self.now = 15.
        self.result(None, usable=False, reason='insufficient_speech')
        self.assertTrue(self.gate.allowed())
        self.assertEqual(self.gate.expires_at, 15.9)
        self.now = 15.9
        self.assertFalse(self.gate.allowed())
        self.now = 16.
        self.result(.9)
        self.assertTrue(self.gate.allowed())
        self.assertEqual(self.gate.expires_at, 19.)

    def test_no_voice_event_required_to_grant(self):
        self.gate = SpeakerPermission(settings(.65), lambda: self.now)
        self.gate.start(7)
        self.result(.9)
        self.assertTrue(self.gate.allowed())

    def test_wrong_session_unusable_nan_future_replay_are_rejected(self):
        for extra in (dict(epoch=8), dict(score=float('nan')),
                      dict(completed_at=11.), dict(completed_at=9.)):
            self.setUp(); self.result(.9); self.now += .01
            self.result(**extra)
            self.assertFalse(self.gate.allowed(), extra)

    def test_legacy_settings_preserve_threshold_and_ttl(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = dict(settings(.45, 10.), policy='delayed_permission_v1')
            path = Path(tmp)/'speaker-follow.local.json'
            path.write_text(json.dumps(old))
            migrated = load_settings(tmp)
            self.assertEqual(migrated['policy'], 'score_ttl_v2')
            self.assertEqual((migrated['threshold'], migrated['permit_seconds']), (.45, 10.))
            self.assertEqual(json.loads(path.read_text()), old)

    def test_mailbox_pass_survives_later_low_or_skipped_result(self):
        for low in (.1, None):
            self.setUp()
            mail = LatestEvents(.65)
            mail.publish(dict(kind='result', epoch=7, voice_epoch=1, completed_at=10.,
                              score=.9, usable=True))
            mail.publish(dict(kind='result', epoch=7, voice_epoch=2, completed_at=10.1,
                              score=low, usable=low is not None, reason='insufficient_speech'))
            self.now = 10.2
            rows = mail.take()
            self.assertEqual(len(rows), 2)
            for row in rows: self.gate.event(row)
            self.assertTrue(self.gate.allowed())
            self.assertEqual(self.gate.expires_at, 13.)
            self.assertEqual(mail.take(), [])

    def test_settings_missing_and_persistence_do_not_imply_calibrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_settings(tmp)['threshold'])
            configure(tmp, .65, 3.)
            self.assertEqual(load_settings(tmp)['threshold'], .65)
            self.assertFalse(load_settings(tmp)['recognition_qualified'])
            configure(tmp, disable=True)
            self.assertIsNone(load_settings(tmp)['threshold'])
        for t in (True, float('inf'), -2, 2):
            with self.assertRaises(ValueError): settings(t)
        for ttl in (0, 31, float('nan')):
            with self.assertRaises(ValueError): settings(.65, ttl)

    def test_events_are_bounded_and_silence_revision_survives_overwrite(self):
        mail = LatestEvents()
        for i in range(10000):
            mail.publish(dict(kind='voice', voice_epoch=i, active=bool(i % 2)))
            mail.publish(dict(kind='result', sequence=i))
        rows = mail.take()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['voice_epoch'], 9999)
        self.assertEqual(mail.take(), [])


class TimedAxes(AxisModel):
    def read(self, offset):
        if offset == hw.FEATURE:
            return 0x110c2800 | self.pair << 8
        if offset == hw.STATUS:
            return super().read(offset) | 0x10
        return {0x84: 7, 0x88: (self.sequence-1)*512, 0x8c: 0,
                0x90: self.sequence, 0x94: 0x10000 | 1024}.get(offset, super().read(offset))


class JointDMA(DMA):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inflight = self.exposed = False

    def reset(self):
        super().reset()
        self.inflight = self.exposed = False

    def submit(self):
        if self.inflight: raise RuntimeError('overwrite in-flight DMA')
        super().submit(); self.inflight = self.exposed = True

    def take(self):
        data = super().take()
        self.inflight = False
        return data


class SpeakerStub:
    def __init__(self, clock, mode='pass'):
        self.clock, self.mode, self.count = clock, mode, 0
        self.fail_at = None

    def started(self, at): self.origin = at

    def submit(self, data, meta):
        assert meta['block_seq'] == self.count
        self.count += 1

    def poll_events(self):
        if self.fail_at is not None and self.count >= self.fail_at:
            raise RuntimeError('injected worker loss')
        now = self.clock()
        values = [dict(kind='voice', epoch=7, voice_epoch=1, active=True, at=now)]
        if self.mode == 'pass':
            values.append(dict(kind='result', epoch=7, voice_epoch=1, completed_at=now,
                               usable=True, score=.8, start_sample16=9999999))
        return values


class JointTests(unittest.TestCase):
    def run_joint(self, *, threshold=.65, mode='pass', failure=None, axes=3, fail_at=None, low=False, limit=12):
        timer = Clock()
        device = TimedAxes()
        device.low = low
        client = ThreeDClient(device, Mock(solve=lambda f: solved()), 7000, 3, 3, axes, calibration())
        audio = Audio()
        dma = JointDMA(audio, failure)
        speaker = SpeakerStub(timer, mode)
        speaker.fail_at = fail_at
        state = State3D()
        with patch('os.fsync', side_effect=AssertionError('No fsync during capture')):
            report = capture_joint(client, audio, dma, speaker, 7, state, settings(threshold),
                                   frames=limit, clock=timer, sleep=timer.sleep)
        return report, device, client, speaker

    def test_two_keys_enable_and_stop_drains_without_motion_after_stop(self):
        report, device, client, speaker = self.run_joint()
        self.assertEqual(report['result'], 'PASS', report)
        self.assertEqual(report['stats']['consumed'], 12)
        self.assertGreater(report['stats']['motion_commits'], 0)
        self.assertFalse(device.active)
        self.assertFalse(device.reg[motion_3d.STATE] & 1)
        self.assertTrue(report['dma_halted'])
        self.assertFalse(report['speaker_permission']['permit'])
        self.assertEqual(speaker.count, report['packets'])

    def test_unconfigured_no_result_off_or_quiet_never_commit(self):
        for options in (dict(threshold=None), dict(mode='waiting'), dict(axes=0), dict(low=True)):
            report, device, _, _ = self.run_joint(**options)
            self.assertEqual(report['result'], 'PASS', report)
            self.assertEqual(report['stats']['motion_commits'], 0)
            self.assertNotIn((motion_3d.COMMAND, 3), device.writes)

    def test_dma_gap_overflow_timeout_and_worker_loss_stop(self):
        for options in (dict(failure='gap'), dict(failure='dma'), dict(failure='overflow'),
                        dict(failure='timeout', limit=100), dict(fail_at=5)):
            report, device, client, _ = self.run_joint(**options)
            self.assertEqual(report['result'], 'FAIL', report)
            self.assertFalse(device.active)
            self.assertFalse(device.reg[motion_3d.STATE] & 1)
            self.assertTrue(report['dma_halted'])

    def test_failed_dma_reset_is_not_claimed_halted(self):
        report, device, _, _ = self.run_joint(failure='reset')
        self.assertEqual(report['result'], 'FAIL')
        self.assertFalse(report['dma_halted'])
        self.assertTrue(report['cleanup_errors'])

    def test_long_session_uses_constant_retention(self):
        report, _, _, _ = self.run_joint(limit=3000, axes=0)
        self.assertEqual(report['stats']['consumed'], 3000)
        self.assertNotIn('records', report)
        self.assertLess(len(json.dumps(report)), 20000)

    def test_metadata_mismatch_retains_locked_frame_and_revokes(self):
        device = TimedAxes()
        client = ThreeDClient(device, Mock(solve=lambda f: solved()), 7000)
        client.start(clear_faults=0x40)
        client.expected_audio_epoch = 99
        with self.assertRaisesRegex(RuntimeError, 'session mismatch'):
            client.record_one(lambda r: None)
        self.assertTrue(device.locked)
        self.assertFalse(device.active)

    def test_cli_modes_keep_manual_independent_and_axes_opt_in(self):
        parser = board_3d.parser()
        a = parser.parse_args(['speaker', '--seconds', '30'])
        self.assertEqual(a.axes, 'off')
        a = parser.parse_args(['speaker-config', '0.65', '--ttl', '3'])
        self.assertEqual(a.threshold, .65)
        a = parser.parse_args(['manual', '--horizontal', '185'])
        self.assertFalse(hasattr(a, 'threshold'))
        with patch.object(board_3d, 'Solver3D'), patch.object(board_3d, 'load_config', return_value=calibration()):
            a = board_3d.run_options(parser.parse_args(['run', '--axes', 'both', '--min-level', '7000']))
            self.assertEqual((a.command, a.seconds), ('speaker', 0.))
            a = board_3d.run_options(parser.parse_args(['run', '--min-level', '7000']))
            self.assertEqual(a.command, 'run')

    def test_gate_expiry_during_arm_or_shadow_write_never_commits(self):
        for expire_on in (motion_3d.COMMAND, motion_3d.TARGET, motion_3d.FRAME):
            device = TimedAxes()
            client = ThreeDClient(device, Mock(solve=lambda f: solved()), 7000, 3, 3, 3, calibration())
            client.start(clear_faults=0x40)
            now = [10.]
            gate = SpeakerPermission(settings(.65, 3.), lambda: now[0])
            gate.start(7)
            gate.event(dict(kind='voice', epoch=7, voice_epoch=1, active=True, at=10.))
            gate.event(dict(kind='result', epoch=7, voice_epoch=1, usable=True, score=.9,
                            completed_at=7.001, start_sample16=0))
            client.speaker_permission = gate
            original = device.write
            def write(address, value):
                original(address, value)
                if address == expire_on:
                    now[0] = 10.002
            device.write = write
            records = []
            for _ in range(3): client.record_one(records.append)
            self.assertNotIn((motion_3d.COMMAND, 3), device.writes, expire_on)
            self.assertFalse(device.reg[motion_3d.STATE] & 1)
            self.assertFalse(records[-1]['motion']['committed'])

    def test_insufficient_raw_pairs_never_reach_hardware_commit(self):
        good = 0x110c2800
        words = []
        for n in range(6): words.extend([good if n < 3 else 0, 1, 1, 1, 1])
        self.assertFalse(ThreeDClient.hardware_follow_qualified(dict(status=0x31, words=words)))
        words[15] = good
        self.assertTrue(ThreeDClient.hardware_follow_qualified(dict(status=0x31, words=words)))
        self.assertFalse(ThreeDClient.hardware_follow_qualified(dict(status=0x39, words=words)))


class PipelineTests(unittest.TestCase):
    def infer(self, duration=3.2, change_voice=False, frames=98, start_age=0., collect_statistics=False):
        value = FollowSpeaker.__new__(FollowSpeaker)
        now = [1.+start_age]
        value.clock = lambda: now[0]
        value.origin = 0.
        value.stop = threading.Event()
        value.mail = Latest()
        value.mail.active = True
        value.mail.voice_epoch = 1
        value.mail.put(dict(epoch=7, voice_epoch=1, end_sample16=16000, start_sample16=0,
                            frames=frames, features=array.array('f', [0.]*7840), active=True,
                            coverage=1., window_seconds=1.))
        value.mail.finish()
        value.config = dict(template=[1.]+[0.]*191, target_id='P02', score_only=True)
        value.completed_rows = deque(maxlen=32)
        value.completed_count = 0
        from speaker_statistics import SpeakerStatistics
        value.statistics = SpeakerStatistics(.65) if collect_statistics else None
        value.error = None
        value.error_lock = threading.Lock()
        rows = []
        value.event_sink = rows.append
        def calculate(op, data):
            now[0] += duration
            if change_voice:
                value.mail.active = False
                value.mail.voice_epoch = 2
            return [1.]+[0.]*191
        value.embed = Mock()
        value.embed.run.side_effect = calculate
        value._infer()
        return value, rows

    def test_new_delayed_mode_accepts_older_than_two_seconds_without_altering_profile(self):
        engine, rows = self.infer()
        self.assertIsNone(engine.error)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['usable'])
        self.assertGreater(rows[0]['source_age_seconds'], 2.)
        self.assertTrue(rows[0]['profile_score_only'])
        self.assertEqual(rows[0]['target_id'], 'P02')
        self.assertFalse(rows[0]['recognition_qualified'])

    def test_mid_inference_silence_can_publish_usable_score(self):
        _, rows = self.infer(change_voice=True)
        self.assertTrue(rows[0]['usable'])
        self.assertEqual(rows[0]['reason'], 'scored')

    def test_old_waiting_window_is_scored_not_discarded_for_age(self):
        engine, rows = self.infer(start_age=4., change_voice=True)
        self.assertIsNone(engine.error)
        self.assertTrue(rows[0]['usable'])
        self.assertEqual(rows[0]['start_age_seconds'], 4.)

    def test_cp1_wrong_shape_fails_before_native_inference(self):
        engine, rows = self.infer(frames=99)
        self.assertIn('98x80', engine.error)
        engine.embed.run.assert_not_called()
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
