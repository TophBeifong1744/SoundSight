"""Bounded Linux IPC: capture owns hardware; a separate interpreter owns algorithms.

No multiprocessing feeder thread or model work in the DMA-owning interpreter.
SEQPACKET preserves complete packets. Credits cover transport AND the old input
queue: returned only when the frontend removes a packet for processing.
"""
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import sys
import time

PACKET_BYTES=8224
CREDITS=32
MAX_MESSAGE=131072


class ProcessSpeaker:
    def __init__(self,core,window,scheduling,worker_command=None,startup_timeout=60.,backend_executable=None,
                 follow=False, permission_threshold=None, collect_statistics=False):
        self.sent=self.acked=self.highwater=0
        self.epoch=None;self.started_once=False;self.result=None;self.error=None
        self.closed=False;self.p=None
        self.events=[];self.follow=follow
        models=None
        if follow:
            from speaker_models import verify_candidates
            models=verify_candidates(core,window)
        self.sock,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,CREDITS*(PACKET_BYTES+256))
        self.sock.setblocking(False)
        self.send_buffer_bytes=self.sock.getsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF)
        config={'core':str(Path(core).resolve()),'window':window,'scheduling':scheduling.info,
                'front_prefix':scheduling.prefix('front'),'embed_prefix':scheduling.prefix('embed')}
        if follow:
            config['models']=models
            config['follow']=True
            config['permission_threshold']=permission_threshold
            config['collect_statistics']=bool(collect_statistics)
        if os.environ.get('SS_SPEAKER_CPU_PROFILE') == '1':
            config['cpu_profile_capture_pid']=os.getpid()
        if backend_executable is not None:config['backend_executable']=str(Path(backend_executable).resolve())
        command=worker_command or [*scheduling.prefix('front'),sys.executable,'-B',str(Path(__file__).resolve()),'--worker']
        try:
            self.p=subprocess.Popen([*command,str(child.fileno()),json.dumps(config)],
                                    pass_fds=(child.fileno(),),start_new_session=True)
            child.close()
            deadline=time.monotonic()+startup_timeout
            while not getattr(self,'ready',False):
                self._drain()
                if self.error or self.result is not None or self.p.poll() is not None:
                    raise RuntimeError(self.error or 'SPEAKER_WORKER_START_FAILED')
                if time.monotonic()>=deadline:raise TimeoutError('SPEAKER_WORKER_START_TIMEOUT')
                select.select([self.sock],[],[],.05)
            print('SPEAKER_PROCESS_READY=1 CAPTURE_GIL_SHARED=0 IPC_PACKET_LIMIT=32',flush=True)
        except BaseException:
            child.close();self.close();raise

    def _drain(self):
        for _ in range(CREDITS+4):
            try:data,_,flags,_=self.sock.recvmsg(MAX_MESSAGE)
            except BlockingIOError:break
            if not data:
                if self.result is None:self.error=self.error or 'SPEAKER_WORKER_EOF'
                break
            if flags & socket.MSG_TRUNC:raise RuntimeError('SPEAKER_IPC_TRUNCATED')
            if data==b'R':self.ready=True
            elif data[:1]==b'A' and len(data)==5:
                count=struct.unpack('<I',data[1:])[0]
                if not self.acked < count <= self.sent:raise RuntimeError('SPEAKER_IPC_BAD_ACK')
                self.acked=count
            elif data[:1]==b'E':self.error=data[1:].decode('utf-8',errors='replace')
            elif data[:1]==b'T' and self.follow:
                event=json.loads(data[1:])
                if not isinstance(event,dict) or len(self.events)>=64:
                    raise RuntimeError('SPEAKER_EVENT_OVERFLOW_OR_FORMAT')
                self.events.append(event)
            elif data[:1]==b'D':
                self.result=json.loads(data[1:])
                if not isinstance(self.result,dict):raise RuntimeError('SPEAKER_IPC_BAD_RESULT')
            else:raise RuntimeError('SPEAKER_IPC_UNKNOWN_MESSAGE')

    def poll_events(self):
        """Capture owner polls even between DMA packets; child loss fails closed."""
        self._drain()
        if self.error or self.result is not None or self.p.poll() is not None:
            raise RuntimeError(self.error or 'SPEAKER_WORKER_EXITED')
        events,self.events=self.events,[]
        return events

    def _send(self,data):
        try:n=self.sock.send(data,socket.MSG_DONTWAIT)
        except BlockingIOError as exc:raise RuntimeError('SPEAKER_IPC_BACKPRESSURE_STOP') from exc
        if n!=len(data):raise RuntimeError('SPEAKER_IPC_SHORT_SEND')

    def started(self,origin):
        if self.started_once:raise RuntimeError('SPEAKER_ALREADY_STARTED')
        self._drain()
        if self.error or self.p.poll() is not None:raise RuntimeError(self.error or 'SPEAKER_WORKER_EXITED')
        self._send(b'S'+struct.pack('<d',origin));self.started_once=True

    def submit(self,data,meta):
        # Called by the sole DMA owner. No print, disk IO, Python threads or wait.
        self._drain()
        if self.error or self.result is not None or self.p.poll() is not None:
            raise RuntimeError(self.error or 'SPEAKER_WORKER_EXITED')
        if not self.started_once or len(data)!=PACKET_BYTES:raise ValueError('SPEAKER_IPC_INPUT')
        if meta['block_seq']!=self.sent or meta['sample_start']!=self.sent*512:raise ValueError('SPEAKER_PACKET_GAP')
        if self.epoch is None:self.epoch=meta['epoch']
        if meta['epoch']!=self.epoch:raise ValueError('SPEAKER_EPOCH_CHANGED')
        if self.sent-self.acked>=CREDITS:raise RuntimeError('SPEAKER_IPC_CREDIT_OVERFLOW_STOP')
        self._send(b'P'+data);self.sent+=1
        self.highwater=max(self.highwater,self.sent-self.acked)

    def finish(self,capture_pass):
        # Called only after capture STOP/reset. Waiting here cannot starve DMA.
        self._drain();deadline=time.monotonic()+65.
        if self.result is None and self.p.poll() is None:
            message=b'F'+struct.pack('<?I',capture_pass,self.sent)
            while True:
                try:self._send(message);break
                except RuntimeError as exc:
                    if 'BACKPRESSURE' not in str(exc):raise
                    if time.monotonic()>=deadline:raise TimeoutError('SPEAKER_FINISH_SEND_TIMEOUT')
                    select.select([self.sock],[self.sock],[],.05);self._drain()
                    if self.result is not None or self.p.poll() is not None:break
            while self.result is None:
                self._drain()
                if self.result is not None:break
                if self.p.poll() is not None:break
                if time.monotonic()>=deadline:raise TimeoutError('SPEAKER_FINISH_TIMEOUT')
                select.select([self.sock],[],[],.05)
        result=self.result or dict(status='FAIL',error=self.error or 'SPEAKER_WORKER_NO_RESULT',results=[])
        if not capture_pass or self.error:
            result.update(status='FAIL',error=self.error or 'CAPTURE_FAILED_IDENTITIES_INVALID')
        if result.get('status')=='PASS' and (result.get('input_packets')!=self.sent or self.acked!=self.sent):
            result.update(status='FAIL',error='SPEAKER_IPC_ACCOUNTING')
        result.update(current_identity='insufficient',reason='session_ended',motion_commands=0,
                      ipc=dict(process_isolated=True,packet_limit=CREDITS,sent=self.sent,
                               frontend_taken=self.acked,highwater=self.highwater,
                               kernel_send_buffer_bytes=self.send_buffer_bytes))
        if result['status']!='PASS':
            for row in result.get('results',[]):row.update(eligible=False,state='insufficient',reason='capture_failed')
            result['eligible_results']=0
        return result

    def close(self):
        if self.closed:return
        self.closed=True
        try:
            if self.p is not None:
                # Dedicated session includes both C backends; do not leave them orphaned.
                try:os.killpg(self.p.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:self.p.wait(timeout=2.)
                except subprocess.TimeoutExpired:
                    try:os.killpg(self.p.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    self.p.wait(timeout=2.)
                # A failed leader may exit before a backend. Kill any remaining
                # members of this dedicated group, even when wait() returned.
                try:os.killpg(self.p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        finally:self.sock.close()


def worker(fd,config):
    from live_speaker import LiveSpeaker
    from pipeline_bench import Backend
    sock=socket.socket(fileno=fd);engine=None;forwarded=0;taken=0;result=None
    events=None
    if config.get('follow'):
        from live_speaker_follow import FollowSpeaker, LatestEvents
        from speaker_models import verify_candidates, backend_options
        verify_candidates(config['core'],config['window'])
        events=LatestEvents(config.get('permission_threshold'))
        sock.settimeout(.5)
    def send(data):
        if len(data)>MAX_MESSAGE:raise RuntimeError('SPEAKER_RESULT_TOO_LARGE')
        if sock.send(data)!=len(data):raise RuntimeError('SPEAKER_WORKER_SHORT_SEND')
    def packet_taken():
        nonlocal taken
        taken+=1;send(b'A'+struct.pack('<I',taken))
    profiler=None
    if 'cpu_profile_capture_pid' in config:
        from live_cpu_profile import InferenceProfile,ProfileBackend
        profiler=InferenceProfile(config['cpu_profile_capture_pid'])
    def backend(path,role):
        kwargs=dict(threads=2,prefix=config[role+'_prefix'],role=role,
                    executable=config.get('backend_executable'))
        if config.get('follow'):
            kwargs.update(backend_options(role))
        value=ProfileBackend(path,profile=profiler,**kwargs) if profiler is not None and role=='embed' else Backend(path,**kwargs)
        if profiler is not None and role=='front':profiler.front=value
        return value
    try:
        factory=FollowSpeaker if config.get('follow') else LiveSpeaker
        extra=dict(event_sink=events.publish,emit=lambda *a,**k:None,
                   collect_statistics=config.get('collect_statistics',False),
                   statistics_threshold=config.get('permission_threshold')) if events is not None else {}
        engine=factory(Path(config['core']),config['window'],backend_factory=backend,
                       scheduling=config['scheduling'],packet_taken=packet_taken,**extra)
        send(b'R')
        while True:
            if engine.error:raise RuntimeError(engine.error)
            if events is not None:
                for event in events.take():send(b'T'+json.dumps(event,allow_nan=False).encode('ascii'))
            if not select.select([sock],[],[],.005 if events is not None else .05)[0]:continue
            data,_,flags,_=sock.recvmsg(PACKET_BYTES+1)
            if not data:raise RuntimeError('SPEAKER_PARENT_CLOSED')
            if flags & socket.MSG_TRUNC:raise RuntimeError('SPEAKER_WORKER_TRUNCATED')
            if data[:1]==b'S' and len(data)==9:
                origin=struct.unpack('<d',data[1:])[0]
                if profiler is not None:profiler.origin=origin
                engine.started(origin)
            elif data[:1]==b'P' and len(data)==PACKET_BYTES+1:
                raw=data[1:];magic,fmt,epoch,seq,lo,hi,count,size=struct.unpack_from('<8I',raw)
                if (magic,fmt,count&65535,size)!=(0x43505353,0x00200001,512,8192):raise ValueError('SPEAKER_IPC_HEADER')
                engine.submit(raw,dict(epoch=epoch,block_seq=seq,sample_start=lo|(hi<<32)));forwarded+=1
            elif data[:1]==b'F' and len(data)==6:
                passed,expected=struct.unpack('<?I',data[1:])
                if expected!=forwarded:raise RuntimeError('SPEAKER_IPC_FORWARD_COUNT')
                result=engine.finish(passed);break
            else:raise RuntimeError('SPEAKER_WORKER_BAD_MESSAGE')
    except BaseException as exc:
        try:send(b'E'+repr(exc).encode('utf-8')[:4000])
        except OSError:pass
        if engine is not None:
            try:result=engine.finish(False)
            except BaseException:pass
        if result is None:result=dict(status='FAIL',error=repr(exc),results=[])
    finally:
        if engine is not None:
            try:engine.close()
            except BaseException as exc:
                if result is not None:result.update(status='FAIL',error='worker cleanup: '+repr(exc))
        if result is not None:
            if profiler is not None:result['cpu_profile']=profiler.finish(result)
            try:send(b'D'+json.dumps(result,allow_nan=False).encode('utf-8'))
            except (OSError,RuntimeError):pass
        sock.close()


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='--worker':raise SystemExit('INTERNAL_WORKER_ONLY')
    worker(int(sys.argv[2]),json.loads(sys.argv[3]))
