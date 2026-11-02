"""Causal offline DOA candidates. Original artifacts and board settings stay unchanged.

All variants keep >=4 qualified pairs, physical tau bound +0.125 samples,
residual <=0.5 samples, and direction norm 0.85..1.15. Multi-frame support
uses only past/current windows; it is diagnostic, not a production runtime.
"""
import collections, json, time, wave
from pathlib import Path
import numpy as np
from analyze_raw import quant, spread

ROOT=Path(__file__).resolve().parent
PAIRS=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
SCANS=(6,8,6,6,8,6)
COORD=np.array([[40/np.sqrt(3),0,-40*np.sqrt(2/3)/4],
                [-20/np.sqrt(3),20,-40*np.sqrt(2/3)/4],
                [-20/np.sqrt(3),-20,-40*np.sqrt(2/3)/4],
                [0,0,30*np.sqrt(2/3)]])
A=np.array([COORD[b]-COORD[a] for a,b in PAIRS])*48/343
BOUND=np.linalg.norm(A,axis=1)+.125

def load():
    with wave.open(str(ROOT/'raw/four_mic.wav'),'rb') as w:
        b=np.frombuffer(w.readframes(w.getnframes()),np.uint8).reshape(-1,3).astype(np.int32)
    v=b[:,0]|(b[:,1]<<8)|(b[:,2]<<16)
    x=((v^0x800000)-0x800000).reshape(-1,4).astype(float)
    rows=json.loads((ROOT/'raw-replay-rows.json').read_text())
    hann=np.array([int(s,16) for s in (ROOT/'reference/hardware/hann-u18f17.mem').read_text().split()])/131072.
    ft=np.array([np.fft.rfft(np.rint(x[r['sample_start']:r['sample_start']+1024]*hann[:,None]),axis=0) for r in rows])
    cross=np.array([ft[:,:,a]*ft[:,:,b].conj() for a,b in PAIRS]).transpose(1,0,2)
    return rows,cross

def masks_and_phat(cross):
    p=np.abs(cross)**2
    mask=np.zeros(p.shape,bool)
    mask[...,7:86]=(p[...,7:86]>0)&(2500*p[...,7:86]>=p[...,7:86].max(axis=-1,keepdims=True))
    ph=np.zeros(cross.shape,complex)
    ph[mask]=cross[mask]/np.abs(cross[mask])
    return mask,ph

def solve_taus(alltau):
    ids=[];taus=[]
    for i,tau in enumerate(alltau):
        if tau is not None and abs(tau)<=BOUND[i]:ids.append(i);taus.append(tau)
    result=dict(reason='few',valid_pairs=len(ids),taus=alltau)
    if len(ids)<4:return result
    mat=A[ids];g=mat.T@mat
    if np.linalg.matrix_rank(g)<3 or np.linalg.cond(g,np.inf)>100:
        result['reason']='condition';return result
    u=np.linalg.solve(g,mat.T@taus);norm=float(np.linalg.norm(u))
    residual=float(np.sqrt(np.mean((mat@u-taus)**2)))
    result.update(norm=norm,residual=residual,u=u.tolist())
    result['reason']='residual' if residual>.5 else ('norm' if not .85<=norm<=1.15 else 'valid')
    return result

def solve_spectrum(spectrum,counts):
    corr=np.fft.irfft(spectrum,n=1024,axis=-1)
    alltau=[None]*6
    for i in range(6):
        if counts[i]<12:continue
        lags=np.arange(-SCANS[i],SCANS[i]+1)
        lag=int(lags[np.argmax(corr[i,lags%1024])])
        # Same Q12 interpolation convention as the checked baseline.
        rm,p,rp=np.rint(corr[i,np.array([lag-1,lag,lag+1])%1024]*2**24).astype(np.int64)
        den=int(rm-2*p+rp)
        delta=0 if den==0 else np.rint((int(rm)-int(rp))*2048/den)
        tau=float(lag+np.clip(delta,-2048,2048)/4096)
        alltau[i]=tau
    return solve_taus(alltau)

def summarize(rows,out):
    selected=[(r,o) for r,o in zip(rows,out) if r['high']]
    accepted=[(r,o) for r,o in selected if o['reason']=='valid']
    jumps=[];run=longest=0;previous=None;last_u=None
    for r,o in zip(rows,out):
        if not r['high'] or o['reason']!='valid':run=0;previous=None;last_u=None;continue
        u=np.array(o['u']);u/=np.linalg.norm(u)
        if previous is not None and r['sequence']==previous+1:
            run+=1;jumps.append(float(np.degrees(np.arccos(np.clip(last_u@u,-1,1)))))
        else:run=1
        longest=max(longest,run);previous=r['sequence'];last_u=u
    mid=len(rows)//2
    return dict(counts=dict(collections.Counter(o['reason'] for r,o in selected)),
                accepted=len(accepted),denominator=len(selected),
                direction=spread([o['u'] for r,o in accepted]),
                consecutive_jump_degrees=quant(jumps),longest_valid_high_run=longest,
                residual_valid_quantiles=quant([o['residual'] for r,o in accepted]),
                halves=[dict(high=sum(r['high'] for r in rr),valid=sum(r['high'] and o['reason']=='valid' for r,o in zip(rr,oo)),direction=spread([o['u'] for r,o in zip(rr,oo) if r['high'] and o['reason']=='valid'])) for rr,oo in ((rows[:mid],out[:mid]),(rows[mid:],out[mid:]))])

def run(rows,cross,kind,history):
    mask,ph=masks_and_phat(cross)
    out=[]
    for i in range(len(rows)):
        # Continuous frames only. This file has no gaps; enforce rather than bridge gaps silently.
        start=max(0,i-history+1)
        for j in range(start+1,i+1):
            if rows[j]['sequence']!=rows[j-1]['sequence']+1:start=j
        if kind=='raw_mean':
            mm,pp=masks_and_phat(cross[start:i+1].mean(axis=0))
            counts=mm.sum(axis=-1)
        elif kind=='phat_mean':
            pp=ph[start:i+1].mean(axis=0);counts=mask[start:i+1].any(axis=0).sum(axis=-1)
        elif kind=='observed_mean':
            hits=mask[start:i+1].sum(axis=0)
            pp=ph[start:i+1].sum(axis=0)/np.maximum(hits,1)
            # At least two observations; one noisy bin cannot enter from a single frame.
            keep=hits>=2;pp[~keep]=0;counts=keep.sum(axis=-1)
        elif kind=='feature_median':
            taus=[]
            for p in range(6):
                values=[r['result']['pairs'][p]['tau_q12']/4096 for r in rows[start:i+1]
                        if r['result']['pairs'][p]['qualified']]
                taus.append(float(np.median(values)) if len(values)>=2 else None)
            o=solve_taus(taus)
            o.update(history_frames=i-start+1,start_sample=rows[start]['sample_start'],end_sample=rows[i]['sample_start']+1024)
            out.append(o);continue
        elif kind=='baseline':
            pp=ph[i];counts=mask[i].sum(axis=-1)
        else:raise ValueError(kind)
        o=solve_spectrum(pp,counts)
        o.update(history_frames=i-start+1,start_sample=rows[start]['sample_start'],end_sample=rows[i]['sample_start']+1024)
        out.append(o)
    return out

def main():
    rows,cross=load();reports=[];outputs={}
    variants=[('baseline',1)]+[(kind,h) for kind in ('raw_mean','phat_mean','observed_mean','feature_median') for h in (4,8,16)]
    for kind,h in variants:
        name=f'{kind}_{h}';t=time.perf_counter();out=run(rows,cross,kind,h)
        report=dict(name=name,history_frames=h,audio_support_ms=(1024+512*(h-1))/48,
                    nominal_history_center_extra_age_ms=512*(h-1)/96,
                    host_wall_seconds=time.perf_counter()-t,**summarize(rows,out))
        if kind=='baseline':assert report['counts']==dict(norm=48,valid=14,few=170,residual=44)
        reports.append(report);outputs[name]=out
        print(json.dumps(report,ensure_ascii=False),flush=True)
    (ROOT/'candidate-study.json').write_text(json.dumps(dict(scope='CAUSAL_SINGLE_RECORDING_EXPLORATORY_NO_GROUND_TRUTH',variants=reports),indent=2))
    (ROOT/'candidate-rows.json').write_text(json.dumps(outputs,indent=2))

if __name__=='__main__':main()
