"""PC验证实际HWH寻址、程序终止/存储失败保帧行为；不导入PYNQ或接触硬件。"""
from pathlib import Path
import sys, tempfile, json, time
P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'software/ps'))
import run_capture as app

checks=0
fixture=P/'document/evidence/inherited/ps/bd_preparation/interface.hwh'
base,size=app.address_from_hwh(fixture)
assert (base,size)==(0x40000000,4096);checks+=1
# 改变HWH地址，软件必须使用新元数据，不能偷偷硬编码0x40000000。
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'moved.hwh'
    path.write_text(fixture.read_text('utf-8').replace('0x40000000','0x43C00000').replace('0x40000FFF','0x43C00FFF'),encoding='utf-8')
    assert app.address_from_hwh(path)==(0x43c00000,4096);checks+=1
    try:app.address_from_hwh(path,'missing')
    except ValueError:checks+=1
    else:raise AssertionError('missing peripheral admitted')

class Client:
    def __init__(self):self.events=[];self.queued=2;self.consumed=0
    def identify(self):self.events.append('id')
    def disable(self):self.events.append('disable')
    def start(self,bist):self.events.append(('start',bist))
    def read(self,a):return 2 if self.queued else 0
    def record_one(self,sink):
        sink({'n':self.consumed+1});self.consumed+=1;self.queued-=1

c=Client();records=[]
assert app.capture(c,records.append,'real',2)==2 and len(records)==2 and c.events[-1]=='disable';checks+=1
c=Client()
def failed(record):raise OSError('disk full')
try:app.capture(c,failed,'real',2)
except OSError:pass
else:raise AssertionError('storage failure swallowed')
assert c.consumed==0 and c.queued==2 and c.events[-1]=='disable';checks+=1
c=Client()
def interrupted(record):raise KeyboardInterrupt()
try:app.capture(c,interrupted,'real',2)
except KeyboardInterrupt:pass
else:raise AssertionError('interrupt swallowed')
assert c.consumed==0 and c.events[-1]=='disable';checks+=1
c=Client();records=[]
assert app.capture(c,records.append,'real',1,True)==2 and not any(isinstance(x,tuple) for x in c.events);checks+=1
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'records.jsonl'
    with path.open('a',encoding='utf-8') as handle:app.durable_sink(handle)({'frame':1})
    assert json.loads(path.read_text())=={'frame':1};checks+=1
out=P/'software/build'/('application_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(parents=True)
(out/'RESULT.json').write_text(json.dumps({'status':'PASS','checks':checks,'scope':'PC HWH and application only; no ARM/PYNQ/board run'},indent=2),encoding='utf-8')
print('APPLICATION_PASS checks='+str(checks));print(out)
