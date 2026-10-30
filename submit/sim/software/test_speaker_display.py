"""Score visibility is diagnostic; existing permission decisions stay authoritative."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for folder in ('software/ps', 'software/ps/speaker_core', 'software/tetra3d/linux'):
    sys.path.insert(0, str(ROOT/folder))
from speaker_permission import SpeakerPermission, settings
from live_speaker_follow import LatestEvents
from speaker_runtime_3d import display


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.
        self.gate = SpeakerPermission(settings(.65, 3.), lambda: self.now)
        self.gate.start(7)
        self.voice()

    def voice(self, ve=1, active=True):
        self.gate.event(dict(kind='voice', epoch=7, voice_epoch=ve, active=active, at=self.now))

    def result(self, **changes):
        value = dict(kind='result', epoch=7, voice_epoch=1, completed_at=self.now,
                     score=.8, usable=True, reason='scored', start_sample16=16000)
        value.update(changes)
        return value

    def line(self):
        with patch('speaker_runtime_3d.angle_display', return_value='ANGLE_STATUS\n'):
            return display({'speaker': self.gate.snapshot()})

    def test_board_reproducer_score_then_skipped_attempt_same_poll(self):
        mail = LatestEvents()
        mail.publish(self.result(score=.50180326, usable=False, reason='speech_state_changed'))
        self.now += .001
        mail.publish(self.result(score=None, usable=False, reason='stale_before_start'))
        for event in mail.take():
            self.gate.event(event)
        self.assertIsNone(self.gate.score)
        self.assertFalse(self.gate.allowed())
        self.assertIn('SPEAKER_SCORE=0.5018', self.line())
        self.assertIn('SCORE_USABLE_AT_COMPLETION=0 SCORE_REASON=SPEECH_STATE_CHANGED', self.line())
        self.assertIn('PERMIT_REASON=STALE_BEFORE_START', self.line())
        self.assertEqual(mail.take(), [])

    def test_skip_next_poll_retains_score_and_existing_permission(self):
        self.gate.event(self.result())
        self.assertTrue(self.gate.allowed())
        self.now += .1
        self.gate.event(self.result(score=None, usable=False, reason='stale_before_start'))
        self.assertTrue(self.gate.allowed())
        self.assertIn('SPEAKER_SCORE=0.8000', self.line())
        self.assertIn('SCORE_AGE=0.10s', self.line())

    def test_quiet_and_new_speech_keep_score_and_permission(self):
        self.gate.event(self.result())
        self.gate.quiet(20000)
        self.assertTrue(self.gate.allowed())
        self.voice(2, False)
        self.voice(3, True)
        self.assertTrue(self.gate.allowed())
        self.assertIn('SCORE_STATE=LAST_COMPLETED', self.line())
        self.assertIn('PERMIT=1', self.line())

    def test_expiry_and_missing_threshold_do_not_hide_score(self):
        self.gate.event(self.result())
        self.now = 13.
        self.voice()
        self.assertFalse(self.gate.allowed())
        self.assertIn('PERMIT_REASON=EXPIRED', self.line())
        self.gate = SpeakerPermission(settings(), lambda: self.now)
        self.gate.start(7); self.voice()
        self.gate.event(self.result())
        self.assertIn('SPEAKER_SCORE=0.8000', self.line())
        self.assertIn('PERMIT_REASON=UNCONFIGURED', self.line())

    def test_no_score_and_invalid_or_old_diagnostics(self):
        self.assertIn('SPEAKER_SCORE=NONE', self.line())
        self.gate.event(self.result())
        for changes in (dict(score=float('nan')), dict(score=True), dict(score=2.),
                        dict(epoch=8), dict(completed_at=11.), dict(completed_at=9.)):
            self.now = 10.1
            self.gate.event(self.result(**changes))
            self.assertEqual(self.gate.snapshot()['display_score'], .8)
            self.assertFalse(self.gate.allowed())

    def test_latest_numeric_replaces_old_and_storage_is_bounded(self):
        mail = LatestEvents()
        for i in range(10000):
            mail.publish(self.result(score=.4+i/100000., completed_at=i/1000.))
        rows = mail.take()
        self.assertEqual(len(rows), 1)
        self.gate.event(rows[0])
        self.assertAlmostEqual(self.gate.snapshot()['display_score'], .49999)
        self.assertIsNone(mail.scored_result)

    def test_invalid_nested_diagnostic_never_displays_or_grants(self):
        for value in (None, 'bad', self.result(epoch=8), self.result(completed_at=-2),
                      self.result(completed_at=11), self.result(score=float('nan'))):
            self.setUp()
            self.gate.event(self.result(score=None, usable=False, reason='stale_before_start',
                                       display_result=value))
            self.assertIsNone(self.gate.snapshot()['display_score'])
            self.assertFalse(self.gate.allowed())


if __name__ == '__main__':
    unittest.main()
