"""A/B evidence analysis. B moved during acquisition: no fixed-delay calibration."""
import collections,json,struct,sys,wave
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly,correlate
ROOT=Path(__file__).resolve().parent
REF=ROOT.parent/'ss-c-3d-analysis-20261101'
sys.path[:0]=[str(REF),str(REF/'reference/software/tetra3d/linux')]
from solver_3d import Solver3D
from study_candidates import PAIRS,run,summarize
from analyze_raw import quant,spread

def wav24(p):
    with wave.open(str(p),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(4,3,48000)
        b=np.frombuffer(w.readframes(w.getnframes()),np.uint8).reshape(-1,3).astype(np.int32)
    v=b[:,0]|(b[:,1]<<8)|(b[:,2]<<16)
    return ((v^0x800000)-0x800000).reshape(-1,4)

def matching(x,reference):
    # Use complete 0.5-second blocks; no alignment assumed from wall-clock times.
    y=resample_poly(x[:,0].astype(float),1,6);y-=y.mean()
    n=4000;energy=np.r_[0,np.cumsum(reference**2)]
    refnorm=np.sqrt(np.maximum(energy[n:]-energy[:-n],1e-30));out=[]
    for i in range(0,len(y)-n+1,n):
        block=y[i:i+n];block=block-block.mean();norm=np.linalg.norm(block)
        if norm<1e-12:out.append(dict(time=i/8000,correlation=0));continue
        score=correlate(reference,block,mode='valid',method='fft')/refnorm/norm
        index=int(np.argmax(np.abs(score)))
        out.append(dict(time=i/8000,reference_time=index/8000,correlation=float(score[index]),rms=float(np.sqrt(np.mean(block**2)))))
    return out

def describe(rows,indices):
    selected=[rows[i] for i in indices];good=[r['native'] for r in selected if r['native']['reason']=='valid']
    return dict(count=len(selected),reasons=dict(collections.Counter(r['native']['reason'] for r in selected)),
                level_quantiles=quant([r['level'] for r in selected]),
                direction=spread([o['u'] for o in good]),
                norm_quantiles=quant([r['native']['norm'] for r in selected if r['native']['reason'] in ('valid','residual','norm')]),
                pair_tau_quantiles={f'{a}{b}':quant([r['result']['pairs'][k]['tau_q12']/4096 for r in selected if r['result']['pairs'][k]['reason'] in (0,3)]) for k,(a,b) in enumerate(PAIRS)})

def main():
    with wave.open(str(ROOT.parent/'ss-user-3d-analysis-20261101/localization-broadband-30s.wav'),'rb') as w:
        full_reference=np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(float)
    reference=resample_poly(full_reference,1,6);reference-=reference.mean()
    fixture=matching(np.repeat(full_reference[96000:144000,None],4,axis=1),reference)
    assert all(abs(r['reference_time']-(2+r['time']))<.002 and r['correlation']>.9 for r in fixture)
    geo=json.loads((REF/'reference/software/tetra3d/core/tetra40-nominal.json').read_text())
    solver=Solver3D(REF/'reference/solver.dll',geo)
    hann=np.array([int(s,16) for s in (REF/'reference/hardware/hann-u18f17.mem').read_text().split()])/131072.
    names={0:'valid',1:'few',2:'condition',3:'residual',4:'norm'}
    reports=[]
    for label,epoch in [('A',38),('B',39)]:
        folder=ROOT/label;d=json.loads((folder/'raw/result.json').read_text());x=wav24(folder/'raw/four_mic.wav')
        assert d['result']=='PASS' and d['epoch']==epoch and len(d['packets'])==1024
        packets=(folder/'raw/packets.bin').read_bytes()
        assert len(packets)==1024*8224 and len(x)==1024*512
        for i,p in enumerate(d['packets']):
            raw=packets[i*8224:(i+1)*8224]
            assert struct.unpack_from('<8I',raw)==(0x43505353,0x00200001,epoch,i,i*512,0,512,8192)
            assert np.array_equal(np.frombuffer(raw[32:],'<i4').reshape(-1,4),x[i*512:(i+1)*512])
            assert p==dict(epoch=epoch,block_seq=i,sample_start=i*512,sample_count=512,clipped=False)
        assert all(b['sequence']==a['sequence']+1 for a,b in zip(d['frames'],d['frames'][1:]))
        rows=[];ft=[]
        for f in d['frames']:
            a=f.get('audio',{})
            if not(a.get('valid') and a.get('covered_by_recording')):continue
            assert a['epoch']==epoch and a['sample_count']==1024 and not f['fault'] and not f['drops']
            s=a['sample_start'];assert 0<=s<=len(x)-1024
            xx=x[s:s+1024].astype(float);o=solver.solve(f);assert o['bridge_status']==o['api_status']==0
            level=float(np.abs(xx).mean())
            rows.append(dict(sequence=f['sequence'],sample_start=s,level=level,pl_level=f['energy'],high=level>=12000,
                             result=o,native=dict(reason=names.get(o['reason'],str(o['reason'])),u=[o[k] for k in ('ux','uy','uz')],
                                                 norm=o['norm'],residual=o['residual_rms_samples']),
                             masks=[(f['words'][5*i]>>16)&127 for i in range(6)]))
            ft.append(np.fft.rfft(np.rint(xx*hann[:,None]),axis=0))
        ft=np.array(ft);cross=np.array([ft[:,:,a]*ft[:,:,b].conj() for a,b in PAIRS]).transpose(1,0,2)
        native=[r['native'] for r in rows];floatbase=run(rows,cross,'baseline',1);candidate=run(rows,cross,'phat_mean',16)
        match=matching(x,reference)
        # Diagnostic matching gate only; retain all raw results so exclusion is auditable.
        matched_ids=[i for i,r in enumerate(rows) if r['sample_start']//24000<len(match) and
                     (r['sample_start']+1023)//24000==r['sample_start']//24000 and
                     abs(match[r['sample_start']//24000]['correlation'])>=.2]
        high_ids=[i for i,r in enumerate(rows) if r['high']]
        report=dict(label=label,epoch=epoch,packet_wav_bit_exact=True,seconds=len(x)/48000,covered=len(rows),
                    faults=[dict(sequence=f['sequence'],fault=f['fault'],audio_valid=f.get('audio',{}).get('valid')) for f in d['frames'] if f['fault']],
                    first_fault=d['first_fault'],final_ps=d['final_ps'],
                    all=describe(rows,range(len(rows))),high=describe(rows,high_ids),
                    matched_playback=describe(rows,matched_ids),
                    matching=match,
                    native_summary=summarize(rows,native),float_summary=summarize(rows,floatbase),candidate_summary=summarize(rows,candidate),
                    native_float_reason_equal=sum(a['reason']==b['reason'] for a,b in zip(native,floatbase)),
                    seconds_summary=[dict(second=second,**describe(rows,[i for i,r in enumerate(rows) if second<=r['sample_start']/48000<second+1])) for second in range(11)])
        (folder/'rows.json').write_text(json.dumps(rows,indent=2));(folder/'candidate.json').write_text(json.dumps(candidate,indent=2))
        reports.append(report)
        print(label,'all',report['all']['reasons'],'high',report['high']['count'],report['high']['reasons'],'center',report['high']['direction'])
        print('MATCHES',label,json.dumps(match))
        for s in report['seconds_summary']:print('SECOND',label,s['second'],s['level_quantiles'],s['reasons'],s['direction'])
    (ROOT/'analysis.json').write_text(json.dumps(dict(scope='AB_RECORDING_ANALYSIS_B_MOVED_AND_DISTANCE_CHANGED_NOT_CALIBRATION',reports=reports),indent=2))

if __name__=='__main__':main()
