"""Generate nominal tetra40 analytic feature fixtures, NOT microphone recordings."""
from pathlib import Path
import argparse
import copy
import json
import math
import random

PAIRS=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
# Frozen ABI flags: raw/second/IFFT qualified + PHAT/IFFT stage OK.
FLAGS=0x11003800


def pair_from_tau(tau):
    q=round(tau*4096);lag=round(q/4096);delta=q-lag*4096
    return dict(lag=lag,peak=100000,r_minus=95904-2*delta,r_plus=95904+2*delta,
                second_peak=10000,mask_count=79,flags=FLAGS)


def frame(ident,az,el,noise=None):
    # Analytic physical layout and forward arrivals; does not call inverse code
    # or load solver's geometry coordinates when synthesizing the input.
    h=40*math.sqrt(2/3);x=40/math.sqrt(3)
    xyz=((x,0,-h/4),(-x/2,20,-h/4),(-x/2,-20,-h/4),(0,0,3*h/4))
    a,e=math.radians(az),math.radians(el)
    u=(math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e))
    arrivals=[-sum(p[k]*u[k] for k in range(3))*48/343 for p in xyz]
    pairs=[pair_from_tau(arrivals[a]-arrivals[b]+(noise[i] if noise else 0)) for i,(a,b) in enumerate(PAIRS)]
    return dict(frame_id=ident,flags=16,pairs=pairs,
                reference=dict(kind='SYNTHETIC',source_id='analytic-forward-tetra40-v1',azimuth_deg=az,elevation_deg=el))


def metadata():
    return dict(schema='SS_3D_FEATURE_REPLAY_V1',session_id='tetra40-demo-v1',source_kind='SYNTHETIC_FEATURES',
                source_id='analytic-six-pair-demo-v1',geometry_revision=1,geometry_source_id='tetra40-nominal-v1',
                pair_order=['01','02','03','12','13','23'])


def demo():
    frames=[]
    for el in (-60,-30,0,30,60):
        for az in (-180,-135,-90,-45,0,45,90,135):
            frames.append(frame(len(frames)+1,az,el))
    frames.extend([frame(41,75,90),frame(42,-125,-90)])
    rng=random.Random(20261018)
    for i in range(12):
        frames.append(frame(len(frames)+1,-150+25*i,-40+8*(i%10),[rng.uniform(-.05,.05) for _ in range(6)]))
    f=frame(55,45,30);f['pairs'][0]['mask_count']=0;frames.append(f)
    f=frame(56,45,30)
    for p in f['pairs'][:3]:p['mask_count']=0
    frames.append(f)
    f=frame(57,0,0);f['pairs']=[pair_from_tau(0) for _ in PAIRS];frames.append(f)
    f=frame(58,0,0);f['pairs'][0]=pair_from_tau(4);frames.append(f)
    f=frame(59,45,30);f['flags']|=0x100000;frames.append(f)
    f=frame(60,45,30);f['pairs'][0]['flags']|=0x8000;frames.append(f)
    f=frame(61,0,0);f['flags']|=8;frames.append(f)
    f=frame(62,45,30);f['pairs'][0]['lag']=32;frames.append(f)
    f=frame(63,45,30);f['pairs'][0]['flags']=0;frames.append(f)
    f=frame(64,45,30);f['flags']=0;frames.append(f)
    f=frame(65,45,30);f['reference']=None;frames.append(f)
    frames.append(copy.deepcopy(f)) # duplicate ID: do not solve twice
    frames.append(frame(63,-45,-30)) # backward: last forward ID stays65
    frames.append(frame(68,-45,-30)) # gap2, not proven physical frame loss
    return [metadata(),*frames]


def write_jsonl(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as out:
        for item in records:out.write(json.dumps(item,allow_nan=False)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    try:write_jsonl(args.out,demo())
    except (OSError,ValueError) as e:ap.exit(2,str(e)+'\n')
    print('SYNTHETIC_DEMO_CREATED,'+str(args.out)+',records=68')
if __name__=='__main__':main()
