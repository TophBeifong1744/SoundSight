"""Live PCM consumer. No MMIO/PYNQ/servo access; capture remains sole device owner."""
import array
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parent/'speaker_core'))
from pipeline_bench import Backend,unit
from stream_bench import Cache,Latest,reset,MAX_FRONT_LAG,MAX_START_AGE,MAX_RESULT_AGE,HOP
from speaker_settings import window_value,verify_assets
from speaker_targets import decision


def pcm32_mic0(data):
    if sys.byteorder!='little' or array.array('i').itemsize!=4 or len(data)!=8224:
        raise ValueError('PCM32 packet layout')
    words=array.array('i');words.frombytes(data[32:])
    samples=words[::4]
    if any(x < -8388608 or x > 8388607 for x in samples):raise ValueError('PCM24 sign extension')
    values=array.array('f',(v/8388608. for v in samples))
    if sum(abs(v)>=.999 for v in values)/512>.01:raise ValueError('EXCESSIVE_CLIPPING')
    return values


class LiveSpeaker:
    def __init__(self,core,window,backend_factory=Backend,clock=time.monotonic,emit=print,config=None,scheduling=None,packet_taken=None):
        self.window=window_value(window);self.clock=clock;self.emit=emit
        self.scheduling=scheduling
        self.packet_taken=packet_taken
        self.config=verify_assets(core) if config is None else config
        self.emit('SPEAKER_TARGET='+json.dumps({'target_id':self.config.get('target_id','P01'),
                  'score_only':self.config.get('score_only',False)}),flush=True)
        self.input=queue.Queue(maxsize=32);self.mail=Latest();self.cache=Cache()
        self.start_event=threading.Event();self.input_done=threading.Event();self.stop=threading.Event()
        self.origin=None;self.epoch=None;self.accepted=0;self.input_highwater=0
        self.front_blocks=0;self.front_seconds=0.;self.max_lag=0.;self.partial_samples=0
        self.rows=[];self.error=None;self.error_lock=threading.Lock()
        self.detail_enabled=os.environ.get('SS_SPEAKER_DETAIL_PROFILE')=='1'
        self.python_timing={'frontend_ipc_seconds':0.,'cache_update_seconds':0.,'candidate_seconds':0.,
                            'embedding_ipc_seconds':0.,'normalize_score_seconds':0.}
        self.front=self.embed=None;self.threads=[]
        try:
            self.front=backend_factory(core,role='front')
            self.embed=backend_factory(core,role='embed')
            if any(b.loads.get('live_opt_revision')!=1 for b in (self.front,self.embed)):
                raise RuntimeError('LIVE_OPT_BACKEND_REQUIRED')
            reset(self.front)
            self.emit('SPEAKER_LOADED='+json.dumps({'front':self.front.loads,'embed':self.embed.loads}),flush=True)
            self.threads=[threading.Thread(target=self._front,name='live-front',daemon=True),
                          threading.Thread(target=self._infer,name='live-infer',daemon=True)]
            for t in self.threads:t.start()
            self.emit('SPEAKER_READY WINDOW_SECONDS=%g SERVO=OFF SPEAK_AFTER_CAPTURE_START'%self.window,flush=True)
        except BaseException:
            self.close();raise

    def fail(self,message):
        with self.error_lock:
            if self.error is None:self.error=str(message)
        self.stop.set();self.mail.finish(self.error)

    def started(self,origin):
        if self.origin is not None:raise RuntimeError('Speaker capture already started')
        self.origin=origin;self.start_event.set()

    def submit(self,data,meta):
        # Called in DMA service context: no model, serial or filesystem IO.
        if self.error:raise RuntimeError(self.error)
        if self.origin is None or self.input_done.is_set():raise RuntimeError('Speaker input not running')
        if meta['block_seq']!=self.accepted or meta['sample_start']!=self.accepted*512:
            raise ValueError('Speaker packet discontinuity')
        if self.epoch is None:self.epoch=meta['epoch']
        if meta['epoch']!=self.epoch:raise ValueError('Speaker epoch changed')
        try:self.input.put_nowait(data)
        except queue.Full:
            self.fail('SPEAKER_INPUT_OVERFLOW_STOP');raise RuntimeError(self.error)
        self.accepted+=1;self.input_highwater=max(self.input_highwater,self.input.qsize())

    def _front(self):
        samples=bytearray();due=int(self.window*16000)
        try:
            while not self.start_event.wait(.05):
                if self.stop.is_set():return
            while not self.stop.is_set():
                try:data=self.input.get(timeout=.05)
                except queue.Empty:
                    if self.input_done.is_set():break
                    continue
                if self.packet_taken is not None:self.packet_taken()
                samples.extend(data[32:])
                if len(samples)<1536*16:continue
                begin=self.clock()
                if begin-self.origin-(self.cache.samples+512)/16000>MAX_FRONT_LAG:
                    raise RuntimeError('SPEAKER_FRONTEND_OVERRUN')
                front_values=self.front.run_pcm32(samples)
                stamp=self.clock() if self.detail_enabled else 0
                if self.detail_enabled:self.python_timing['frontend_ipc_seconds']+=stamp-begin
                self.cache.push(front_values);samples.clear()
                if self.detail_enabled:self.python_timing['cache_update_seconds']+=self.clock()-stamp
                self.front_blocks+=1;self.front_seconds+=self.clock()-begin
                lag=self.clock()-self.origin-self.cache.samples/16000
                self.max_lag=max(self.max_lag,lag)
                if lag>MAX_FRONT_LAG:raise RuntimeError('SPEAKER_FRONTEND_OVERRUN')
                stamp=self.clock() if self.detail_enabled else 0
                self.mail.update_voice(self.cache)
                if self.cache.samples>=due:
                    job=self.cache.snapshot(self.window);job['epoch']=self.epoch
                    self.mail.put(job);due+=HOP
                if self.detail_enabled:self.python_timing['candidate_seconds']+=self.clock()-stamp
            self.partial_samples=len(samples)//16
            if samples and not self.stop.is_set():self.front.check_pcm32_tail(samples)
            if not self.stop.is_set():self.mail.finish()
        except BaseException as exc:self.fail(repr(exc))

    def _infer(self):
        try:
            while not self.stop.is_set():
                job=self.mail.take()
                if job is None:break
                begin=self.clock();end_seconds=job['end_sample16']/16000
                row={k:v for k,v in job.items() if k!='features'}
                row.update(state='insufficient',eligible=False,score=None,start_age_seconds=begin-self.origin-end_seconds)
                if row['start_age_seconds']>MAX_START_AGE:reason='stale_before_start'
                elif job['coverage']<.5 or not job['active']:reason='insufficient_speech'
                else:
                    stamp=self.clock() if self.detail_enabled else 0
                    raw_vec=self.embed.run('J',job['features'])
                    scored=self.clock() if self.detail_enabled else 0
                    vec=unit(raw_vec)
                    score=max(-1.,min(1.,sum(x*y for x,y in zip(vec,self.config['template']))))
                    if self.detail_enabled:
                        self.python_timing['embedding_ipc_seconds']+=scored-stamp
                        self.python_timing['normalize_score_seconds']+=self.clock()-scored
                    row.update(score=score,raw_state=decision(score,self.config))
                    reason=self.mail.validity(job,self.clock()-self.origin-end_seconds)
                    if reason=='fresh' and self.config.get('score_only',False):reason='threshold_not_calibrated'
                    if reason=='fresh' and not self.stop.is_set():row.update(state=row['raw_state'],eligible=row['raw_state']!='insufficient')
                row.update(target_id=self.config.get('target_id','P01'),score_only=self.config.get('score_only',False))
                row.update(reason=reason,compute_seconds=self.clock()-begin,result_age_seconds=self.clock()-self.origin-end_seconds)
                if self.error == 'CAPTURE_FAILED_IDENTITIES_INVALID':
                    row.update(reason='capture_failed',state='insufficient',eligible=False)
                if row['eligible']:
                    reason=self.mail.validity(job,row['result_age_seconds'])
                    if reason!='fresh' or self.stop.is_set():row.update(reason=reason,state='insufficient',eligible=False)
                row['publish_elapsed_seconds']=self.clock()-self.origin
                row['valid_until_source_elapsed_seconds']=end_seconds+MAX_RESULT_AGE if row['eligible'] else None
                row['motion_commands']=0
                self.rows.append(row)
                # Separate inference thread; DMA callback never prints or writes SD.
                self.emit('SPEAKER_RESULT='+json.dumps(row),flush=True)
        except BaseException as exc:self.fail(repr(exc))

    def finish(self,capture_pass):
        if not capture_pass:self.fail('CAPTURE_FAILED_IDENTITIES_INVALID')
        self.input_done.set()
        for t in self.threads:t.join(timeout=30)
        if any(t.is_alive() for t in self.threads):self.fail('SPEAKER_WORKER_SHUTDOWN_TIMEOUT')
        if capture_pass and not self.error and self.front_blocks*1536+self.partial_samples!=self.accepted*512:
            self.fail('SPEAKER_INPUT_ACCOUNTING')
        if not self.error and self.mail.generated!=self.mail.replaced+len(self.rows):self.fail('SPEAKER_WINDOW_ACCOUNTING')
        # This is session end: no permission/identity survives it, even on success.
        self.stop.set()
        timings=None
        if not self.error:
            timings={'front':self.front.timings(),'embed':self.embed.timings(),
                     'meaning':'C wall time includes scheduling; frontend contains mel and VAD, do not sum nested fields'}
            if self.detail_enabled:
                timings['detail']={'front':self.front.detail_timings(),'embed':self.embed.detail_timings(),
                                   'python':dict(self.python_timing),
                                   'meaning':'Nested in parent timings; IPC includes C computation, not pure transport. ORT Run includes profiler overhead. FIR includes stream bookkeeping.'}
        result={'status':'FAIL' if self.error else 'PASS','error':self.error,'window_seconds':self.window,
                'epoch':self.epoch,'input_packets':self.accepted,'input_capacity_packets':32,'input_highwater':self.input_highwater,
                'front_blocks':self.front_blocks,'front_seconds':self.front_seconds,'max_front_lag_seconds':self.max_lag,
                'tail_samples48_not_processed':self.partial_samples,'mel_frames_computed_once':self.cache.frame_count,
                'generated':self.mail.generated,'replaced':self.mail.replaced,'consumed':len(self.rows),
                'results':list(self.rows),'eligible_results':sum(r['eligible'] for r in self.rows),
                'current_identity':'insufficient','reason':'session_ended','motion_commands':0,'recognition_qualified':False,
                'scheduling':self.scheduling,'backend_timing':timings,
                'target_id':self.config.get('target_id','P01'),'score_only':self.config.get('score_only',False),
                'time_origin':'host monotonic before capture START; includes start/transport overhead, not measured acoustic timestamp'}
        return result

    def close(self):
        self.stop.set();self.start_event.set();self.mail.finish('SESSION_CLOSED')
        for b in (self.front,self.embed):
            if b is not None:
                # Only diagnostic sessions need a graceful Q to flush ORT traces.
                # Never write into a pipe concurrently with a still-running worker.
                graceful=self.detail_enabled and not any(t.is_alive() for t in self.threads)
                b.close(force=not graceful)
        for t in self.threads:t.join(timeout=2)


def main(root,window=None,seconds=10.):
    from speaker_settings import get_window,capture_blocks
    from run_pcm import main as pcm_main
    from speaker_scheduling import CaptureScheduling
    from speaker_process import ProcessSpeaker
    root=Path(root);selected=get_window(root) if window is None else window_value(window)
    blocks=capture_blocks(seconds,selected)
    core=root/'software/ps/speaker_core'
    verify_assets(core)
    print('SPEAKER_REQUEST WINDOW_SECONDS=%g CAPTURE_SECONDS=%.3f MOTION_COMMANDS=0'%(selected,blocks*512/48000),flush=True)
    with CaptureScheduling() as scheduling:
        print('SPEAKER_SCHEDULING='+json.dumps(scheduling.info),flush=True)
        return pcm_main(blocks=blocks,root=root,processor_factory=lambda:ProcessSpeaker(core,selected,scheduling))
