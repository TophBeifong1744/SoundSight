"""Matched short-window evaluation and exact PCM conversion A/B, stdlib only."""
import argparse
import array
import json
from pathlib import Path
import resource
import statistics
import struct
import sys
import time
import wave

from pipeline_bench import Backend, unit, spans_from_probs, read_mic0, extract, check_reference


def read_raw(path, start=0, frames=None):
    with wave.open(str(path),'rb') as f:
        if (f.getframerate(),f.getnchannels(),f.getsampwidth(),f.getcomptype())!=(48000,4,3,'NONE'):
            raise ValueError('REQUIRED_WAV_PCM24_48K_4CH')
        total=f.getnframes()
        if total>2880000 or start<0:
            raise ValueError('AUDIO_DURATION_BOUND')
        n=total if frames is None else frames
        if n<24000 or start+n>total:
            raise ValueError('WINDOW_BOUND')
        f.setpos(start);raw=f.readframes(n)
        if len(raw)!=n*12:raise ValueError('TRUNCATED_WAV')
    return raw,n/48000


def convert(backend, raw):
    if not raw or len(raw)%12:raise ValueError('PCM_BYTE_LENGTH')
    n=len(raw)//12
    backend.p.stdin.write(b'D'+struct.pack('<I',n));backend.p.stdin.write(raw);backend.p.stdin.flush()
    count,=struct.unpack('<I',backend.read(4))
    if count!=n:raise RuntimeError('PCM_RESULT_LENGTH')
    values=array.array('f');values.frombytes(backend.read(count*4))
    return values


def fast_decoder(backend,path):
    raw,duration=read_raw(path)
    return convert(backend,raw),duration


def pcm_bench(backend,path,rid):
    rows=[]
    for repeat in range(2):
        a=time.perf_counter();old,duration=read_mic0(path);b=time.perf_counter()
        raw,_=read_raw(path);c=time.perf_counter();new=convert(backend,raw);d=time.perf_counter()
        if old.tobytes()!=new.tobytes():raise ValueError('PCM_NOT_BIT_EXACT')
        rows.append({'id':rid,'run':repeat+1,'samples':len(new),'input_seconds':duration,
                     'python_read_convert_seconds':b-a,'c_read_seconds':c-b,
                     'c_convert_pipe_seconds':d-c,'c_read_convert_seconds':d-b,'bit_exact':True})
    return rows


def short_extract(backend,source,ref,config,model='int8',trace=None):
    start=time.perf_counter()
    raw,duration=read_raw(source,ref['anchor_sample16']*3,int(ref['duration']*48000))
    loaded=time.perf_counter();mic=convert(backend,raw);decoded=time.perf_counter()
    audio=backend.run('P',mic);prepared=time.perf_counter()
    probs=backend.run('V',audio) if audio else []
    spans=spans_from_probs(probs,len(audio));coverage=sum(b-a for a,b in spans)/len(audio) if audio else 0.
    vadded=time.perf_counter()
    # Measure each window's network even if VAD rejects it, to expose raw-score
    # quality separately from gating. No speech fragments are concatenated.
    feat=backend.run('F',audio) if audio else []
    featured=time.perf_counter()
    vec=backend.run('E',feat) if feat else []
    embedded=time.perf_counter()
    score=sum(a*b for a,b in zip(unit(vec),config['template'])) if vec else None
    if score is not None:score=max(-1.,min(1.,score))
    raw_state='insufficient' if score is None else 'target' if score>=config['high'] else 'non_target' if score<=config['low'] else 'insufficient'
    state=raw_state if coverage>=config['vad_coverage_min'] else 'insufficient'
    total=time.perf_counter()-start
    result={'id':ref['id'],'model':model,'recording_id':ref['recording_id'],'window_seconds':duration,
            'spans':spans,'vad_coverage':coverage,'frames':len(feat)//80,'score':score,
            'raw_state':raw_state,'state':state,'read_seconds':loaded-start,
            'pcm_convert_seconds':decoded-loaded,'resample_seconds':prepared-decoded,
            'vad_seconds':vadded-prepared,'fbank_seconds':featured-vadded,
            'embedding_seconds':embedded-featured,'total_seconds':total,
            'rtf_window':total/duration,'wait_then_compute_seconds':duration+total,
            'live_capture':False}
    if trace is not None:trace.update(mic=mic,audio=audio,probs=probs,features=feat,embedding=vec)
    return result


def check_short(result,ref,model):
    key='score' if model=='int8' else 'fp32_score'
    raw_key='raw_state' if model=='int8' else 'fp32_raw_state'
    expected=ref[raw_key] if ref['vad_coverage']>=.5 else 'insufficient'
    if result['spans']!=ref['spans'] or result['frames']!=ref['frames'] or result['state']!=expected or result['raw_state']!=ref[raw_key]:
        raise ValueError('SHORT_REFERENCE_STATE_OR_SHAPE')
    if result['score'] is None or abs(result['score']-ref[key])>.002:
        raise ValueError('SHORT_REFERENCE_SCORE')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['bench','all','full','pcm'])
    p.add_argument('--model',choices=['int8','fp32'],default='int8');p.add_argument('--output',required=True)
    args=p.parse_args();root=Path(__file__).resolve().parent
    if sys.byteorder!='little':raise ValueError('LITTLE_ENDIAN_REQUIRED')
    if args.action in ('full','pcm') and args.model!='int8':raise ValueError('FULL_PCM_REQUIRE_INT8')
    cfg=json.loads((root/'short-cases.json').read_text());fullcfg=json.loads((root/'cases.json').read_text())
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True);result_path=output/'result.json'
    if result_path.exists():raise ValueError('RESULT_ALREADY_EXISTS')
    result={'status':'RUNNING','scope':'OFFLINE_WINDOW_EVALUATION','model':args.model,'pcm':[],'runs':[],
            'thresholds_unchanged':True,'motion_commands':0,'recognition_qualified':False}
    backend=None
    try:
        begin=time.perf_counter()
        backend=Backend(root,model_filename='int8-head.onnx' if args.model=='int8' else 'fp32-opt.onnx')
        result['startup_seconds']=time.perf_counter()-begin;result.update(backend.loads)
        print('SHORT_MODE='+args.model+' '+json.dumps(backend.loads),flush=True)
        if args.action in ('bench','pcm'):
            for rid in fullcfg['groups']['pair']:
                for row in pcm_bench(backend,root/'full-audio'/(rid+'.wav'),rid):
                    result['pcm'].append(row);print('PCM_COMPARE='+json.dumps(row),flush=True)
        if args.action=='full':
            for repeat in range(2):
                for rid in fullcfg['groups']['pair']:
                    r=extract(backend,root/'full-audio'/(rid+'.wav'),cfg['template'],cfg['low'],cfg['high'],decoder=lambda path:fast_decoder(backend,path))
                    check_reference(r,fullcfg['references'][rid]);r.update(id=rid,run=repeat+1,reference_pass=True)
                    result['runs'].append(r);print(json.dumps(r),flush=True)
        elif args.action in ('bench','all'):
            ids=cfg['groups']['bench' if args.action=='bench' else 'all']
            for repeat in range(2 if args.action=='bench' else 1):
                for fid in ids:
                    ref=cfg['references'][fid]
                    r=short_extract(backend,root/'full-audio'/(ref['recording_id']+'.wav'),ref,cfg,args.model)
                    check_short(r,ref,args.model);r.update(run=repeat+1,reference_pass=True)
                    result['runs'].append(r);print(json.dumps(r),flush=True)
            result['timing_summary']={str(d):{'mean_total_seconds':statistics.mean(r['total_seconds'] for r in result['runs'] if r['window_seconds']==d),
                'mean_core_seconds':statistics.mean(r['embedding_seconds'] for r in result['runs'] if r['window_seconds']==d)} for d in cfg['lengths']}
            print('WINDOW_TIMING='+json.dumps(result['timing_summary']),flush=True)
        result['backend_peak_rss_mib']=backend.rss()
        result['driver_peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.
        backend.close();backend=None;result['status']='PASS'
    except BaseException as exc:
        result.update(status='FAIL',error=repr(exc));raise
    finally:
        if backend is not None:backend.close(force=True)
        with result_path.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print('SHORT_BENCH=PASS NUMERICAL_ONLY=1 RECOGNITION_QUALIFIED=0 LIVE_CAPTURE=0 MOTION_COMMANDS=0',flush=True)


if __name__=='__main__':main()
