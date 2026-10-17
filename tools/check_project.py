"""只读结构检查：文件/清单/旧路径/入口语法，不代替HDL编译或板测。"""
from pathlib import Path
import ast, json, re, sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    errors=[]; counts={}
    for rel in ['project/script/src_list.txt','document/build/ps-src-list.txt','simulation/script/src_list.txt']:
        lines=[s.strip() for s in (ROOT/rel).read_text('utf-8').splitlines() if s.strip() and not s.startswith('#')]
        if len(lines)!=len(set(lines)):errors.append('duplicate list entries: '+rel)
        for name in lines:
            p=(ROOT/name).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file():errors.append('missing/outside source: '+name)
        counts[rel]=len(lines)
    live=['project/rtl','project/script','project/bd','tools','simulation/models','software/ps','software/tests']
    scripts=[]
    for base in live:
        for p in (ROOT/base).rglob('*'):
            if not p.is_file() or p.suffix not in {'.py','.sv','.v','.tcl','.bat','.sh','.c','.h','.xdc'}:continue
            text=p.read_text('utf-8-sig')
            if any(ord(c)<32 and c not in '\n\r\t' for c in text):errors.append('control character: '+str(p.relative_to(ROOT)))
            # 历史原文/原始日志可能保留旧路径；只有活动代码不得使用旧工程。
            for word in ['Competition'+'_fpga','F:/AMD/p/'+'i17_live_loop','migration/'+'clean_pl_20261017','migration/'+'zynq_ps_20261017']:
                if word in text:errors.append('old project reference in active file: '+str(p.relative_to(ROOT)))
            if p.suffix=='.py':
                try:ast.parse(text,filename=str(p))
                except SyntaxError as e:errors.append(str(e))
                scripts.append(p)
    for rel in ['software/common/FROZEN_SSOT_ABI.md','software/common/fpga_stm32_abi_frozen.h',
                'software/common/s1/doa_solver.c','software/common/s1/doa_solver.h',
                'software/common/s1/test_doa_solver.c','hardware/reference/infineon/im73d122v01-datasheet-v1.00.pdf',
                'project/ip/create_fft_ip.tcl','project/ip/create_platform_clock.tcl']:
        if not (ROOT/rel).is_file():errors.append('missing necessary file: '+rel)
    for rel in ['project/script/vivado.tcl','tools/vivado_cli.tcl','project/bd/stm32.tcl','project/bd/ps.tcl']:
        text=(ROOT/rel).read_text('utf-8')
        if re.search(r'(?m)^\s*(launch_runs|synth_design|reset_run|program_hw_devices)\b',text):errors.append('unexpected physical operation: '+rel)
    result={'status':'PASS' if not errors else 'FAIL','scope':'static project structure only; no HDL/STA/board claim',
            'root':str(ROOT),'source_lists':counts,'python_syntax_checked':len(scripts),'errors':errors}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
