"""Negative control: only an isolated simulation snapshot is deliberately broken."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('crossing',choices=('enable','drain'))
args=ap.parse_args()
src=ROOT/'simulation/work/audioctrl_20261024_115736'
out=ROOT/('simulation/work/audioctrl_canary_'+args.crossing+'_20261024')
out.mkdir(exist_ok=True)

for p in (src/'sources').iterdir():
 q=out/'sources'/p.name
 q.parent.mkdir(exist_ok=True)
 if not q.exists():shutil.copy2(p,q)
for pattern in ('*.bat','*.mem','*.svh','run.tcl'):
 for p in src.glob(pattern):shutil.copy2(p,out/p.name)
p=out/'sources/ss_dual_compute.sv'
s=(src/'sources/ss_dual_compute.sv').read_text(encoding='utf-8');old='.SRC_INPUT_REG(1),.INIT_SYNC_FF(1)) '+args.crossing+'_sync'
assert old in s;p.write_text(s.replace(old,old.replace('SRC_INPUT_REG(1)','SRC_INPUT_REG(0)'),1),encoding='utf-8')
env=os.environ.copy()
for key in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE'):env.pop(key,None)
for key in ('APPDATA','LOCALAPPDATA','TEMP','TMP'):
 p=out/key;p.mkdir(exist_ok=True);env[key]=str(p)
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import simulation_tools,vivado_root
windir=Path(os.environ.get('SystemRoot','C:/Windows'))
env['PATH']=os.pathsep.join(map(str,(simulation_tools(vivado_root())/'bin',windir/'System32',windir)))
record={}
for name in ('vhdl','compile','elaborate','simulate'):
 p=subprocess.run([str(windir/'System32/cmd.exe'),'/d','/c',name+'.bat'],cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
 (out/(name+'.stdout.txt')).write_bytes(p.stdout)
 text=p.stdout.decode(errors='replace')
 record[name]={'exit':p.returncode}
 if name!='simulate':assert p.returncode==0 and 'ERROR:' not in text,text[-2000:]
 else:
  assert ('AUDIOCTRL_FAIL '+('source' if args.crossing=='enable' else 'drain')+' glitch crossed') in text and 'AUDIOCTRL_PASS' not in text,text[-2000:]
  record['result']='EXPECTED_FAILURE_DETECTED';print(text[-1200:])
(out/'RESULT.json').write_text(json.dumps(record,indent=2))
print('CANARY_PASS',args.crossing,'source-register removal detected')
