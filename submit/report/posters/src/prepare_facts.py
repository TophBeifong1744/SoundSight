"""Read existing evidence only; no hardware, builds or measurement acquisition."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'document/posters/assets'
OUT.mkdir(parents=True, exist_ok=True)
bench_path = ROOT/'document/evidence/ps-speaker-live-opt-20261025/board-opt1-bench.json'
bench = json.loads(bench_path.read_text(encoding='utf-8-sig'))
raw_path = ROOT/'document/evidence/ps-speaker-live-opt-20261025/board-opt1-bench-user.log'
raw_front = [json.loads(line.split('=',1)[1]) for line in raw_path.read_text(encoding='utf-8-sig').splitlines() if line.startswith('OPT_FRONT=')]
assert raw_front == [r for r in bench['rows'] if r['phase']=='frontend'], 'Structured rows differ from original console'
means = {}
for variant in ('baseline', 'opt1'):
    vals = [r['seconds'] for r in bench['rows'] if r['phase']=='frontend' and r['variant']==variant]
    assert len(vals)==2
    means[variant] = sum(vals)/len(vals)
reduction = 100*(1-means['opt1']/means['baseline'])
assert abs(reduction-bench['summary']['frontend']['reduction_percent']) < 1e-10
runs = []
archive = ROOT/'document/evidence/speaker-dual-axis-20261030/board-tests.zip'
with zipfile.ZipFile(archive) as z:
    for name in sorted(z.namelist()):
        if name.startswith('logs/speaker-3d-') and name.endswith('.json'):
            data = json.loads(z.read(name))
            s = data['stats']
            runs.append(dict(source=name, seconds=data['elapsed_seconds'], frames=s['consumed'],
                             commits=s['motion_commits'], runtime_fault=s['fault_or'],
                             drops=s['drops_last']-s['drops_first'], gaps=s['sequence_gaps'],
                             threshold=data['speaker_permission']['threshold'],
                             ttl=data['speaker_permission']['permit_seconds'], result=data['result']))
assert len(runs)==2
assert [r['frames'] for r in runs]==[3012,2552]
assert [r['commits'] for r in runs]==[117,94]
assert [r['drops'] for r in runs]==[0,1]
picture = ROOT/'project/reports/ps_3d/latest_result/user-export/imp_schematic.png'
shutil.copy2(picture, OUT/'fpga-implementation-original.png')
sources = [bench_path, archive, picture,
           ROOT/'document/evidence/ps-speaker-live-opt-20261025/board-opt1-bench-user.log',
           ROOT/'document/requirements/report-poster-master-guide.md',
           ROOT/'document/main-architecture.md', ROOT/'software/tetra3d/README.md']
manifest = [{'path':p.relative_to(ROOT).as_posix(), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
facts = {'date':'2026-10-31','frontend_mean_seconds':means,'frontend_reduction_percent':reduction,
         'input_seconds_each':10.912,'recording_count':2,'runs':runs,'sources':manifest,
         'scope':'Offline board benchmark and separate live sessions; no new measurements in this task.'}
(OUT/'facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'means':means,'reduction_percent':reduction,'runs':runs},ensure_ascii=False,indent=2))
