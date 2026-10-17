"""SoundSight XSim入口：目录无关；只做仿真，不打开或构建物理工程。"""
from pathlib import Path
import argparse, json, os, re, shutil, subprocess, time
from tool_config import vivado_root, simulation_tools

ROOT = Path(__file__).resolve().parents[1]
CASES = ('pair','preprocess','capture','clean','dual','cdc','samplecdc','link','stm32',
         'pdm','frontstop','queue','spi','actuator','clock','axi','ps','pscdc','platform')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('case',choices=CASES,nargs='?',default='link')
    ap.add_argument('--gui',action='store_true',help='展开后打开波形GUI；不提前宣称测试通过')
    ap.add_argument("--check-tools", action="store_true", help="Resolve tools only; no simulation")
    args=ap.parse_args(); case=args.case
    toolroot=simulation_tools(vivado_root())
    tool=toolroot/'bin'
    if args.check_tools:
        import sys
        print(json.dumps({'python': sys.executable, 'xsim': str(tool/'xsim.bat'), 'eda_started': False}))
        return 0
    out=ROOT/'simulation/work'/(case+'_'+time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir(parents=True,exist_ok=False)
    source_dir=out/'sources';source_dir.mkdir()
    ps=case in ('axi','ps','pscdc')
    tb=ROOT/'simulation/tb'/('ps' if ps else 'stm32')
    rtl=ROOT/'project/rtl'
    ip=ROOT/'project/ip/reference'/('ps' if ps else 'stm32')
    sources=[ROOT/line.strip() for line in (ROOT/'simulation/script/src_list.txt').read_text('utf-8').splitlines()
             if line.strip() and not line.startswith('#')]
    if case=='pair':sources=[p for p in sources if p.name!='ifft25_official.sv']
    vhdl=[]
    official=case in ('clean','dual','stm32','pdm','frontstop','ps','pscdc')
    glbl=case in ('clean','dual','cdc','samplecdc','stm32','pdm','frontstop','clock','ps','pscdc','platform')
    libs=['xpm']
    if official:
        vhdl=[ip/n/'sim'/(n+'.vhd') for n in ('ss_fft29','ss_ifft25')];libs+=['xfft_v9_1_15']
    if case=='pscdc':
        sources+=sorted((ip/'platform_sim').glob('*.v'))
        libs+=['axi_clock_converter_v2_1_35','axi_infrastructure_v1_1_0']
    if case=='platform':
        sources=sorted((ip/'platform_sim').glob('*.v'))
        vhdl=sorted((ip/'platform_sim').glob('*.vhd'))
        libs+=['proc_sys_reset_v5_0_17','xpm_cdc_gen_v1_0_5']
    sources += [tb/('tb_'+case+'.sv')]
    if glbl:sources += [toolroot/'data/verilog/src/glbl.v'];libs+=['unisims_ver']
    inputs=sources+vhdl
    names=[p.name for p in inputs]
    if len(set(names))!=len(names):raise RuntimeError('Duplicate simulation source basename')
    for p in inputs:
        if not p.is_file():raise FileNotFoundError(p)
        shutil.copy2(p,source_dir/p.name)
    shutil.copy2(rtl/'hann-u18f17.mem',out/'hann-u18f17.mem')
    for p in list(tb.glob('*.mem'))+list(tb.glob('*.svh')):shutil.copy2(p,out/p.name)
    shutil.copy2(ROOT/'simulation/script/vsim.do',out/'run.tcl')
    top='tb_'+case;snapshot=case
    stages=[]
    if vhdl:stages.append(('vhdl','xvhdl',['--2008',*['sources/'+p.name for p in vhdl],'--log','vhdl.log']))
    stages += [('compile','xvlog',['--sv',*['sources/'+p.name for p in sources],'--log','compile.log']),
               ('elaborate','xelab',['work.'+top,*(['work.glbl'] if glbl else []),
                 *[a for lib in libs for a in ('-L',lib)],'--debug','typical','--relax','--mt','16',
                 '-s',snapshot,'--log','elaborate.log'])]
    if not args.gui:stages.append(('simulate','xsim',[snapshot,'--maxdeltaid','1000','--onerror','quit','--tclbatch','run.tcl','--log','simulate.log']))
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE'):env.pop(key,None)
    for key in ('APPDATA','LOCALAPPDATA','TEMP','TMP'):
        p=out/key;p.mkdir();env[key]=str(p)
    windir=Path(os.environ.get('SystemRoot','C:/Windows'))
    env['PATH']=os.pathsep.join(map(str,(tool,windir/'System32',windir)))
    record={'case':case,'scope':'RTL simulation only','inputs':[str(p) for p in inputs],'stages':[]}
    marker=case.upper()+'_PASS'
    def command_file(name,exe,argv):
        for value in [str(tool),*argv]:
            if any(c in value for c in '\n\r"%&|<>^'):raise ValueError('Unsupported batch path character')
        p=out/(name+'.bat')
        # PATH只修改当前子进程；Windows带空格路径使用独立的双引号参数。
        p.write_text('@echo off\ncall '+exe+' '+' '.join('"'+a+'"' for a in argv)+'\nexit /b %errorlevel%\n','utf-8')
        return [str(windir/'System32/cmd.exe'),'/d','/c',p.name]
    for stage,exe,argv in stages:
        start=time.monotonic(); timeout=False
        with (out/(stage+'.stdout.txt')).open('wb') as log:
            proc=subprocess.Popen(command_file(stage,exe,argv),cwd=out,env=env,
                                  stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:proc.wait(timeout=(3600 if case=='pdm' else 1200) if stage=='simulate' else 300)
            except subprocess.TimeoutExpired:
                timeout=True
                subprocess.run([str(windir/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=15)
                proc.wait(timeout=15)
        text=(out/(stage+'.stdout.txt')).read_text('utf-8',errors='replace')
        native=out/(stage+'.log')
        if native.exists():text+='\n'+native.read_text('utf-8',errors='replace')
        errors=[s for s in text.splitlines() if re.search(r'(?i)(^ERROR:|Fatal:|_FAIL)',s)]
        ok=not timeout and proc.returncode==0 and not errors and (stage!='simulate' or marker in text)
        record['stages'].append({'stage':stage,'exit':proc.returncode,'pass':ok,'timeout':timeout,'seconds':time.monotonic()-start,'errors':errors})
        (out/'RESULT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8')
        print(stage,ok,out,flush=True)
        if not ok:print(text[-6000:]);return 1
        if stage=='simulate':print('\n'.join(s for s in text.splitlines() if marker in s),flush=True)
    if args.gui:
        subprocess.Popen(command_file('gui','xsim',[snapshot,'--gui']),cwd=out,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        print('SIMULATION_GUI_OPENED: run the test in the GUI; result is NOT_RUN')
    else:print('SIMULATION_PASS',case,out)
    return 0

if __name__=='__main__':raise SystemExit(main())
