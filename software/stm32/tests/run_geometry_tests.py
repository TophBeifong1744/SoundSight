"""D2 PC geometry/configuration checks and optional AC5 objects; no hardware."""
from pathlib import Path
import argparse
import copy
import json
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from tool_config import gcc_executable
OUT=ROOT/'software/stm32/build/geometry-d2'
OUT.mkdir(parents=True,exist_ok=True)

def run(name,cmd,expected=0):
    cmd=list(map(str,cmd));p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    log='COMMAND: '+subprocess.list2cmdline(cmd)+'\n'+p.stdout+p.stderr+f'\nEXIT_CODE: {p.returncode}\n'
    (OUT/(name+'.log')).write_text(log,encoding='utf-8')
    if p.returncode!=expected:
        first=OUT/(name+'-first-failure.log')
        if not first.exists():first.write_text(log,encoding='utf-8')
        raise RuntimeError(name+' unexpected exit '+str(p.returncode))
    return p.stdout+p.stderr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--armcc');args=ap.parse_args()
    inc=['-Isoftware/common','-Isoftware/common/s1','-Isoftware/common/s1_3d','-Isoftware/stm32/include']
    base=[gcc_executable(),'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-D__USE_MINGW_ANSI_STDIO=1','-DSS_DOA_PROFILE=1',*inc]
    sources=['software/common/s1/doa_solver.c',*[f'software/common/s1_3d/{u}.c' for u in ('doa_solver_3d','doa_dispatch','doa_geometry')],*[f'software/stm32/src/{u}.c' for u in ('fpga_link','ss_runtime','ss_motion','ss_app','ss_spatial')]]
    run('compile-geometry',base+sources+['software/stm32/tests/test_geometry.c','-lm','-o',OUT/'test.exe'])
    result=run('geometry',[OUT/'test.exe']);print(result,end='')
    if 'D2_RESULT,PASS' not in result or 'failures=0' not in result:raise RuntimeError('Missing D2 PASS')
    template=json.loads((ROOT/'software/stm32/config/tetra40-nominal.json').read_text(encoding='utf-8'))
    importer=ROOT/'software/stm32/tools/prepare_geometry.py'
    count=0
    # Ephemeral importer fixtures are removed by TemporaryDirectory, including
    # generated headers; selected checked-in example remains the only input.
    with tempfile.TemporaryDirectory(prefix='import-tests-',dir=OUT) as folder:
        tmp=Path(folder)
        def case(name,obj,success=False,raw=None):
            nonlocal count
            source=tmp/(name+'.json');out=tmp/(name+'.h')
            source.write_text(json.dumps(obj) if raw is None else raw,encoding='utf-8')
            log=run('import-'+name,[sys.executable,importer,'--input',source,'--out',out],0 if success else 1)
            assert out.exists()==success,(name,log)
            count+=1
            return source,out
        src,h=case('nominal',template,True)
        original=h.read_bytes()
        run('import-no-overwrite',[sys.executable,importer,'--input',src,'--out',h],1)
        assert h.read_bytes()==original
        count+=1
        # Compile the selected-header path and exercise app_init without buses.
        smoke=tmp/'selected.c'
        smoke.write_text('#include "ss_app.h"\n#include <stdio.h>\n'
            'static ss_bus_status_t tx(void *p,const uint8_t a[5],uint8_t b[5],uint32_t t){(void)p;(void)a;(void)b;(void)t;return SS_BUS_ERROR;}\n'
            'static uint32_t now(void *p){(void)p;return 0;}\n'
            'int main(void){ss_app_t a;ss_bus_t b={0,tx,now,10,100};int s=ss_app_init(&a,&b);'
            'printf("D2_SELECTED_INIT,status=%d,revision=%lu,valid=%u\\n",s,(unsigned long)a.geometry.revision,(unsigned)a.geometry_report.valid);'
            'return s!=SS_OK || !a.geometry_report.valid || a.geometry.revision!=1U;}\n',encoding='ascii')
        selected=['-I'+str(tmp),'-DSS_GEOMETRY_HEADER="nominal.h"']
        run('compile-selected',base+selected+sources+[smoke,'-lm','-o',tmp/'selected.exe'])
        print(run('selected',[tmp/'selected.exe']),end='')
        bad=copy.deepcopy(template);bad['microphones'][0]['channel']=1;case('duplicate-channel',bad)
        bad=copy.deepcopy(template);bad['microphones'][0]['channel']=True;case('boolean-channel',bad)
        bad=copy.deepcopy(template);bad['schema']=2;case('schema',bad)
        bad=copy.deepcopy(template);bad['revision']=0;case('revision',bad)
        bad=copy.deepcopy(template);bad['provenance']='MEASURED';case('measurement-no-bound',bad)
        bad['position_error_mm']=0.5;bad['revision']=2;case('declared-measured',bad,True)
        bad['position_error_mm']=2;case('measurement-too-uncertain',bad)
        bad=copy.deepcopy(template);bad['microphones'][3]['xyz_mm'][2]=-8.16496580927726;case('coplanar',bad)
        bad=copy.deepcopy(template);bad['sample_rate_hz']=44100;case('rate',bad)
        bad=copy.deepcopy(template);bad['source_id']='x'*64;case('long-source',bad)
        bad=copy.deepcopy(template);bad['source_id']='x\ny';case('newline-source',bad)
        bad=copy.deepcopy(template);bad['source_id']='quote"slash\\??/';case('escaped-source',bad,True)
        bad=copy.deepcopy(template);bad['other']=1;case('unknown-key',bad)
        case('duplicate-key',None,raw='{"schema":1,"schema":1}')
        bad=copy.deepcopy(template);bad['sample_rate_hz']=float('nan');case('nan',bad)
        bad['sample_rate_hz']=float('inf');case('inf',bad)
        if args.armcc:
            for unit in ('software/common/s1_3d/doa_geometry.c','software/stm32/src/ss_app.c'):
                extra=selected if unit.endswith('ss_app.c') else []
                run('armcc-'+Path(unit).stem,[args.armcc,'--cpu=Cortex-M4.fp.sp','--c99','--library_type=microlib','-O2','--strict','--diag_error=warning','-DSS_DOA_PROFILE=1',*inc,*extra,'-c',unit,'-o',OUT/(Path(unit).stem+'.o')])
            print('D2_ARMCC,PASS,geometry_and_selected_app_objects,NOT_FULL_3D_LINK')
    print(f'D2_IMPORT,PASS,cases={count},strict_JSON,C_validator,no_overwrite,selected_app_init')
if __name__=='__main__':main()
