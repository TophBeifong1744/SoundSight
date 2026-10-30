"""Paced WAV replay with a bounded latest-window mailbox; Python 3.8 stdlib.

Two processes own one model each: continuous frontend/VAD and embedding.
No hardware capture or motion. No decisions are latched across jobs.
"""
import argparse
import array
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import struct
import threading
import time
import wave

from pipeline_bench import Backend, unit
from short_bench import convert

BLOCK48 = 1536
BLOCK16 = 512
HOP = 8000
MAX_FRONT_LAG = 0.5
MAX_START_AGE = 0.25
MAX_RESULT_AGE = 2.0


def reset(front):
    front.p.stdin.write(b'Z'); front.p.stdin.flush()
    if front.read(4) != struct.pack('<I', 1):
        raise RuntimeError('STREAM_RESET_ACK')


class Cache:
    def __init__(self):
        self.frames = deque(maxlen=202)
        self.activity = deque(maxlen=66)
        self.samples = self.frame_count = self.voice_epoch = 0
        self.active = False

    def push(self, packet):
        if len(packet) < 515 or packet[0] != 512 or packet[1] not in (1, 2, 3, 4):
            raise ValueError('STREAM_PACKET_SHAPE')
        nf = int(packet[1]); p = packet[2]
        if len(packet) != 515+nf*80 or not all(math.isfinite(x) for x in packet) or not 0 <= p <= 1:
            raise ValueError('STREAM_PACKET_VALUES')
        active = True if p >= .5 else False if p < .35 else self.active
        if active != self.active:
            self.voice_epoch += 1
        self.active = active
        self.activity.append((self.samples, self.samples+512, active))
        self.samples += 512
        for f in range(nf):
            self.frames.append((self.frame_count*160, packet[515+f*80:515+(f+1)*80]))
            self.frame_count += 1

    def snapshot(self, duration):
        n = int(duration*16000)
        end = self.samples//160*160
        start = end-n
        if start < 0:
            return None
        frames = [(s, x) for s, x in self.frames if start <= s and s+400 <= end]
        expected = 1+(n-400)//160
        if len(frames) != expected or frames[0][0] != start:
            raise ValueError('CACHE_FRAME_GAP')
        raw = array.array('f')
        for _, x in frames:
            raw.extend(x)
        coverage = sum(max(0, min(b,end)-max(a,start)) for a,b,on in self.activity if on)/n
        return {'end_sample16': end, 'start_sample16': start, 'features': raw,
                'frames': expected, 'coverage': coverage, 'voice_epoch': self.voice_epoch,
                'active': self.active, 'window_seconds': duration}


class Latest:
    """At most one queued snapshot; one other may be executing."""
    def __init__(self):
        self.cv = threading.Condition()
        self.pending = None
        self.done = False
        self.error = None
        self.generated = self.replaced = 0
        self.active = False
        self.voice_epoch = 0

    def update_voice(self, cache):
        with self.cv:
            self.active, self.voice_epoch = cache.active, cache.voice_epoch

    def put(self, job):
        with self.cv:
            if self.done:
                raise RuntimeError('PUBLISH_AFTER_FINISH')
            self.generated += 1
            self.replaced += self.pending is not None
            self.pending = job
            self.cv.notify()

    def finish(self, error=None):
        with self.cv:
            self.done, self.error = True, error
            if error:
                self.pending = None
            self.cv.notify_all()

    def take(self):
        with self.cv:
            while self.pending is None and not self.done:
                self.cv.wait(.1)
            if self.error:
                raise RuntimeError(self.error)
            job, self.pending = self.pending, None
            return job

    def validity(self, job, age):
        with self.cv:
            if self.error:
                return 'frontend_failed'
            if age > MAX_RESULT_AGE:
                return 'expired'
            if not self.active or self.voice_epoch != job['voice_epoch']:
                return 'speech_state_changed'
            return 'fresh'


def source_info(path):
    with wave.open(str(path), 'rb') as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getcomptype()) != (48000,4,3,'NONE'):
            raise ValueError('REQUIRED_WAV_PCM24_48K_4CH')
        n = f.getnframes()
        if n < 96000 or n > 2880000:
            raise ValueError('STREAM_SOURCE_BOUND')
    return n


def reference_check(job, ref, score):
    if job['frames'] != ref['frames'] or abs(job['coverage']-ref['coverage']) > 1e-12:
        raise ValueError('STREAM_REFERENCE_SHAPE_OR_COVERAGE')
    if score is not None and abs(score-ref['score']) > .002:
        raise ValueError('STREAM_REFERENCE_SCORE')


def replay(front, embed, source, rid, duration, config, stress_delay=0., emit=print):
    n = source_info(source)
    reset(front)
    cache, mailbox, stop = Cache(), Latest(), threading.Event()
    origin = time.monotonic()
    stats = {'blocks': 0, 'front_seconds': 0., 'max_front_lag_seconds': 0.,
             'source_samples48': n, 'tail_samples48_not_processed': n % BLOCK48}

    def produce():
        due = int(duration*16000)
        try:
            with wave.open(str(source), 'rb') as f:
                for b in range(n//BLOCK48):
                    release = origin+(b+1)*.032
                    if stop.wait(max(0., release-time.monotonic())):
                        break
                    lag = time.monotonic()-release
                    stats['max_front_lag_seconds'] = max(stats['max_front_lag_seconds'], lag)
                    if lag > MAX_FRONT_LAG:
                        raise RuntimeError('FRONTEND_OVERRUN_NO_CATCHUP')
                    begin = time.monotonic()
                    raw = f.readframes(BLOCK48)
                    if len(raw) != BLOCK48*12:
                        raise ValueError('TRUNCATED_WAV')
                    packet = front.run('S', convert(front, raw))
                    cache.push(packet)
                    stats['blocks'] += 1
                    stats['front_seconds'] += time.monotonic()-begin
                    lag = time.monotonic()-release
                    stats['max_front_lag_seconds'] = max(stats['max_front_lag_seconds'], lag)
                    if lag > MAX_FRONT_LAG:
                        raise RuntimeError('FRONTEND_OVERRUN_NO_CATCHUP')
                    mailbox.update_voice(cache)
                    if cache.samples >= due:
                        job = cache.snapshot(duration)
                        job['reference_id'] = '%s/%g/%d' % (rid, duration, job['end_sample16'])
                        mailbox.put(job)
                        due += HOP
            mailbox.finish()
        except BaseException as exc:
            mailbox.finish(repr(exc))

    producer = threading.Thread(target=produce, name='pcm-replay', daemon=True)
    producer.start()
    rows = []
    try:
        while True:
            job = mailbox.take()
            if job is None:
                break
            started = time.monotonic()
            age = started-origin-job['end_sample16']/16000
            row = {k:v for k,v in job.items() if k != 'features'}
            row.update(start_age_seconds=age, score=None, state='insufficient',
                       eligible=False, compute_seconds=0., reference_pass=False)
            ref = config['references'][job['reference_id']]
            if age > MAX_START_AGE:
                reason = 'stale_before_start'
            elif job['coverage'] < .5 or not job['active']:
                reason = 'insufficient_speech'
            else:
                features = embed.run('N', job['features'])
                vector = unit(embed.run('E', features))
                score = max(-1., min(1., sum(a*b for a,b in zip(vector,config['template']))))
                if stress_delay:
                    time.sleep(stress_delay)
                row['score'] = score
                row['raw_state'] = 'target' if score >= config['high'] else 'non_target' if score <= config['low'] else 'insufficient'
                reason = mailbox.validity(job, time.monotonic()-origin-job['end_sample16']/16000)
                if reason == 'fresh':
                    row.update(state=row['raw_state'], eligible=row['raw_state'] != 'insufficient')
            reference_check(job, ref, row['score'])
            row['reference_pass'] = True
            row['reason'] = reason
            row['compute_seconds'] = time.monotonic()-started
            row['result_age_seconds'] = time.monotonic()-origin-job['end_sample16']/16000
            # Deadline applies at publication as well, including validation overhead.
            if row['result_age_seconds'] > MAX_RESULT_AGE and row['eligible']:
                row.update(state='insufficient', eligible=False, reason='expired')
            row['source_end_seconds'] = job['end_sample16']/16000
            row['publish_elapsed_seconds'] = time.monotonic()-origin
            row['valid_until_source_elapsed_seconds'] = row['source_end_seconds']+MAX_RESULT_AGE if row['eligible'] else None
            rows.append(row)
            emit('STREAM_WINDOW='+json.dumps(dict(row, recording_id=rid)), flush=True)
        if stats['blocks'] != n//BLOCK48:
            raise RuntimeError('INCOMPLETE_REPLAY')
    finally:
        stop.set()
        producer.join(timeout=5)
        if producer.is_alive():
            front.close(force=True)
            producer.join(timeout=5)
            raise RuntimeError('FRONTEND_SHUTDOWN_TIMEOUT')
    elapsed = time.monotonic()-origin
    result = dict(stats, recording_id=rid, window_seconds=duration, elapsed_seconds=elapsed,
                  generated=mailbox.generated, replaced=mailbox.replaced, consumed=len(rows),
                  pending_capacity=1, in_flight_capacity=1, max_cached_frames=202,
                  mel_frames_computed_once=cache.frame_count, vad_blocks_computed_once=stats['blocks'],
                  results=rows, live_capture=False, recognition_qualified=False)
    result['embedding_calls'] = sum(r['score'] is not None for r in rows)
    result['eligible_results'] = sum(r['eligible'] for r in rows)
    result['reason_counts'] = {k:sum(r['reason']==k for r in rows) for k in sorted({r['reason'] for r in rows})}
    assert mailbox.generated == mailbox.replaced+len(rows)
    assert all(not r['eligible'] or r['result_age_seconds'] <= MAX_RESULT_AGE for r in rows)
    emit('STREAM_SUMMARY='+json.dumps({k:v for k,v in result.items() if k != 'results'}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['bench','stress'])
    parser.add_argument('--window', type=float, choices=[1.,1.5,2.])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = json.loads((root/'stream-cases.json').read_text())
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    result_path = output/'result.json'
    if result_path.exists():
        raise ValueError('RESULT_ALREADY_EXISTS')
    for rid in config['groups']['pair']:
        path = root/'audio'/(rid+'.wav')
        source_info(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != config['sources'][rid]['sha256']:
            raise ValueError('SOURCE_HASH')
    front = embed = None
    result = {'status':'RUNNING', 'live_capture':False, 'motion_commands':0,
              'recognition_qualified':False, 'action':args.action, 'runs':[],
              'limits':{'max_front_lag':MAX_FRONT_LAG, 'max_start_age':MAX_START_AGE,
                        'max_result_age':MAX_RESULT_AGE, 'hop_seconds':HOP/16000}}
    try:
        front = Backend(root, role='front')
        embed = Backend(root, role='embed')
        result['loads'] = {'front':front.loads, 'embed':embed.loads}
        print('STREAM_LOADED='+json.dumps(result['loads']), flush=True)
        for duration in ([args.window] if args.window else [1.,1.5,2.]):
            for rid in config['groups']['pair']:
                print('STREAM_REPLAY_BEGIN='+json.dumps({'recording':rid, 'window':duration}), flush=True)
                r = replay(front, embed, root/'audio'/(rid+'.wav'), rid, duration, config,
                           stress_delay=3. if args.action=='stress' else 0.)
                result['runs'].append(r)
        result['frontend_peak_rss_mib'] = front.rss()
        result['embedding_peak_rss_mib'] = embed.rss()
        result['driver_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.
        front.close(); front=None
        embed.close(); embed=None
        result['status']='PASS'
    except BaseException as exc:
        result.update(status='FAIL',error=repr(exc))
        raise
    finally:
        for backend in (front,embed):
            if backend is not None:
                backend.close(force=True)
        with result_path.open('x') as f:
            json.dump(result,f,indent=2,allow_nan=False)
    print('STREAM_BENCH=PASS REPLAY_ONLY=1 RECOGNITION_QUALIFIED=0 LIVE_CAPTURE=0 MOTION_COMMANDS=0',flush=True)


if __name__ == '__main__':
    main()
