"""CF1 offline numerical/ownership checks. No PYNQ import or hardware action."""
import json
import os
from pathlib import Path
import struct
import sys
import time
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for folder in ('software/ps', 'software/ps/speaker_core', 'software/tests', 'software/tetra3d/linux', 'software/tetra3d/tests'):
    sys.path.insert(0, str(ROOT/folder))
from coherent_frontend import CoherentSolver
from solver_3d import Solver3D
from pcm_capture import decode_packet
from filter_3d import SpatialFilter
from test_speaker_follow import Clock, TimedAxes, Audio, JointDMA, solved, calibration, SpeakerStub, settings
from client_3d import ThreeDClient
from runtime_3d import State3D
from speaker_capture_3d import capture_joint

GEOMETRY = json.loads((ROOT/'software/tetra3d/core/tetra40-nominal.json').read_text())
HANN = ROOT/'software/tetra3d/linux/cf1_hann.mem'


def packet(i, pcm, clipped=False):
    raw = struct.pack('<8I', 0x43505353, 0x00200001, 7, i, i*512, 0,
                      512 | (int(clipped) << 16), 8192)+np.asarray(pcm, dtype='<i4').tobytes()
    return raw, decode_packet(raw, 7, i)


def frame(i):
    words = [v for p in range(6) for v in (0x110c2800 | p << 8, 0, 0, 0, 0)]
    return dict(sequence=i+1, status=0x20031, energy=20000, fault=0, drops=0, words=words,
                audio=dict(valid=True, epoch=7, sample_start=i*512, sample_count=1024))


class NumericTests(unittest.TestCase):
    def solver(self, clock=lambda: 10.):
        library = os.environ.get('CF1_TEST_LIBRARY', str(ROOT/'software/tetra3d/linux/libss_solver_3d.so'))
        return CoherentSolver(Solver3D(library, GEOMETRY), 7, HANN, clock)

    def plane(self, az, el=0, blocks=80):
        count=blocks*512
        f=np.fft.rfftfreq(count, 1/48000)
        rng=np.random.RandomState(122)
        spectrum=np.fft.rfft(rng.normal(size=count));spectrum[(f<400)|(f>3800)]=0
        a,e=np.radians([az,el]);u=np.array([np.cos(e)*np.cos(a),np.cos(e)*np.sin(a),np.sin(e)])
        xyz=np.array([r['xyz_mm'] for r in GEOMETRY['microphones']])
        phase=np.exp(2j*np.pi*f[:,None]*(xyz@u)[None,:]/343000)
        x=np.fft.irfft(spectrum[:,None]*phase,n=count,axis=0)
        return np.rint(x*(30000/np.std(x))).astype(np.int32),u

    def replay(self, solver, x):
        out=[]
        for i in range(len(x)//512):
            solver.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            if i:out.append(solver.solve(frame(i-1)))
        return out

    def test_known_pcm_directions_and_filter_output(self):
        for az,el in ((0,0),(180,0),(90,20)):
            x,u=self.plane(az,el);out=self.replay(self.solver(),x)
            filt=SpatialFilter(20,12);groups=0
            for i,r in enumerate(out):
                if i>=16:
                    self.assertTrue(r['direction_valid'],r)
                    v=np.array([r[k] for k in ('ux','uy','uz')]);v/=np.linalg.norm(v)
                    self.assertLess(np.degrees(np.arccos(np.clip(v@u,-1,1))),2)
                groups+=int(filt.apply(frame(i),r,12000)['direction_output']['valid'])
            self.assertGreater(groups,0)

    def test_silence_does_not_publish_direction(self):
        out=self.replay(self.solver(),np.zeros((512*24,4),np.int32))
        self.assertFalse(any(r['direction_valid'] for r in out))

    def test_missing_clipped_wrong_epoch_and_stale(self):
        s=self.solver();r=s.solve(frame(0));self.assertEqual(r['cf1_reset'],'pcm_window_not_received')
        self.assertEqual((r['api_status'],r['bridge_status']),(0,0))
        s=self.solver()
        zeros=np.zeros((512,4),np.int32)
        s.accept_packet(*packet(0,zeros));s.accept_packet(*packet(1,zeros,True))
        r=s.solve(frame(0));self.assertEqual(r['cf1_reset'],'pcm_clipped')
        self.assertEqual((r['api_status'],r['bridge_status']),(0,0))
        f=frame(0);f['audio']['epoch']=8
        self.assertFalse(s.solve(f)['direction_valid'])
        clock=[10.];s=self.solver(lambda:clock[0])
        s.accept_packet(*packet(0,zeros));s.accept_packet(*packet(1,zeros));clock[0]=11.
        self.assertEqual(s.solve(frame(0))['cf1_reset'],'pcm_window_stale')

    def test_packet_gap_fails_and_storage_bounded(self):
        s=self.solver();zeros=np.zeros((512,4),np.int32)
        s.accept_packet(*packet(0,zeros))
        with self.assertRaises(ValueError):s.accept_packet(*packet(2,zeros))
        for i in range(1,100):s.accept_packet(*packet(i,zeros))
        self.assertEqual(len(s.blocks),64)
        self.assertFalse(s.has_window(frame(0)))

    def test_snapshot_gap_keeps_continuous_pcm_history(self):
        x,_=self.plane(0,blocks=24);s=self.solver()
        for i in range(24):
            s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            if i:
                f=frame(i-1)
                if i>=12:f['sequence']+=3
                r=s.solve(f)
                if i==12:self.assertEqual(r['history_frames'],12)
        self.assertLessEqual(len(s.history),16)

    def test_skipped_snapshots_match_full_audio_history(self):
        x,_=self.plane(180,blocks=50)
        reference=self.replay(self.solver(),x);s=self.solver()
        for i in range(50):
            s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            if not i or i%6==0:continue
            r=s.solve(frame(i-1));expected=reference[i-1]
            self.assertEqual(r['reason'],expected['reason'])
            for key in ('ux','uy','uz'):
                self.assertAlmostEqual(r[key],expected[key],places=6)
        self.assertGreater(s.stats['backfilled_windows'],0)
        self.assertEqual(s.stats['resets'],0)

    def test_large_snapshot_gap_is_bounded_and_replay_rejected(self):
        x,_=self.plane(0,blocks=100);s=self.solver()
        for i in range(100):
            s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            if i==2:s.solve(frame(1))
        r=s.solve(frame(98))
        self.assertEqual(r['history_frames'],16)
        self.assertLessEqual(s.stats['max_windows_per_solve'],16)
        self.assertEqual(s.solve(frame(98))['cf1_reset'],'pcm_window_repeated_or_reversed')
        self.assertEqual(s.solve(frame(98))['cf1_reset'],'pcm_window_repeated_or_reversed')
        self.assertEqual(s.solve(frame(97))['cf1_reset'],'pcm_window_repeated_or_reversed')

    def test_clipped_or_missing_history_does_not_bridge_gap(self):
        x,_=self.plane(0,blocks=20)
        for missing in (False,True):
            s=self.solver()
            for i in range(20):s.accept_packet(*packet(i,x[i*512:(i+1)*512],clipped=(i==17 and not missing)))
            if missing:del s.blocks[17*512]
            r=s.solve(frame(18))
            self.assertEqual(r['history_frames'],1)
            self.assertFalse(r['direction_valid'])

    def test_queued_dma_cannot_refresh_old_samples(self):
        now=[10.];s=self.solver(lambda:now[0]);s.started(10.)
        now[0]=11.;zeros=np.zeros((512,4),np.int32)
        s.accept_packet(*packet(0,zeros));s.accept_packet(*packet(1,zeros))
        self.assertEqual(s.solve(frame(0))['cf1_reset'],'pcm_window_stale')

    def test_cooperative_receipt_preserves_exact_numeric_window_even_after_eviction(self):
        x,_=self.plane(90,20,blocks=100)
        reference=self.solver(); active=self.solver()
        for i in range(17):
            for s in (reference,active):s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
        expected=reference.solve(frame(15)); calls=[]
        def receive():
            calls.append(1)
            if len(calls)==1:
                for i in range(17,100):active.accept_packet(*packet(i,x[i*512:(i+1)*512]))
        active.service_capture=receive
        actual=active.solve(frame(15))
        self.assertEqual(actual,expected)
        self.assertEqual(len(calls),19)
        self.assertEqual(len(active.blocks),64)
        self.assertNotIn(0,active.blocks)

    def test_history_backfill_services_receiver_before_fifo_budget(self):
        # Deterministic scheduling model, not a claim about ARM wall-clock time.
        x,_=self.plane(0,blocks=17)
        for cooperative in (False,True):
            s=self.solver();elapsed=[0.];last=[0.];gaps=[]
            for i in range(17):s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            append=s.append_window
            def timed_append(*args):
                elapsed[0]+=.003
                return append(*args)
            def receive():
                gaps.append(elapsed[0]-last[0]);last[0]=elapsed[0]
            s.append_window=timed_append
            s.service_capture=receive if cooperative else None
            s.solve(frame(15));receive()
            self.assertLess(max(gaps),.01) if cooperative else self.assertGreater(max(gaps),2048/48000.)

    def test_cooperative_fault_or_stop_never_returns_a_direction(self):
        for error in (RuntimeError('audio overflow'),KeyboardInterrupt()):
            s=self.solver();x,_=self.plane(0,blocks=17)
            for i in range(17):s.accept_packet(*packet(i,x[i*512:(i+1)*512]))
            def fail():raise error
            s.service_capture=fail
            with self.assertRaises(type(error)):s.solve(frame(15))
            self.assertEqual(s.stats['solved'],0)


class FakePCM:
    requires_pcm=True
    def __init__(self,dma,fail=False):self.dma,self.fail,self.count=dma,fail,0
    def started(self,when):pass
    def accept_packet(self,data,meta):
        assert self.dma.inflight, 'PCM processing must follow DMA rearm'
        self.count+=1
        if self.fail:raise RuntimeError('injected frontend failure')
    def has_window(self,f):return self.count*512>=f['audio']['sample_start']+1024
    def solve(self,f):
        if f['audio']['valid'] and not f['fault']:assert self.has_window(f)
        return solved(valid=not bool(f['fault']))
    def summary(self):return dict(packets=self.count)


class OwnershipTests(unittest.TestCase):
    def session(self,acoustic=True,failure=None,frontend_fail=False,interrupt=False):
        timer=Clock();device=TimedAxes();audio=Audio();dma=JointDMA(audio,failure)
        solver=FakePCM(dma,frontend_fail)
        client=ThreeDClient(device,solver,7000,3,3,3,calibration())
        speaker=SpeakerStub(timer)
        if acoustic:
            speaker.poll_events=lambda: (_ for _ in ()).throw(AssertionError('No identity engine in acoustic mode'))
        elif interrupt:
            poll=speaker.poll_events
            def interrupt_poll():
                if speaker.count>=3:raise KeyboardInterrupt()
                return poll()
            speaker.poll_events=interrupt_poll
        with patch('os.fsync',side_effect=AssertionError('No storage writes during capture')):
            report=capture_joint(client,audio,dma,speaker,7,State3D(),None if acoustic else settings(.65),
                                 frames=12,clock=timer,sleep=timer.sleep)
        return report,device

    def test_acoustic_and_speaker_use_exact_window_then_stop(self):
        for acoustic in (True,False):
            r,d=self.session(acoustic)
            self.assertEqual(r['result'],'PASS',r)
            self.assertEqual(r['stats']['consumed'],12)
            self.assertGreater(r['stats']['motion_commits'],0)
            self.assertTrue(r['dma_halted'])
            self.assertFalse(d.active)
            self.assertIsNone(r['speaker_permission']) if acoustic else self.assertFalse(r['speaker_permission']['permit'])

    def test_frontend_or_dma_failure_stops(self):
        for args in ({'frontend_fail':True},{'failure':'gap'},{'failure':'dma'},{'failure':'timeout'}):
            r,d=self.session(**args)
            self.assertEqual(r['result'],'FAIL',r)
            self.assertTrue(r['dma_halted']);self.assertFalse(d.active)

    def test_ctrl_c_revokes_and_halts(self):
        r,d=self.session(acoustic=False,interrupt=True)
        self.assertEqual(r['result'],'PASS',r)
        self.assertEqual(r['stop_reason'],'user_stop')
        self.assertFalse(d.active);self.assertTrue(r['dma_halted'])
        self.assertFalse(r['speaker_permission']['permit'])

    def test_receiver_hook_is_wired_and_bounded_while_snapshot_is_locked(self):
        original=FakePCM.solve
        def solve(solver,frame):
            if solver.service_capture is not None:solver.service_capture()
            return original(solver,frame)
        with patch.object(FakePCM,'solve',solve):r,d=self.session()
        self.assertEqual(r['result'],'PASS',r)
        self.assertGreater(r['capture_service']['cooperative_packets'],0)
        self.assertEqual(r['capture_service']['max_batch_packets'],4)
        self.assertEqual(r['packets'],r['direction_frontend']['packets'])


if __name__=='__main__':
    unittest.main(verbosity=2)
