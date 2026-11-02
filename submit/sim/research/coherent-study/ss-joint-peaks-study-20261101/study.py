"""Frozen offline multi-recording peak study. No product or device mutations."""
import itertools,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
REF=ROOT.parent/'ss-c-3d-analysis-20261101'
sys.path[:0]=[str(REF),str(ROOT.parent/'ss-ab-3d-analysis-20261101')]
from study_candidates import PAIRS,SCANS,A,BOUND,masks_and_phat,solve_spectrum,solve_taus,summarize,run
from study_weighting import run_weighted
from analyze_ab import wav24

VARIANTS=('float1','phat16','raw16','coherent16','joint1','joint16')
DATASETS=[('A_STATIC','ss-ab-3d-analysis-20261101/A','rows.json',0),
          ('B_STATIC','ss-b-static-3d-analysis-20261101/B_STATIC','rows.json',180),
          ('B_DYNAMIC','ss-ab-3d-analysis-20261101/B','rows.json',None),
          ('USER_SPEECH','ss-user-3d-analysis-20261101','rows.json',0),
          ('C_SPEECH_UNCONTROLLED','ss-c-3d-analysis-20261101','raw-replay-rows.json',None)]

def interpolate(c,lag):
    rm,p,rp=np.rint(c[np.array([lag-1,lag,lag+1])%1024]*2**24).astype(np.int64)
    den=int(rm-2*p+rp)
    delta=0 if den==0 else np.rint((int(rm)-int(rp))*2048/den)
    return float(lag+np.clip(delta,-2048,2048)/4096)

def joint(spectrum,counts):
    base=solve_spectrum(spectrum,counts)
    corr=np.fft.irfft(spectrum,n=1024,axis=-1)
    options=[]
    for i in range(6):
        if counts[i]<12:options.append([(None,0.)]);continue
        lags=np.arange(-SCANS[i],SCANS[i]+1)
        peak=int(lags[np.argmax(corr[i,lags%1024])]);height=float(corr[i,peak%1024])
        choices=[(interpolate(corr[i],peak),1.)]
        others=[int(lag) for lag in lags if lag!=peak and height>0 and corr[i,lag%1024]>=.8*height
                and corr[i,lag%1024]>corr[i,(lag-1)%1024] and corr[i,lag%1024]>=corr[i,(lag+1)%1024]]
        if others:
            other=max(others,key=lambda lag:corr[i,lag%1024])
            choices.append((interpolate(corr[i],other),float(corr[i,other%1024]/height)))
        options.append(choices)
    base.update(alternative_pairs=sum(len(c)>1 for c in options),joint_changed=False)
    if base['reason']=='valid':return base
    best=None;best_key=None
    for combo in itertools.product(*options):
        taus=[v[0] for v in combo];r=solve_taus(taus)
        if r['reason']!='valid':continue
        ids=[i for i,t in enumerate(taus) if t is not None and abs(t)<=BOUND[i]]
        rank=(len(ids),float(np.mean([combo[i][1] for i in ids])),-r['residual'])
        if best_key is None or rank>best_key:best,best_key=r,rank
    if best is None:return base
    best.update(alternative_pairs=base['alternative_pairs'],joint_changed=True)
    return best

def joint_run(rows,cross,h):
    mask,ph=masks_and_phat(cross);out=[]
    for i in range(len(rows)):
        start=max(0,i-h+1)
        for j in range(start+1,i+1):
            if rows[j]['sequence']!=rows[j-1]['sequence']+1:start=j
        out.append(joint(ph[start:i+1].mean(0),mask[start:i+1].any(0).sum(-1)))
    return out

def variant(rows,cross,name):
    if name=='float1':return run(rows,cross,'baseline',1)
    if name=='phat16':return run(rows,cross,'phat_mean',16)
    if name=='raw16':return run(rows,cross,'raw_mean',16)
    if name=='coherent16':return run_weighted(rows,cross,dict(lo=7,history=16,weight='coherent_support'))
    if name=='joint1':return joint_run(rows,cross,1)
    if name=='joint16':return joint_run(rows,cross,16)
    raise ValueError(name)

def metrics(rows,out,az):
    result=summarize(rows,out)
    accepted=[o for r,o in zip(rows,out) if r['high'] and o['reason']=='valid']
    result['alternative_peak_windows']=sum(r['high'] and o.get('alternative_pairs',0)>0 for r,o in zip(rows,out))
    result['joint_rescued_windows']=sum(r['high'] and o.get('joint_changed',False) for r,o in zip(rows,out))
    if az is not None and accepted:
        u=np.array([o['u'] for o in accepted]);u/=np.linalg.norm(u,axis=1,keepdims=True)
        expected=np.array([np.cos(np.radians(az)),np.sin(np.radians(az)),0])
        err=np.degrees(np.arccos(np.clip(u@expected,-1,1)))
        result['approx_direction_error_p50_p90']=np.quantile(err,[.5,.9]).tolist()
        result['approx_direction_over_90deg']=int(sum(err>90))
        result['direction_caveat']='Intended horizontal direction only; not surveyed ground truth'
    return result

def cross_from_pcm(x,rows):
    hann=np.array([int(s,16) for s in (REF/'reference/hardware/hann-u18f17.mem').read_text().split()])/131072.
    ft=np.array([np.fft.rfft(np.rint(x[r['sample_start']:r['sample_start']+1024].astype(float)*hann[:,None]),axis=0) for r in rows])
    return np.array([ft[:,:,a]*ft[:,:,b].conj() for a,b in PAIRS]).transpose(1,0,2)

def fixtures():
    n=128;rows=[dict(sequence=i,sample_start=512*i,high=True) for i in range(n)]
    k=np.arange(513);reports=[]
    # Ideal cross spectra with exact plane-wave phase. Independently checks sign and angle.
    for az,el in [(0,0),(180,0),(90,20),(-90,-20),(45,45)]:
        u=np.array([np.cos(np.radians(el))*np.cos(np.radians(az)),np.cos(np.radians(el))*np.sin(np.radians(az)),np.sin(np.radians(el))])
        cross=np.broadcast_to(np.exp(-2j*np.pi*(A@u)[:,None]*k[None,:]/1024),(n,6,513)).copy()
        cross[:,:,:7]=0;cross[:,:,86:]=0
        for name in VARIANTS:
            out=variant(rows,cross,name);errors=[]
            for r in out[15:]:
                assert r['reason']=='valid',(az,el,name,r)
                v=np.array(r['u']);v/=np.linalg.norm(v)
                errors.append(float(np.degrees(np.arccos(np.clip(v@u,-1,1)))))
            assert max(errors)<1,(az,el,name,max(errors))
            reports.append(dict(test='ideal_phase',az=az,el=el,variant=name,max_error_deg=max(errors)))
    zeros=np.zeros((n,6,513),complex)
    for name in VARIANTS:
        out=variant(rows,zeros,name);accepted=sum(o['reason']=='valid' for o in out)
        assert accepted==0
        reports.append(dict(test='silence',variant=name,accepted=accepted,frames=n))
    # Negative control: independent bandlimited channel noise at audible amplitude.
    # Measure false acceptance; do not silently count this as a passing test.
    n=510;rows=[dict(sequence=i,sample_start=512*i,high=True) for i in range(n)]
    rng=np.random.default_rng(20261101)
    count=512*(n-1)+1024
    z=rng.normal(size=(count,4));spec=np.fft.rfft(z,axis=0);freq=np.fft.rfftfreq(count,1/48000)
    spec[(freq<400)|(freq>3800)]=0
    x=np.fft.irfft(spec,n=count,axis=0);x*=40000/np.std(x,axis=0)
    cross=cross_from_pcm(x,rows)
    for name in VARIANTS:
        out=variant(rows,cross,name)
        reports.append(dict(test='independent_noise',variant=name,**metrics(rows,out,None)))
    return reports

def main():
    reports=[];outputs={}
    checks=fixtures();(ROOT/'fixtures.json').write_text(json.dumps(checks,indent=2))
    for label,folder,rowfile,az in DATASETS:
        folder=ROOT.parent/folder;rows=json.loads((folder/rowfile).read_text());x=wav24(folder/'raw/four_mic.wav')
        for r in rows:
            if 'native' not in r:
                o=r['result'];r['native']=dict(reason={0:'valid',1:'few',2:'condition',3:'residual',4:'norm'}[o['reason']],u=[o[k] for k in ('ux','uy','uz')],norm=o['norm'],residual=o['residual_rms_samples'])
        cross=cross_from_pcm(x,rows);outputs[label]={}
        baseline=metrics(rows,[r['native'] for r in rows],az)
        reports.append(dict(dataset=label,variant='production_C',**baseline))
        print(label,'production_C',baseline['accepted'],baseline['denominator'],flush=True)
        for name in VARIANTS:
            start=time.perf_counter();out=variant(rows,cross,name)
            result=dict(dataset=label,variant=name,host_wall_seconds=time.perf_counter()-start,**metrics(rows,out,az))
            reports.append(result);outputs[label][name]=out
            print(label,name,result['accepted'],result['counts'],result['direction'],flush=True)
        (ROOT/(label+'-rows.json')).write_text(json.dumps(outputs[label]))
    (ROOT/'results.json').write_text(json.dumps(dict(scope='OFFLINE_EXPLORATORY_NOT_BOARD_ACCEPTANCE',variants=list(VARIANTS),reports=reports),indent=2))

if __name__=='__main__':main()
