"""D3 real-CLI integration tests; numerical acceptance uses forward truth.
No hardware, full firmware linking or physical-time claims.
"""
from pathlib import Path
import copy
import csv
import json
import os
import subprocess
import sys
import tempfile
import uuid
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'software/stm32/tools'))
from generate_replay_demo import demo,frame,metadata,write_jsonl
from replay_3d import angular_error
OUT=ROOT/'software/stm32/build/replay-d3'
OUT.mkdir(parents=True,exist_ok=True)
SCRIPT=ROOT/'software/stm32/tools/replay_3d.py'
GEOM=ROOT/'software/stm32/config/tetra40-nominal.json'
checks=0


def check(condition,message):
    global checks
    checks+=1
    if not condition:raise AssertionError(message)


def call(name,src,dest,geometry=GEOM,expected=0,env=None):
    command=[sys.executable,str(SCRIPT),'--input',str(src),'--geometry',str(geometry),'--out',str(dest)]
    p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,env=env)
    log='COMMAND: '+subprocess.list2cmdline(command)+'\n'+p.stdout+p.stderr+f'\nEXIT_CODE: {p.returncode}\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if p.returncode!=expected:
        failure=OUT/(name+'-first-failure.log')
        if not failure.exists():failure.write_text(log,encoding='utf-8')
    check(p.returncode==expected,name+': '+log)
    if expected!=0:check(not dest.exists(),name+' published output on failure')
    return log


def load(dest):
    summary=json.loads((dest/'summary.json').read_text(encoding='utf-8'))
    with (dest/'frames.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    with (dest/'pairs.csv').open(encoding='utf-8',newline='') as f:pairs=list(csv.DictReader(f))
    return summary,rows,pairs


def run():
    with tempfile.TemporaryDirectory(prefix='tests-',dir=OUT) as d:
        temp=Path(d);src=temp/'demo.jsonl';data=demo();write_jsonl(src,data)
        dest=temp/'result';call('demo',src,dest)
        summary,rows,pairs=load(dest)
        check(len(rows)==68 and len(pairs)==408,'all frame/pair rows retained')
        check(summary['disposition_counts']==dict(VALID=57,ALGORITHM_REJECT=6,INPUT_REJECT=3,SEQUENCE_REJECT=2),'classification counts')
        check(summary['algorithm_rejection_counts']==dict(PAIRS=1,NORM=1,RESIDUAL=1,CANCELLED=1,SOURCE=1,LEGACY_BIST=1),'algorithm reason separation')
        for i,row in enumerate(rows[:42]):
            check(row['direction_valid']=='1','ideal direction valid')
            check(float(row['angular_error_deg'])<0.04,'ideal spherical error')
            check(row['geometry_revision']=='1' and row['geometry_source_id']=='tetra40-nominal-v1','geometry annotation')
            if i>=40:
                check(row['azimuth_deg']=='' and row['azimuth_error_deg']=='' and row['azimuth_valid']=='0','pole no invented azimuth')
            else:check(abs(float(row['azimuth_error_deg']))<0.04,'wrapped azimuth error')
        for i in range(42):
            for j in range(6):
                raw=data[i+1]['pairs'][j];actual=pairs[i*6+j]
                expected_delta=(raw['r_plus']-raw['r_minus'])//4
                check(int(actual['tau_q12'])==raw['lag']*4096+expected_delta,'quantized feature/sign bridge')
                check(int(actual['margin_q15'])==29491 and actual['qualified']=='1','pair result precision bridge')
        for row in rows[42:54]:
            check(row['direction_valid']=='1' and float(row['angular_error_deg'])<2,'bounded perturbed TDOA')
        check(rows[54]['valid_pair_count']=='5','one missing pair remains solvable')
        for row in rows[55:64]+rows[65:67]:
            check(row['direction_valid']=='0' and row['azimuth_deg']=='' and row['elevation_deg']=='','no stale direction on rejection')
            check(row['angular_error_deg']=='','rejections excluded from accuracy')
        check(rows[64]['direction_valid']=='1' and rows[64]['angular_error_deg']=='','valid no-reference error unavailable')
        check(rows[65]['sequence']=='DUPLICATE' and rows[66]['sequence']=='BACKWARD_OR_AMBIGUOUS','sequence reasons')
        check(rows[67]['sequence']=='GAP' and rows[67]['frame_id_gap']=='2','gap from last forward ID')
        check(summary['observed_frame_id_gap_total']==2,'gap total')
        check(summary['accuracy']['angular']['count']==56 and summary['accuracy']['azimuth_absolute']['count']==54,'conditional error denominator')
        check(summary['reference_records']==66,'reference records include rejected reference inputs')
        check(summary['api_status_counts']==dict(OK=63,INPUT_RANGE=1,INPUT_FLAGS=1,INCOMPLETE_FRAME=1),'API status counts')
        check(all(p['tau_q12']=='' and p['pair_reason']=='NOT_EVALUATED' for p in pairs[65*6:67*6]),'sequence-rejected pairs uncomputed')
        check(pairs[55*6]['pair_reason']=='MASK','pair mask rejection preserved')
        check((dest/'input.jsonl').read_bytes()==src.read_bytes(),'input copy exact')
        # Artifact retained outside temporary test directory for the report.
        report=OUT/'example'
        if report.exists():
            # Do not destroy earlier runs; select a new directory on rerun.
            report=OUT/('example-'+uuid.uuid4().hex[:8])
        import shutil
        shutil.copytree(dest,report)
        (OUT/'latest-example.txt').write_text(str(report),encoding='utf-8')
        before={p.name:p.read_bytes() for p in dest.iterdir()}
        p=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--geometry',str(GEOM),'--out',str(dest)],capture_output=True,text=True,cwd=ROOT)
        check(p.returncode==2 and before=={p.name:p.read_bytes() for p in dest.iterdir()},'no output overwrite')
        # uint32 wrap accepted; half-range/backwards/duplicate rejected without
        # changing chronology. A new session must be a new input, not ID guessing.
        records=[metadata(),frame(0xffffffff,45,30),frame(0,-45,-30),frame(1,0,0),frame(0x80000001,0,0),frame(1,0,0),frame(2,0,0)]
        wrap=temp/'wrap.jsonl';write_jsonl(wrap,records);call('wrap',wrap,temp/'wrap-out')
        s,w,_=load(temp/'wrap-out')
        check([r['sequence'] for r in w]==['FIRST','NEXT','NEXT','BACKWARD_OR_AMBIGUOUS','DUPLICATE','NEXT'],'wrap and half-range')
        check(s['observed_frame_id_gap_total']==0,'no wrap gap')
        # A recorded-feature declaration without any reference must never
        # manufacture zero error or measured calibration.
        recorded=[metadata(),frame(1,45,30)];recorded[0]['source_kind']='RECORDED_FEATURES';recorded[1]['reference']=None
        nr=temp/'no-reference.jsonl';write_jsonl(nr,recorded);call('no-reference',nr,temp/'nr-out')
        s,n,_=load(temp/'nr-out')
        check(s['accuracy']['angular']==dict(count=0,mean_deg=None,rms_deg=None,max_deg=None),'unavailable accuracy')
        check(s['geometry_declaration']['provenance']=='NOMINAL','no measured promotion')
        # All rejected is a completed diagnostic run, not a successful direction.
        rejected=[metadata(),frame(1,0,0)];rejected[1]['flags']=0
        reject_src=temp/'all-rejected.jsonl';write_jsonl(reject_src,rejected)
        call('all-rejected',reject_src,temp/'all-rejected-out')
        s,_,_=load(temp/'all-rejected-out')
        check(s['disposition_counts']=={'INPUT_REJECT':1} and s['accuracy']['angular']['count']==0,'completed is not direction pass')
        # D2 permits printable ASCII source IDs; CSV must not activate formulas.
        geo=json.loads(GEOM.read_text(encoding='utf-8'));geo['source_id']='=1+1'
        gp=temp/'formula-geometry.json';gp.write_text(json.dumps(geo),encoding='utf-8')
        record=[metadata(),frame(1,0,0)];record[0]['geometry_source_id']='=1+1'
        fp=temp/'formula-source.jsonl';write_jsonl(fp,record)
        call('csv-formula',fp,temp/'formula-out',geometry=gp)
        s,f,_=load(temp/'formula-out')
        check(f[0]['geometry_source_id']=="'=1+1" and s['geometry_declaration']['source_id']=='=1+1','CSV inert; JSON identity exact')
        # Known metric cases independently constrain conventions, not just
        # checking that our report recomputes its own answer.
        check(abs(angular_error(179,0,-179,0)-2)<1e-10,'dateline shortest arc')
        check(abs(angular_error(0,0,90,0)-90)<1e-10,'orthogonal')
        check(abs(angular_error(120,90,-70,-90)-180)<1e-10,'opposite poles')
        check(angular_error(120,90,-70,90)<1e-10,'same pole independent azimuth')
        negatives=0
        def bad(name,items=None,raw=None,geom=GEOM):
            nonlocal negatives
            path=temp/(name+'.jsonl')
            if raw is not None:path.write_text(raw,encoding='utf-8')
            else:write_jsonl(path,items)
            call(name,path,temp/(name+'-out'),geom,2);negatives+=1
        for field,value in [('frame_id',True),('frame_id',0x100000000),('flags',-1)]:
            b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1][field]=value;bad('bad-'+field+'-'+str(value),b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['pairs'][0]['mask_count']=256;bad('mask-storage-overflow',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['pairs'][0]['peak']=0x80000000;bad('signed-storage-overflow',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['pairs'].pop();bad('missing-pair',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[0]['pair_order'][0]='10';bad('wrong-pair-order',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[0]['geometry_revision']=2;bad('wrong-revision',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[0]['geometry_source_id']='other';bad('wrong-geometry-source',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['extra']=1;bad('unknown-field',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['reference']['kind']='ALGORITHM';bad('algorithm-reference',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[0]['source_kind']='RECORDED_FEATURES';bad('synthetic-ref-on-recorded',b)
        b=copy.deepcopy([metadata(),frame(1,0,0)]);b[1]['reference']['elevation_deg']=91;bad('bad-elevation',b)
        bad('duplicate-json-key',raw=json.dumps(metadata())+'\n{"frame_id":1,"frame_id":1}\n')
        bad('nan',raw=json.dumps(metadata())+'\n'+json.dumps(frame(1,0,0)).replace('"azimuth_deg": 0','"azimuth_deg": NaN')+'\n')
        bad('empty',raw='')
        bad('blank-frame',raw=json.dumps(metadata())+'\n\n')
        bad('truncated',raw=json.dumps(metadata())+'\n{"frame_id":1\n')
        geo=json.loads(GEOM.read_text(encoding='utf-8'))
        for mic in geo['microphones']:mic['xyz_mm'][2]=0
        gp=temp/'coplanar.json';gp.write_text(json.dumps(geo),encoding='utf-8')
        bad('bad-geometry',[metadata(),frame(1,0,0)],geom=gp)
        env=os.environ.copy();env['SS_GCC']=str(temp/'missing-gcc.exe')
        call('compiler-failure',src,temp/'compiler-failure-out',expected=2,env=env)
        negatives+=1
        print('D3_NEGATIVES,PASS,cases='+str(negatives))
        print('D3_NUMERIC,ideal_max_deg='+str(max(float(r['angular_error_deg']) for r in rows[:42]))+',noisy_max_deg='+str(max(float(r['angular_error_deg']) for r in rows[42:54])))
        print('D3_EXAMPLE,'+str(report))
    print(f'D3_RESULT,PASS,checks={checks},failures=0')


if __name__=='__main__':
    try:run()
    except Exception as e:
        first=OUT/'test-first-failure.txt'
        if not first.exists():first.write_text(repr(e),encoding='utf-8')
        raise
