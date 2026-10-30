"""Python 3.8+ standard-library file pipeline; no PYNQ, torch or hardware IO."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time
import wave


def unit(v):
    norm = math.sqrt(sum(x*x for x in v))
    if len(v) != 192 or not math.isfinite(norm) or norm < 1e-8:
        raise ValueError('INVALID_EMBEDDING')
    return [x/norm for x in v]


def spans_from_probs(probs, length):
    """Silero 6.0 rule subset: 16k, pad=0, unlimited max span, 250/100ms.
    Adapted from MIT silero_vad/utils_vad.py; max-span logic is unreachable.
    """
    spans, start, temp_end = [], None, 0
    for i, p in enumerate(probs):
        pos = i*512
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('INVALID_VAD_PROBABILITY')
        if p >= .5 and temp_end:
            temp_end = 0
        if p >= .5 and start is None:
            start = pos
            continue
        if p < .35 and start is not None:
            if not temp_end:
                temp_end = pos
            if pos-temp_end < 1600:
                continue
            if temp_end-start > 4000:
                spans.append([start, temp_end])
            start, temp_end = None, 0
    if start is not None and length-start > 4000:
        spans.append([start, length])
    return spans


class Backend:
    def __init__(self, root, threads=2, prefix=None, executable=None, model_filename='int8-head.onnx', role=None,
                 vad_filename='silero_vad.onnx'):
        self.root = Path(root)
        cmd = list(prefix or []) + [str(executable or self.root/'pipeline_backend'),
              str(self.root/'models'/model_filename), str(self.root/'models'/vad_filename),
              str(self.root/'frontend.f32'), str(threads)]
        if role is not None:
            if role not in ('front','embed'):raise ValueError('BACKEND_ROLE')
            cmd.append(role)
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            line = self.p.stdout.readline()
            self.loads = json.loads(line)
        except BaseException:
            self.close(force=True)
            raise

    def read(self, n):
        parts = bytearray()
        while len(parts) < n:
            block = self.p.stdout.read(n-len(parts))
            if not block:
                raise RuntimeError('BACKEND_EOF')
            parts.extend(block)
        return parts

    def run(self, op, values):
        data = values if isinstance(values, array.array) else array.array('f', values)
        self.p.stdin.write(op.encode()+struct.pack('<I', len(data)))
        self.p.stdin.write(data.tobytes())
        self.p.stdin.flush()
        return self._reply()

    def _reply(self):
        n, = struct.unpack('<I', self.read(4))
        if n > 960000:
            raise RuntimeError('BACKEND_LENGTH')
        result = array.array('f')
        result.frombytes(self.read(4*n))
        return result

    def run_pcm32(self, raw):
        if len(raw)!=1536*16:raise ValueError('PCM32_BLOCK_BYTES')
        self.p.stdin.write(b'B'+struct.pack('<I',1536))
        self.p.stdin.write(raw);self.p.stdin.flush()
        return self._reply()

    def timings(self):
        self.p.stdin.write(b'T');self.p.stdin.flush()
        keys=('decode_seconds','frontend_seconds','mel_seconds','vad_seconds',
              'cmn_seconds','embedding_seconds','frontend_blocks','embedding_calls')
        return dict(zip(keys,struct.unpack('<8d',self.read(64))))

    def detail_timings(self):
        self.p.stdin.write(b'U');self.p.stdin.flush()
        keys=('frame_prepare_seconds','fft_seconds','power_seconds','mel_project_log_seconds',
              'fir_and_stream_bookkeeping_seconds','vad_ort_run_seconds','embedding_ort_run_seconds',
              'embedding_output_copy_seconds','vad_calls','embedding_calls','mel_frames','stream_blocks')
        return dict(zip(keys,struct.unpack('<12d',self.read(96))))

    def check_pcm32_tail(self, raw):
        if len(raw) not in (512*16,1024*16):raise ValueError('PCM32_TAIL_BYTES')
        self.p.stdin.write(b'C'+struct.pack('<I',len(raw)//16))
        self.p.stdin.write(raw);self.p.stdin.flush()
        if self._reply():raise RuntimeError('PCM32_TAIL_ACK')

    def rss(self):
        self.p.stdin.write(b'R'); self.p.stdin.flush()
        return struct.unpack('<d', self.read(8))[0]

    def close(self, force=False):
        if self.p.poll() is None:
            if force:
                self.p.kill()
            else:
                self.p.stdin.write(b'Q'); self.p.stdin.flush()
        try:
            code = self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill(); self.p.wait()
            raise RuntimeError('BACKEND_SHUTDOWN_TIMEOUT')
        self.p.stdin.close(); self.p.stdout.close()
        if code and not force:
            raise RuntimeError('BACKEND_FAILED')


def read_mic0(path):
    # Deliberately narrow input contract for the existing PL capture format.
    with wave.open(str(path), 'rb') as f:
        n = f.getnframes()
        if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getcomptype()) != (48000, 4, 3, 'NONE'):
            raise ValueError('REQUIRED_WAV_PCM24_48K_4CH')
        if not 72000 <= n <= 2880000:
            raise ValueError('AUDIO_DURATION_BOUND')
        raw = f.readframes(n)
        if len(raw) != n*12:
            raise ValueError('TRUNCATED_WAV')
    values = array.array('f')
    clipped = 0
    for i in range(0, len(raw), 12):
        v = raw[i] | raw[i+1] << 8 | raw[i+2] << 16
        if v & 0x800000:
            v -= 0x1000000
        value = v/8388608.
        clipped += abs(value) >= .999
        values.append(value)
    if clipped/n > .01:
        raise ValueError('EXCESSIVE_CLIPPING')
    return values, n/48000


def extract(backend, path, template, low, high, trace=None, decoder=read_mic0):
    start = time.perf_counter()
    mic, duration = decoder(path)
    decoded = time.perf_counter()
    audio = backend.run('P', mic)
    prepared = time.perf_counter()
    probs = backend.run('V', audio) if audio else []
    spans = spans_from_probs(probs, len(audio))
    vad_done = time.perf_counter()
    count = sum(b-a for a,b in spans)
    result = {'input_seconds': duration, 'speech_seconds': count/16000,
              'spans': spans, 'chunks': 0, 'state': 'insufficient', 'score': None,
              'decode_seconds': decoded-start, 'resample_seconds': prepared-decoded,
              'vad_seconds': vad_done-prepared, 'fbank_seconds': 0., 'embedding_seconds': 0.}
    if trace is not None:
        trace.update(audio=list(audio), probs=list(probs), features=[], embeddings=[])
    if count >= 24000:
        speech = array.array('f')
        for a,b in spans:
            speech.extend(audio[a:b])
        speech = speech[:320000]
        chunks = (len(speech)+63999)//64000
        size, rem = divmod(len(speech), chunks)
        vectors, lengths, offset = [], [], 0
        for i in range(chunks):
            n = size+(i < rem)
            begin = time.perf_counter()
            feat = backend.run('F', speech[offset:offset+n])
            middle = time.perf_counter()
            vector = backend.run('E', feat)
            end = time.perf_counter()
            result['fbank_seconds'] += middle-begin
            result['embedding_seconds'] += end-middle
            vectors.append(unit(vector)); lengths.append(n); offset += n
            if trace is not None:
                trace['features'].append(list(feat)); trace['embeddings'].append(list(vector))
        avg = unit([sum(v[j]*n for v,n in zip(vectors,lengths))/sum(lengths) for j in range(192)])
        score = max(-1., min(1., sum(a*b for a,b in zip(avg,template))))
        result.update(chunks=chunks, score=score,
                      state='target' if score >= high else 'non_target' if score <= low else 'insufficient')
        if trace is not None:
            trace['vector'] = avg
    else:
        result['reason'] = 'SILENCE_OR_TOO_QUIET' if not audio else 'NO_VALID_SPEECH' if count == 0 else 'INSUFFICIENT_SPEECH'
    result['total_seconds'] = time.perf_counter()-start
    result['other_seconds'] = result['total_seconds']-sum(result[k] for k in
        ('decode_seconds','resample_seconds','vad_seconds','fbank_seconds','embedding_seconds'))
    result['rtf_file'] = result['total_seconds']/duration
    result['rtf_speech'] = result['total_seconds']/(count/16000) if count else None
    return result


def check_reference(result, ref):
    if result['spans'] != ref['spans'] or result['state'] != ref['state'] or result['chunks'] != ref['chunks']:
        raise ValueError('REFERENCE_SPANS_OR_DECISION_MISMATCH')
    if ref['score'] is not None and (result['score'] is None or abs(result['score']-ref['score']) > .002):
        raise ValueError('REFERENCE_SCORE_MISMATCH')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=['pair','all','target','other','silence'], default='pair')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if sys.byteorder != 'little':
        raise ValueError('REQUIRED_LITTLE_ENDIAN')
    root = Path(__file__).resolve().parent
    config = json.loads((root/'cases.json').read_text())
    ids = config['groups'][args.case]
    # Check fixture hashes before the timed section, never substitute saved features.
    for rid in ids:
        f = root/'audio'/(rid+'.wav')
        if hashlib.sha256(f.read_bytes()).hexdigest() != config['references'][rid]['wav_sha256']:
            raise ValueError('WAV_HASH_MISMATCH')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output/'result.json'
    if result_path.exists():
        raise ValueError('RESULT_ALREADY_EXISTS')
    results = {'status':'RUNNING', 'scope':'OFFLINE_WAV_END_TO_END', 'motion_commands':0,
               'live_capture':False, 'threads':2, 'vad_threads':1, 'runs':[]}
    backend = None
    try:
        begin = time.perf_counter()
        backend = Backend(root)
        results['startup_seconds'] = time.perf_counter()-begin
        results.update(backend.loads)
        print('PIPELINE_LOADED='+json.dumps(backend.loads), flush=True)
        for repeat in range(2):
            for rid in ids:
                r = extract(backend, root/'audio'/(rid+'.wav'), config['template'], config['low'], config['high'])
                r.update(id=rid, run=repeat+1)
                results['runs'].append(r)
                check_reference(r, config['references'][rid])
                r['reference_pass'] = True
                r['backend_peak_rss_mib'] = backend.rss()
                r['driver_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
                r['rss_sum_upper_bound_mib'] = r['backend_peak_rss_mib']+r['driver_peak_rss_mib']
                print(json.dumps(r, allow_nan=False), flush=True)
        backend.close(); backend = None
        results['status'] = 'PASS'
    except BaseException as exc:
        results.update(status='FAIL', error=repr(exc))
        raise
    finally:
        if backend is not None:
            backend.close(force=True)
        with result_path.open('x') as f:
            json.dump(results,f,indent=2,allow_nan=False)
    print('PIPELINE_BENCH=PASS LIVE_CAPTURE=0 MOTION_COMMANDS=0', flush=True)


if __name__ == '__main__':
    main()
