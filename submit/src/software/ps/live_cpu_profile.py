"""Opt-in diagnostics. No MMIO ownership, scheduling or identity policy changes."""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent/'speaker_core'))
from pipeline_bench import Backend
from cpu_profile_bench import snapshot, difference, proc_stat


def enabled():
    return os.environ.get('SS_SPEAKER_CPU_PROFILE') == '1'


def process_sample(pid):
    try:
        data=proc_stat(Path('/proc/%d/stat'%pid).read_text())
        return dict(pid=pid,**data)
    except (OSError,ValueError,IndexError) as exc:
        return dict(pid=pid,unavailable=type(exc).__name__)


def process_delta(a,b,hz):
    if 'unavailable' in a or 'unavailable' in b:
        return dict(status='UNAVAILABLE',before=a,after=b)
    if a['pid']!=b['pid'] or a['start']!=b['start'] or b['ticks']<a['ticks']:
        return dict(status='INVALID_COUNTER_IDENTITY')
    return dict(status='OK',pid=a['pid'],cpu_seconds=(b['ticks']-a['ticks'])/hz)


class InferenceProfile:
    """Owned only by the algorithm interpreter; never read /proc in DMA loop."""
    def __init__(self,capture_pid):
        self.capture_pid=capture_pid
        self.front=None
        self.origin=None
        self.rows=[]
        self.omitted_calls=0
        self.hz=os.sysconf('SC_CLK_TCK')

    def measure(self,backend,operation):
        # A 10-second bounded session at a 0.5-second hop cannot reach 32 jobs.
        # If reused outside this contract, retain a bounded diagnostic history.
        if len(self.rows)>=32:
            self.omitted_calls+=1
            return operation()
        overall=time.monotonic()
        ids={'capture':self.capture_pid,'algorithm_interpreter':os.getpid()}
        if self.front is not None:ids['frontend']=self.front.p.pid
        peers_before={name:process_sample(pid) for name,pid in ids.items()}
        before=None;error=None
        try:before=snapshot(backend.p.pid)
        except (OSError,ValueError,IndexError) as exc:error=repr(exc)
        begin=time.monotonic()
        succeeded=False
        try:
            result=operation();succeeded=True
            return result
        finally:
            done=time.monotonic();after=None
            try:after=snapshot(backend.p.pid)
            except (OSError,ValueError,IndexError) as exc:error=repr(exc)
            peers_after={name:process_sample(pid) for name,pid in ids.items()}
            counters=None
            if before is not None and after is not None:
                try:counters=difference(before,after,done-begin,self.hz)
                except (RuntimeError,ValueError) as exc:error=repr(exc)
            row=dict(call=len(self.rows)+1,completed=succeeded,
                start_elapsed_seconds=begin-self.origin if self.origin is not None else None,
                end_elapsed_seconds=done-self.origin if self.origin is not None else None,
                j_wall_seconds=done-begin,measurement_overhead_seconds=time.monotonic()-overall-(done-begin),
                embedding=counters,counter_error=error,
                peer_cpu={name:process_delta(peers_before[name],peers_after[name],self.hz) for name in ids})
            self.rows.append(row)

    def finish(self,result):
        scores=[r for r in result.get('results',[]) if r.get('score') is not None]
        completed=[r for r in self.rows if r['completed']]
        aligned=len(scores)==len(completed)
        if aligned:
            for row,score in zip(completed,scores):
                row['source_window']={k:score.get(k) for k in ('start_sample16','end_sample16','score','compute_seconds','reason','eligible')}
        complete=(aligned and result.get('status')=='PASS' and not self.omitted_calls and
                  all(r['completed'] and r['embedding'] is not None and
                      all(p['status']=='OK' for p in r['peer_cpu'].values()) for r in self.rows))
        status='NO_SAMPLES' if not self.rows else 'COMPLETE' if complete else 'PARTIAL'
        return dict(status=status,
                    scope='LIVE_J_CPU_AND_PEER_PROCESS_COUNTERS',calls=list(self.rows),
                    source_windows_aligned=aligned,record_limit=32,omitted_calls=self.omitted_calls,
                    meaning='J wall excludes counter sampling; compute_seconds includes diagnostic overhead; peer CPU windows include boundary sampling, not exact synchronized counters; process CPU sums threads; missing schedstat is unknown, never zero wait')


class ProfileBackend(Backend):
    def __init__(self,*args,profile,**kwargs):
        self.profile=profile
        super().__init__(*args,**kwargs)

    def run(self,op,values):
        if op=='J':
            return self.profile.measure(self,lambda:super(ProfileBackend,self).run(op,values))
        return super().run(op,values)


class CaptureMeter:
    """RAM counters around selected calls; no file IO, print or /proc here.

Buckets are non-overlapping selected calls, not all DMA polling/service costs.
CPU is process CPU (all threads), not inferred from elapsed time.
"""
    def __init__(self,wall=time.monotonic,cpu=time.process_time):
        self.wall,self.cpu=wall,cpu
        self.buckets={}
        self.restore=[]

    def wrap(self,name,operation):
        bucket=self.buckets.setdefault(name,dict(calls=0,wall_seconds=0.,cpu_seconds=0.))
        def measured(*args,**kwargs):
            begin=self.wall();cpu=self.cpu()
            try:return operation(*args,**kwargs)
            finally:
                bucket['calls']+=1
                bucket['cpu_seconds']+=self.cpu()-cpu
                bucket['wall_seconds']+=self.wall()-begin
        return measured

    def bind(self,obj,name,bucket):
        operation=getattr(obj,name)
        existing=obj.__dict__.get(name)
        had=name in obj.__dict__
        setattr(obj,name,self.wrap(bucket,operation))
        self.restore.append((obj,name,had,existing))

    def capture(self,operation,client,audio,dma,*args,**kwargs):
        try:
            self.bind(client,'acquire','snapshot_acquire')
            self.bind(client,'consume','snapshot_consume')
            self.bind(dma,'take','dma_take')
            self.bind(dma,'submit','dma_submit')
            if kwargs.get('packet_sink') is not None:
                kwargs['packet_sink']=self.wrap('speaker_ipc_submit',kwargs['packet_sink'])
            begin=self.wall();cpu=self.cpu()
            report,packets=operation(client,audio,dma,*args,**kwargs)
            cpu_elapsed=self.cpu()-cpu;elapsed=self.wall()-begin
            measured=sum(x['cpu_seconds'] for x in self.buckets.values())
            report['capture_cpu_profile']=dict(wall_seconds=elapsed,cpu_seconds=cpu_elapsed,
                buckets=self.buckets,other_and_measurement_cpu_seconds=cpu_elapsed-measured,
                meaning='Capture call including initial checks, START, STOP and DMA halt; excludes model load, inference join and file saving. Buckets exclude empty polls, packet validation, metadata checks and other receiver work; residual includes these and instrumentation overhead. No direction solver runs in this receiver.')
            return report,packets
        finally:
            for obj,name,had,old in reversed(self.restore):
                if had:setattr(obj,name,old)
                else:delattr(obj,name)
            self.restore.clear()
