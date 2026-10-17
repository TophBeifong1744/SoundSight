"""Analytic layout check, not acoustic/FPGA measurement."""
import math, json
from pathlib import Path
edge=40.0
h=edge*math.sqrt(2/3)
x=edge/math.sqrt(3)
xyz=[[x,0,-h/4],[-x/2,edge/2,-h/4],[-x/2,-edge/2,-h/4],[0,0,3*h/4]]
pairs=[(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]
g=[[0.0]*3 for _ in range(3)]
records=[]
for n,(a,b) in enumerate(pairs):
    v=[xyz[b][k]-xyz[a][k] for k in range(3)]
    length=math.sqrt(sum(t*t for t in v))
    assert abs(length-edge)<1e-10
    limit=8 if n in (1,4) else 6
    tau=length*48/343
    assert tau<limit
    records.append(dict(pair=f'{a}{b}',length_mm=length,max_lag_samples=tau,pl_search_limit=limit))
    for j in range(3):
        for k in range(3):g[j][k]+=v[j]*v[k]
for j in range(3):
    for k in range(3):assert abs(g[j][k]-(2*edge**2 if j==k else 0))<1e-9
report=dict(scope='ANALYTIC_GEOMETRY_ONLY',mic_xyz_mm=xyz,height_mm=h,pairs=records,normal_matrix_mm2=g,ideal_condition_2=1,band_top_hz=85*48000/1024,half_wavelength_frequency_hz=343/(2*edge/1000))
root=Path(__file__).resolve().parents[3]
out=root/'software/stm32/build/tetra3d/geometry.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
