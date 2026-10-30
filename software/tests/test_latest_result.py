"""Latest-result mode may skip READY frames; a delayed LOCKED frame cannot re-arm."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
for folder in ('software/ps', 'software/tests', 'software/tetra3d/linux', 'software/tetra3d/tests'):
    sys.path.insert(0, str(ROOT/folder))
from test_online_3d import AxisModel, result, config
from test_speaker_follow import TimedAxes
from client_3d import ThreeDClient
from speaker_permission import SpeakerPermission, settings
import motion_3d as motion


class FreshnessTests(unittest.TestCase):
    def scenario(self, delay, speaker=False, delayed_write=None, low_last=False):
        now = [10.]
        dev = TimedAxes() if speaker else AxisModel()
        count = [0]
        gate = SpeakerPermission(settings(.65, 10.), lambda: now[0]) if speaker else None
        if gate:
            gate.start(7)
            gate.event(dict(kind='voice', epoch=7, voice_epoch=1, active=True, at=now[0]))
            gate.event(dict(kind='result', epoch=7, voice_epoch=1, completed_at=now[0],
                            usable=True, score=.9, start_sample16=0))
        def solve(frame):
            count[0] += 1
            if count[0] == 3 and delayed_write is None:
                now[0] += delay
            if gate:
                gate.event(dict(kind='voice', epoch=7, voice_epoch=1, active=True, at=now[0]))
            return result()
        c = ThreeDClient(dev, Mock(solve=solve), 7000, 3, 3, 3, config())
        c.speaker_permission = gate
        original = dev.write
        def write(a, v):
            original(a, v)
            if a == delayed_write and (a != motion.COMMAND or v == 2):
                now[0] += delay
        dev.write = write
        rows=[]
        with patch('client_3d.time.monotonic', side_effect=lambda: now[0]):
            c.start(clear_faults=0x40)
            for index in range(3):
                dev.low = low_last and index == 2
                c.record_one(rows.append)
        return c, dev, rows, now

    def test_read_deadline_before_equal_after_for_both_modes(self):
        for speaker in (False, True):
            for delay in (.749, .750, .751):
                with self.subTest(speaker=speaker, delay=delay):
                    c,d,rows,now=self.scenario(delay,speaker)
                    committed=(motion.COMMAND,3) in d.writes
                    self.assertEqual(committed,delay<.75)
                    self.assertFalse(d.locked)
                    if delay>=.75:
                        self.assertEqual(rows[-1]['motion']['reason'],'STALE_LOCKED_FRAME')
                        self.assertEqual(c.spatial.count,0)
                        self.assertIsNone(c.target)
                        self.assertFalse(rows[-1]['direction_output']['valid'])

    def test_arm_and_shadow_stalls_do_not_commit(self):
        for speaker in (False, True):
            for register in (motion.COMMAND,motion.TARGET,motion.FRAME):
                with self.subTest(speaker=speaker, register=register):
                    c,d,rows,now=self.scenario(.75,speaker,register)
                    self.assertNotIn((motion.COMMAND,3),d.writes)
                    self.assertFalse(d.locked)
                    self.assertFalse(d.reg[motion.STATE]&1)
                    self.assertEqual(c.spatial.count,0)

    def test_stale_quiet_frame_blocks_motion_but_preserves_speaker_ttl(self):
        c,d,rows,now=self.scenario(.751, speaker=True, low_last=True)
        gate=c.speaker_permission
        self.assertTrue(gate.allowed())
        now[0]+=.01
        gate.event(dict(kind='voice',epoch=7,voice_epoch=1,active=True,at=now[0]))
        gate.event(dict(kind='result',epoch=7,voice_epoch=1,completed_at=now[0],
                        usable=True,score=.99,start_sample16=0))
        self.assertTrue(gate.allowed())
        self.assertEqual(gate.expires_at, now[0]+10.)
        self.assertNotIn((motion.COMMAND,3),d.writes)
        self.assertFalse(d.locked)

    def test_stall_revokes_previously_held_target(self):
        c,d,rows,now=self.scenario(0.)
        self.assertIsNotNone(c.target)
        d.writes.clear()
        def delayed(frame):
            now[0]+=.751
            return result()
        c.solver.solve=delayed
        with patch('client_3d.time.monotonic',side_effect=lambda:now[0]):
            c.record_one(rows.append)
        self.assertIsNone(c.target)
        self.assertFalse(d.reg[motion.STATE]&1)
        self.assertNotIn((motion.COMMAND,3),d.writes)
        self.assertFalse(d.locked)

    def test_expired_frame_needs_a_whole_new_window(self):
        c,d,rows,now=self.scenario(.751)
        with patch('client_3d.time.monotonic',side_effect=lambda:now[0]):
            for _ in range(2): c.record_one(rows.append)
            self.assertNotIn((motion.COMMAND,3),d.writes)
            c.record_one(rows.append)
            self.assertIn((motion.COMMAND,3),d.writes)
            self.assertEqual(c.target_time,c.frame_read_started_at)


if __name__ == '__main__':
    unittest.main()
