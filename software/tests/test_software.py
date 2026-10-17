"""PC验证：原S1全套测试、实际AXI仿真导出字→C求解，以及PS客户程序失败保帧。"""
from pathlib import Path
import sys, subprocess, os, time, json, importlib.util

P=Path(__file__).resolve().parents[2]
out=P/'software/build'/('software_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(parents=True)
gcc=Path(os.environ.get('SS_GCC',str(P/'tools'/'gcc-not-configured')))
if not gcc.is_file():
    config=dict(line.split('=',1) for line in (P/'simulation/script/setting.txt').read_text('utf-8').splitlines() if line and not line.startswith('#'))
    gcc=Path(config['GCC_ROOT'])/'bin/gcc.exe'
spec=importlib.util.spec_from_file_location('ps_client',P/'software/ps/ps_client.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
common=[str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1','-I'+str(P/'software/common'),'-I'+str(P/'software/common/s1')]
def run(name,args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    (out/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0,(name,p.stderr);return p.stdout
run('compile_s1',common+[str(P/'software/common/s1/doa_solver.c'),str(P/'software/common/s1/test_doa_solver.c'),'-lm','-o',str(out/'s1.exe')])
text=run('s1',[str(out/'s1.exe')]);assert '4705' in text and 'failures=0' in text,text[-600:]
library=out/'solver.dll'
run('compile_bridge',common+['-shared',str(P/'software/ps/ss_solver_bridge.c'),str(P/'software/common/s1/doa_solver.c'),'-lm','-o',str(library)])
solver=m.Solver(library)
frames=[];results=[];checks=0
candidates=list((P/'simulation/work').glob('ps_*/ps_bist_pass.txt'))+list((P/'document/evidence/inherited/ps').glob('ps_*/ps_bist_pass.txt'))
if not candidates:raise RuntimeError('需要实际AXI仿真的双BIST输出；先运行test/run.py ps')
evidence=max(candidates,key=lambda p:p.parent.name).parent
for which in ('reject','pass'):
    words=[int(v,16) for v in (evidence/('ps_bist_'+which+'.txt')).read_text().split()]
    frame=dict(sequence=words[0],status=words[1],words=words[2:]);result=solver.solve(frame)
    expected=(46831,-171729,3,0) if which=='reject' else (749295,0,0,1)
    assert tuple(result[k] for k in ('ux_q20','uy_q20','reason','direction_valid'))==expected
    assert result['servo_cmd_valid']==0 and result['bridge_status']==0;checks+=2
    frames.append(frame);results.append(result)
bad=dict(frames[1],words=frames[1]['words'][:]);bad['words'][0]^=0x100
assert solver.solve(bad)['bridge_status']==-4;checks+=1
assert solver.solve(frames[1],[90*256,1,-90*256,90*256,-1,180,180])['bridge_status']==-5;checks+=1
class Device:
    def __init__(self,frame):self.frame=frame;self.selected=0;self.consumes=0;self.stops=0;self.locked=False
    def read(self,a):
        if a==m.STATUS:return self.frame['status']&~1|int(self.locked)|2
        if a==m.SEQ:return self.frame['sequence']
        if a in (m.FEATURE,m.PEAK,m.LEFT,m.RIGHT,m.SECOND):return self.frame['words'][self.selected*5+(m.FEATURE,m.PEAK,m.LEFT,m.RIGHT,m.SECOND).index(a)]
        if a==m.MAGIC:return 0x5a5a2026
        if a==m.ABI:return 0x10000
        return 0
    def write(self,a,v):
        if a==m.SELECT:self.selected=v
        elif a==m.SNAP and v==1:self.locked=True
        elif a==m.SNAP and v==4:self.consumes+=1;self.locked=False
        elif a==m.ACT and v==2:self.stops+=1
dev=Device(frames[1]);client=m.Client(dev,solver);client.identify();saved=[]
client.record_one(saved.append);assert dev.consumes==1 and len(saved)==1;checks+=1
dev=Device(frames[1]);client=m.Client(dev,solver)
def fail_sink(record):raise OSError('injected storage full')
try:client.record_one(fail_sink)
except OSError:pass
else:raise AssertionError('write failure lost')
assert dev.consumes==0 and dev.locked and dev.stops==1;checks+=1
try:client.command(frames[1],results[1])
except RuntimeError:pass
else:raise AssertionError('BIST motion admitted')
assert dev.consumes==0;checks+=1
(out/'RESULT.json').write_text(json.dumps(dict(status='PASS',s1_assertions=4705,bridge_and_client_checks=checks,axi_fixture=str(evidence),results=results),ensure_ascii=False,indent=2),encoding='utf-8')
print('SOFTWARE_PASS original_s1=4705 bridge_and_client_checks='+str(checks));print(out)
