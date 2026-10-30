"""Bounded ownership and invalidation tests with independent expected outcomes."""
import json
from pathlib import Path
import sys
import threading
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'software/ps/speaker_core'))
from stream_bench import Latest,Cache,reference_check


class SchedulerTests(unittest.TestCase):
    def test_only_latest_survives(self):
        m=Latest()
        for n in range(100):m.put({'id':n})
        self.assertEqual(m.take()['id'],99)
        self.assertEqual((m.generated,m.replaced),(100,99))
        m.finish();self.assertIsNone(m.take())

    def test_inflight_immutable_and_one_pending(self):
        m=Latest();m.put({'id':1});running=m.take()
        for n in range(2,10):m.put({'id':n})
        self.assertEqual(running,{'id':1});self.assertEqual(m.take()['id'],9)
        self.assertEqual(m.replaced,7)

    def test_expiry_and_silence_and_restart(self):
        m=Latest();c=Cache();c.active=True;c.voice_epoch=3;m.update_voice(c)
        job={'voice_epoch':3}
        self.assertEqual(m.validity(job,1.99),'fresh')
        self.assertEqual(m.validity(job,2.01),'expired')
        c.active=False;c.voice_epoch=4;m.update_voice(c)
        self.assertEqual(m.validity(job,.1),'speech_state_changed')
        c.active=True;c.voice_epoch=5;m.update_voice(c)
        self.assertEqual(m.validity(job,.1),'speech_state_changed')

    def test_front_error_discards_pending(self):
        m=Latest();m.put({'id':1});m.finish('input_failed')
        self.assertIsNone(m.pending)
        with self.assertRaisesRegex(RuntimeError,'input_failed'):m.take()
        self.assertEqual(m.validity({'voice_epoch':0},0),'frontend_failed')

    def test_done_wakes_consumer(self):
        m=Latest();out=[];t=threading.Thread(target=lambda:out.append(m.take()))
        t.start();m.finish();t.join(1)
        self.assertFalse(t.is_alive());self.assertEqual(out,[None])

    def test_reference_canaries(self):
        job={'frames':98,'coverage':.75}
        for ref in ({'frames':99,'coverage':.75,'score':.8},{'frames':98,'coverage':.7,'score':.8},{'frames':98,'coverage':.75,'score':.4}):
            with self.assertRaises(ValueError):reference_check(job,ref,.8)

    def test_cache_rejects_bad_packets(self):
        c=Cache()
        for packet in ([],[512.,4.,float('nan')]+[0.]*832,[512.,1.,0.]+[0.]*511):
            with self.assertRaises(ValueError):c.push(packet)

if __name__=='__main__':unittest.main()
