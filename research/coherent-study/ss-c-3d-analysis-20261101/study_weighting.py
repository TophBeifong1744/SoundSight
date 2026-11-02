"""Second offline batch: bounded predeclared band/weight comparisons.

No new source/servo configuration, no lowered physical acceptance thresholds.
"""
import json, time
import numpy as np
from study_candidates import ROOT,load,solve_spectrum,summarize

VARIANTS=[
    dict(name='previous_phat16',history=16,lo=7,weight='flat'),
    dict(name='highpass750_8',history=8,lo=16,weight='flat'),
    dict(name='highpass750_16',history=16,lo=16,weight='flat'),
    dict(name='highpass1031_8',history=8,lo=22,weight='flat'),
    dict(name='highpass1031_16',history=16,lo=22,weight='flat'),
    dict(name='sqrt_frequency_8',history=8,lo=7,weight='sqrt_frequency'),
    dict(name='sqrt_frequency_16',history=16,lo=7,weight='sqrt_frequency'),
    dict(name='phase_coherence_8',history=8,lo=7,weight='phase_coherence'),
    dict(name='phase_coherence_16',history=16,lo=7,weight='phase_coherence'),
    dict(name='coherent_support_16',history=16,lo=7,weight='coherent_support'),
]

def run_weighted(rows,cross,config):
    lo=config['lo'];h=config['history'];weight=config['weight']
    p=np.abs(cross)**2;mask=np.zeros(p.shape,bool)
    mask[...,lo:86]=(p[...,lo:86]>0)&(2500*p[...,lo:86]>=p[...,lo:86].max(axis=-1,keepdims=True))
    ph=np.zeros(cross.shape,complex);ph[mask]=cross[mask]/np.abs(cross[mask])
    out=[]
    for i in range(len(rows)):
        start=max(0,i-h+1)
        for j in range(start+1,i+1):
            if rows[j]['sequence']!=rows[j-1]['sequence']+1:start=j
        pp=ph[start:i+1].mean(axis=0);hits=mask[start:i+1].sum(axis=0)
        keep=hits>0
        if weight=='sqrt_frequency':pp*=np.sqrt(np.arange(513)*48000/1024/1000)[None,:]
        elif weight in ('phase_coherence','coherent_support'):
            coherence=np.abs(ph[start:i+1].sum(axis=0))/np.maximum(hits,1)
            pp*=coherence**2
            if weight=='coherent_support':
                # Fixed before examining this variant: >=4 observations and phase concentration >=0.7.
                keep=(hits>=4)&(coherence>=.7);pp[~keep]=0
        elif weight!='flat':raise ValueError(weight)
        o=solve_spectrum(pp,keep.sum(axis=-1))
        o.update(history_frames=i-start+1,start_sample=rows[start]['sample_start'],end_sample=rows[i]['sample_start']+1024)
        out.append(o)
    return out

def main():
    rows,cross=load();reports=[];outputs={}
    for config in VARIANTS:
        t=time.perf_counter();out=run_weighted(rows,cross,config)
        s=summarize(rows,out)
        if config['name']=='previous_phat16':assert s['accepted']==68
        report=dict(config=config,host_wall_seconds=time.perf_counter()-t,**s)
        reports.append(report);outputs[config['name']]=out
        print(json.dumps(report),flush=True)
    (ROOT/'weighting-study.json').write_text(json.dumps(dict(scope='EXPLORATORY_SAME_RECORDING_NO_GROUND_TRUTH',variants=reports),indent=2))
    (ROOT/'weighting-rows.json').write_text(json.dumps(outputs,indent=2))

if __name__=='__main__':main()
