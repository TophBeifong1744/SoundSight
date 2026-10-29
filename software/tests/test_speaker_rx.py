"""Receiver ownership/fault boundaries and real Linux child scheduling; no MMIO."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'software/ps'))
sys.path.insert(0,str(ROOT/'software/tests'))
import pcm_capture as pcm
from speaker_scheduling import CaptureScheduling
from test_pcm_capture import Audio,Client,DMA,Clock,packet


class ReceiverTests(unittest.TestCase):
    def test_rearm_precedes_slow_decode_and_consumer_without_corrupting_copy(self):
        audio,client,timer=Audio(),Client(),Clock()
        class ReuseDMA(DMA):
            def submit(self):
                super().submit()
                self.buffer=bytearray(packet(seq=self.submitted-1))
            def take(self):
                self.audio.published+=1
                return bytes(self.buffer)
        dma=ReuseDMA(audio);decode=pcm.decode_packet;seen=[]
        def slow(data,epoch,seq):
            # The next hardware receive must already be armed before slow work.
            self.assertEqual(dma.submitted,min(seq+2,3))
            timer.sleep(.015)
            return decode(data,epoch,seq)
        def sink(data,meta):
            self.assertEqual(dma.submitted,min(meta['block_seq']+2,3))
            seen.append(data)
        with patch.object(pcm,'decode_packet',side_effect=slow):
            report,raw=pcm.capture(client,audio,dma,7,3,timer,timer.sleep,packet_sink=sink)
        self.assertEqual(report['result'],'PASS',report)
        self.assertEqual(raw,[packet(seq=i) for i in range(3)])
        self.assertEqual(seen,raw)
        self.assertEqual(report['receiver_timing']['early_rearms'],2)
        self.assertGreaterEqual(report['receiver_timing']['max_decode_seconds'],.015)
        self.assertLess(report['receiver_timing']['max_rearm_seconds'],.015)
        self.assertIsNone(report['first_fault'])

    def test_invalid_packet_after_rearm_stops_and_never_reaches_consumer(self):
        audio,client,timer=Audio(),Client(),Clock();dma=DMA(audio,'gap');seen=[]
        report,raw=pcm.capture(client,audio,dma,7,3,timer,timer.sleep,packet_sink=lambda *x:seen.append(x))
        self.assertEqual(dma.submitted,2)
        self.assertFalse(seen);self.assertEqual(len(raw),1)
        self.assertEqual(report['result'],'FAIL');self.assertTrue(report['dma_halted'])
        self.assertFalse(client.running)

    def test_fault_evidence_is_before_cleanup_stop_bit(self):
        audio,client,timer=Audio(),Client(),Clock()
        class OverflowDMA(DMA):
            def completed(self):
                if self.submitted==2:
                    audio.status|=256;client.fault|=8;return False
                return True
        report,_=pcm.capture(client,audio,OverflowDMA(audio),7,3,timer,timer.sleep)
        self.assertEqual(report['first_fault']['fault'],8)
        self.assertEqual(report['first_fault']['audio']['errors'],1)
        self.assertEqual(report['first_fault']['received_packets'],1)
        self.assertEqual(report['final_ps']['fault'],72)
        self.assertTrue(report['dma_halted']);self.assertFalse(client.running)

    def test_rearm_write_failure_still_keeps_raw_and_resets(self):
        audio,client,timer=Audio(),Client(),Clock()
        class FailureDMA(DMA):
            def submit(self):
                super().submit()
                if self.submitted==2:raise RuntimeError('injected LENGTH failure')
        dma=FailureDMA(audio)
        report,raw=pcm.capture(client,audio,dma,7,3,timer,timer.sleep)
        self.assertEqual(report['result'],'FAIL');self.assertEqual(len(raw),1)
        self.assertIn('LENGTH failure',report['error'])
        self.assertTrue(report['dma_halted']);self.assertEqual(dma.reset_count,2)

    def test_last_packet_has_no_extra_receive_and_sink_failure_stops(self):
        for failure in (False,True):
            audio,client,timer=Audio(),Client(),Clock();dma=DMA(audio)
            def sink(*args):
                if failure:raise RuntimeError('sink failure')
            report,_=pcm.capture(client,audio,dma,7,1,timer,timer.sleep,packet_sink=sink)
            self.assertEqual(dma.submitted,1)
            self.assertEqual(report['receiver_timing']['early_rearms'],0)
            self.assertTrue(report['dma_halted']);self.assertFalse(client.running)
            self.assertEqual(report['result'],'FAIL' if failure else 'PASS')


class SchedulingTests(unittest.TestCase):
    def test_actual_child_threads_affinity_and_nice_restored(self):
        original=set(os.sched_getaffinity(0));parent_nice=os.nice(0)
        with CaptureScheduling() as policy:
            self.assertEqual(set(os.sched_getaffinity(0)),{min(original)})
            code='import os,json,threading; out=[]; t=threading.Thread(target=lambda:out.append([sorted(os.sched_getaffinity(0)),os.nice(0)])); t.start(); t.join(); print(json.dumps(out[0]))'
            for role in ('front','embed'):
                result=json.loads(subprocess.check_output(policy.prefix(role)+[sys.executable,'-c',code]))
                self.assertEqual(result[0],policy.cpus if role=='embed' else [policy.cpus[1]])
                if role=='front':self.assertTrue(set(result[0]).isdisjoint(os.sched_getaffinity(0)))
                self.assertEqual(result[1],min(19,parent_nice+10) if role=='embed' else parent_nice)
        self.assertEqual(set(os.sched_getaffinity(0)),original)
        self.assertEqual(os.nice(0),parent_nice)

    def test_exception_restores_parent_affinity(self):
        original=set(os.sched_getaffinity(0))
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with CaptureScheduling():raise RuntimeError('injected')
        self.assertEqual(set(os.sched_getaffinity(0)),original)

    def test_missing_tool_or_single_cpu_fails_before_change(self):
        with patch('speaker_scheduling.os.sched_getaffinity',return_value={0}),patch('speaker_scheduling.os.sched_setaffinity') as change:
            with self.assertRaisesRegex(RuntimeError,'TWO_AVAILABLE'):CaptureScheduling().__enter__()
            change.assert_not_called()
        with patch('speaker_scheduling.os.sched_getaffinity',return_value={0,1}),patch('speaker_scheduling.shutil.which',return_value=None),patch('speaker_scheduling.os.sched_setaffinity') as change:
            with self.assertRaisesRegex(RuntimeError,'TASKSET'):CaptureScheduling().__enter__()
            change.assert_not_called()


if __name__=='__main__':unittest.main()
