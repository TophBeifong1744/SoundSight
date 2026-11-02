"""Re-read the existing joint-run archive; no board access or new measurements."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parents[3]
archive=ROOT/'document/evidence/speaker-dual-axis-20261030/board-tests.zip'
handoff=ROOT/'document/posters/assets/reference/zh-content-handoff.md'
analysis_path=ROOT/'document/evidence/speaker-dual-axis-20261030/analysis.json'
analysis=json.loads(analysis_path.read_text(encoding='utf-8-sig'))
runs=[]
with ZipFile(archive) as z:
    for name in sorted(z.namelist()):
        if not (name.startswith('logs/speaker-3d-') and name.endswith('.json')):continue
        d=json.loads(z.read(name));st=d['stats'];cfg=d['settings']
        live=[r for r in d['speaker_worker']['results'] if isinstance(r.get('score'),(int,float))
              and math.isfinite(r['score']) and r['completed_at']<=d['at']]
        a=next(r for r in analysis['runs'] if r['log']==name)
        assert len(live)==a['completed_before_stop']==6
        runs.append(dict(source=name,seconds=d['elapsed_seconds'],frames=st['consumed'],
                         speaker_before_stop=len(live),commits=st['motion_commits'],
                         runtime_fault=st['fault_or'],drops=st['drops_last']-st['drops_first'],
                         gaps=st['sequence_gaps'],sample_rate=cfg['geometry']['sample_rate_hz'],
                         window_frames=cfg['window_frames'],min_valid=cfg['min_valid'],
                         min_level=cfg['min_level'],threshold=cfg['speaker']['threshold'],
                         ttl=cfg['speaker']['permit_seconds'],axes=cfg['axes'],target_id=cfg['target_id']))
assert len(runs)==2
for r in runs:
    assert (r['sample_rate'],r['window_frames'],r['min_valid'],r['min_level'],r['threshold'],r['ttl'],r['axes'])==(48000,3,1,12000,0.45,10.0,'both')
assert runs[0]['target_id']==runs[1]['target_id']
result={'content_handoff':handoff.relative_to(ROOT).as_posix(),'runs':runs,
        'sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in (handoff,archive,analysis_path)],
        'scope':'Two short existing sessions. Computations completed before STOP; not recognition correctness or mechanical arrival.'}
out=ROOT/'document/posters/assets/joint-run-facts.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'runs':len(runs),'speaker_before_stop':[r['speaker_before_stop'] for r in runs],'source_sha256':result['sources'][1]['sha256']}))
