"""Bounded opt-in CPU instrumentation tests; all hardware is simulated."""
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
W=ROOT/'software/build/speaker-live-profile-validation'
P=Path(os.environ.get('SS_LIVE_PACKAGE',str(W/'relocated/SoundSight_PYNQ_Speaker_Live')))
E=ROOT/'document/evidence/ps-speaker-live-profile-20261025'
sys.path.insert(0,str(P/'software/ps'));sys.path.insert(0,str(P/'software/tests'))
import live_cpu_profile as cpu


class Tests(unittest.TestCase):
    def test_opt_in(self):
        for val,want in [('0',False),('',False),('true',False),('1',True)]:
            with patch.dict(os.environ,{'SS_SPEAKER_CPU_PROFILE':val}):self.assertEqual(cpu.enabled(),want)

    def test_peer_missing_or_pid_changed(self):
        self.assertEqual(cpu.process_delta({'unavailable':'x'},{},100)['status'],'UNAVAILABLE')
        self.assertEqual(cpu.process_delta(dict(pid=1,start=1,ticks=0),dict(pid=2,start=1,ticks=1),100)['status'],'INVALID_COUNTER_IDENTITY')

    def test_no_samples_and_partial_not_complete(self):
        p=cpu.InferenceProfile(os.getpid())
        self.assertEqual(p.finish({'status':'FAIL','results':[]})['status'],'NO_SAMPLES')
        p.rows=[dict(completed=True,embedding={},peer_cpu={'capture':dict(status='UNAVAILABLE')})]
        self.assertEqual(p.finish({'status':'PASS','results':[dict(score=.7)]})['status'],'PARTIAL')
        p.rows[0]['peer_cpu']['capture']['status']='OK'
        self.assertEqual(p.finish({'status':'PASS','results':[dict(score=.7,end_sample16=16000)]})['status'],'COMPLETE')
        self.assertEqual(p.rows[0]['source_window']['end_sample16'],16000)
        self.assertEqual(p.finish({'status':'FAIL','results':[dict(score=.7)]})['status'],'PARTIAL')

    def test_missing_proc_does_not_skip_or_change_operation(self):
        p=cpu.InferenceProfile(999999999)
        class Fake:
            class p:pid=999999998
        self.assertEqual(p.measure(Fake(),lambda:42),42)
        self.assertEqual(len(p.rows),1);self.assertIsNone(p.rows[0]['embedding'])
        self.assertTrue(p.rows[0]['completed'])
        with self.assertRaisesRegex(RuntimeError,'ORIGINAL_FAILURE'):
            p.measure(Fake(),lambda:(_ for _ in ()).throw(RuntimeError('ORIGINAL_FAILURE')))
        self.assertFalse(p.rows[-1]['completed'])

    def test_record_bound_not_inference_bound(self):
        p=cpu.InferenceProfile(os.getpid());p.rows=[{}]*32
        self.assertEqual(p.measure(None,lambda:42),42)
        self.assertEqual(len(p.rows),32);self.assertEqual(p.omitted_calls,1)

    def test_capture_wrappers_restore_success_and_exception(self):
        class Client:
            def acquire(self):return 17
            def consume(self,v):self.value=v
        class DMA:
            def take(self):return b'raw'
            def submit(self):pass
        for fail in (False,True):
            c,d=Client(),DMA();calls=[]
            def operation(client,audio,dma,*args,**kw):
                dma.submit();self.assertEqual(dma.take(),b'raw');v=client.acquire();client.consume(v)
                kw['packet_sink'](b'x',{})
                if fail:raise RuntimeError('CAPTURE_ORIGINAL_ERROR')
                return {'result':'PASS'},[b'x']
            meter=cpu.CaptureMeter()
            if fail:
                with self.assertRaisesRegex(RuntimeError,'CAPTURE_ORIGINAL_ERROR'):
                    meter.capture(operation,c,None,d,packet_sink=lambda *a:calls.append(a))
            else:
                report,raw=meter.capture(operation,c,None,d,packet_sink=lambda *a:calls.append(a))
                self.assertEqual(raw,[b'x']);self.assertEqual(report['capture_cpu_profile']['buckets']['dma_submit']['calls'],1)
            self.assertEqual(c.value,17);self.assertEqual(len(calls),1)
            self.assertNotIn('acquire',c.__dict__);self.assertNotIn('submit',d.__dict__)

    def test_real_process_clock_delta(self):
        p=cpu.InferenceProfile(os.getpid())
        class Fake:
            class p:pid=os.getpid()
        self.assertEqual(p.measure(Fake(),lambda:123),123)
        self.assertIsNotNone(p.rows[0]['embedding'])
        self.assertGreaterEqual(p.rows[0]['measurement_overhead_seconds'],0)

    def test_bind_failure_keeps_original_error(self):
        class Missing:pass
        meter=cpu.CaptureMeter()
        with self.assertRaisesRegex(AttributeError,'acquire'):
            meter.capture(None,Missing(),None,None)
        self.assertEqual(meter.restore,[])

    def test_message_bound(self):
        p=cpu.InferenceProfile(os.getpid())
        class Fake:
            class p:pid=os.getpid()
        p.measure(Fake(),lambda:1);p.rows=p.rows*32
        result=dict(status='PASS',results=[dict(score=.7,end_sample16=i) for i in range(32)])
        result['cpu_profile']=p.finish(result)
        from speaker_process import MAX_MESSAGE
        self.assertLess(len(json.dumps(result).encode()),MAX_MESSAGE)


def replay():
    from test_live_replay import packets,TimedDMA
    from test_pcm_capture import Audio,Client
    from ps_client import STATUS
    from pcm_capture import capture
    from speaker_scheduling import CaptureScheduling
    from speaker_process import ProcessSpeaker
    cfg=json.loads((P/'software/ps/speaker_core/opt-cases.json').read_text())
    report=dict(status='RUNNING',scope='TIMED_MOCK_DMA_NATIVE_NOT_BOARD',runs=[])
    os.environ['SS_SPEAKER_CPU_PROFILE']='1'
    with CaptureScheduling() as policy:
        for rid in cfg['groups']['pair']:
            source=packets(P/'software/ps/speaker_core/audio'/(rid+'.wav'))[:938]
            audio=Audio()
            class FrameClient(Client):
                def __init__(self):super().__init__();self.served=0
                def read(self,address):
                    if address==STATUS:return 1 if self.running and self.served<audio.published else 0
                    return super().read(address)
                def acquire(self):
                    return dict(audio=dict(valid=True,epoch=7,sample_count=1024,
                                           sample_start=self.served*512,source_window=self.served))
                def consume(self,frame):self.served+=1
            client,timing=FrameClient(),[None]
            original_start=client.start
            def start(clear_faults):timing[0]=time.monotonic();original_start(clear_faults)
            client.start=start
            engine=ProcessSpeaker(P/'software/ps/speaker_core',1.,policy,backend_executable=W/'native/pipeline_backend')
            try:
                cap,raw=cpu.CaptureMeter().capture(capture,client,audio,TimedDMA(audio,source,timing),7,938,
                                                  packet_sink=engine.submit,started=engine.started)
                live=engine.finish(cap['result']=='PASS')
                assert cap['result']=='PASS' and cap['dma_halted'] and not client.running
                assert live['status']=='PASS' and live['input_packets']==938 and live['ipc']['frontend_taken']==938
                assert live['motion_commands']==0 and live['current_identity']=='insufficient'
                profile=live['cpu_profile'];assert profile['status']=='COMPLETE' and profile['calls']
                for r in profile['calls']:
                    assert r['source_window']['end_sample16'] is not None
                    for peer in ['capture','frontend','algorithm_interpreter']:assert r['peer_cpu'][peer]['status']=='OK'
                errors=[]
                for r in live['results']:
                    if r['score'] is not None:
                        ref=cfg['references']['%s/1/%d'%(rid,r['end_sample16'])]
                        errors.append(abs(r['score']-ref['score']));assert errors[-1]<.002
                    assert not r['eligible'] or r['result_age_seconds']<=2.
                assert len(errors)==len(profile['calls'])
                buckets=cap['capture_cpu_profile']['buckets']
                assert buckets['speaker_ipc_submit']['calls']==938 and buckets['dma_take']['calls']==938
                assert buckets['snapshot_acquire']['calls']==938 and buckets['snapshot_consume']['calls']==938
                report['runs'].append(dict(recording=rid,capture_cpu_profile=cap['capture_cpu_profile'],
                    receiver_timing=cap['receiver_timing'],cpu_profile=profile,ipc=live['ipc'],max_score_error=max(errors),
                    consumed=live['consumed'],dma_halted=cap['dma_halted']))
                print('LIVE_CPU_REPLAY_PASS',rid,len(errors),flush=True)
            finally:engine.close()
    report['status']='PASS';(E/'live-replay.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    if sys.argv[1]=='unit':
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        (E/'unit.json').write_text(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun),indent=2)+'\n')
        if not result.wasSuccessful():raise SystemExit(1)
    elif sys.argv[1]=='replay':replay()
    elif sys.argv[1]=='board':
        # Existing lifecycle fixture intentionally exposes no snapshots; supply
        # the real client's interface and assert these methods are never used.
        import test_live_board_entry as board
        def no_frames(*args):raise AssertionError('UNEXPECTED_SNAPSHOT_IN_LIFECYCLE_FIXTURE')
        board.Client.acquire=no_frames;board.Client.consume=no_frames
        board.main()
    else:raise SystemExit(2)
