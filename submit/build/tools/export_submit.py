"""Export actual submission files; never run EDA or access hardware."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import argparse
import hashlib
import json
import os
import posixpath
import re
import subprocess
from submit_scope import include

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('src', 'sim', 'build', 'board', 'data', 'skill', 'report')


def destination(name):
    if not include(name):
        return None
    if name == 'research/competition-skills/README.md':
        return 'skill/package-overview.md'
    if name.startswith('submit/') or name in {'README.md', 'AGENTS.md', 'data/README.md'}:
        return None
    if name.startswith('.') or name.split('/')[0] in {'src', 'sim', 'build', 'board', 'skill'}:
        return None
    if '/.gitattributes' in name:
        return None
    if name == 'LICENSE': return 'report/licenses/license.txt'
    if name == 'THIRD_PARTY.md': return 'report/licenses/third-party.md'
    if name == 'release/output/soundsight_screen_product_p1.zip':
        return 'board/artifacts/soundsight_screen_product_p1.zip'
    if name == 'tools.local.env.example': return 'build/config/tools.local.env.example'
    if name in {'soundsight.sh', 'soundsight-3d.sh', 'soundsight-screen.sh', 'soundsight-screen-i2c.sh', 'soundsight-panel.sh', 'soundsight-product.sh'}: return 'board/scripts/'+name
    if name in {'document/screen-readme.md','document/screen-control.md'}:
        return 'board/instructions/'+name.rsplit('/',1)[1]
    pairs = [
        ('handoff/', 'build/handoff/'),
        ('report/', 'build/reports/current/'),
        ('software/tetra3d/tests/', 'sim/tetra3d/'),
        ('release/output/screen_s2/', 'board/artifacts/screen_s2/'),
        ('project/rtl/', 'src/rtl/'),
        ('project/reports/', 'build/reports/'),
        ('project/', 'build/vivado/'),
        ('software/tests/', 'sim/software/'),
        ('software/', 'src/software/'),
        ('simulation/', 'sim/rtl/'),
        ('tools/', 'build/tools/'),
        ('hardware/', 'board/hardware/'),
        ('document/evidence/', 'data/evidence/'),
        ('document/', 'report/'),
        ('research/competition-skills/', 'skill/'),
        ('release/', 'build/release/'),
        ('data/', 'data/'),
    ]
    for prefix, target in pairs:
        if name.startswith(prefix): return (target+name[len(prefix):]).lower()
    raise ValueError('Unclassified tracked file: '+name)


PREPARE = r'''"""Prepare an independent working copy from this submit folder only."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def safe(base, relative):
    if not isinstance(relative, str):
        raise ValueError('Relative path must be text')
    p = PurePosixPath(relative)
    if p.as_posix() != relative:
        raise ValueError('Noncanonical relative path: '+relative)
    if p.is_absolute() or not p.parts or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe relative path: '+relative)
    target = base.joinpath(*p.parts).resolve()
    try: target.relative_to(base.resolve())
    except ValueError: raise ValueError('Path escapes its root: '+relative)
    return target

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True, help='New empty workspace, outside submit')
    args = ap.parse_args()
    output = args.output.resolve()
    try: output.relative_to(ROOT)
    except ValueError: pass
    else: raise ValueError('Workspace must be outside submit')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Refusing to overwrite existing work')
    manifest = json.loads((ROOT/'build/file-map.json').read_text('utf-8'))
    if manifest.get('schema') != 2:
        raise ValueError('Source-preserving submission manifest required')
    inputs=[]; seen=set()
    for entry in manifest['files']:
        display = safe(ROOT, entry['submit_path'])
        source = safe(ROOT, entry['restore_path'])
        target = safe(output, entry['source_path'])
        if str(target).casefold() in seen: raise ValueError('Duplicate output path')
        seen.add(str(target).casefold())
        if hashlib.sha256(display.read_bytes()).hexdigest() != entry['submit_sha256']:
            raise ValueError('Submission file differs from manifest: '+entry['submit_path'])
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry['restore_sha256'] or digest != entry['source_sha256']:
            raise ValueError('Original source differs from manifest: '+entry['restore_path'])
        inputs.append((target,data,entry['mode']))
    output.mkdir(parents=True,exist_ok=True)
    for target,data,mode in inputs:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        if mode == '100755': target.chmod(0o755)
    (output/'README.md').write_text('Generated working copy. Read the original submit/README.md for reproduction steps.\n',encoding='utf-8')
    print('WORKSPACE_READY files='+str(len(inputs))+' EDA_STARTED=0 HARDWARE_ACCESSED=0')
    print(str(output))

if __name__ == '__main__': main()
'''

README = '# SoundSight 最终提交材料 — 2026-11-04\n\n最终范围：RGB触屏、40 mm正四面体四麦三维定位、声纹验证、双轴指向。组合为S2硬件、P1产品面板、CF1A前端、CP1/VF1声纹与score_ttl_v2许可。水平J3-2/M15、垂直J3-3/J14，默认关轴。\n\n七类目录包含实际文件。当前软件含采集调度、方向窗口、旋转/触摸、确认删除用户和快速启动更新；公开[产品更新包](board/artifacts/soundsight_screen_product_p1.zip)可用于已有匹配板端。私人模型、模板和用户录音不在公共提交内。\n\n[设计报告](report/design-report.docx)（第9章为复现步骤）、[测量/日志原件](data/evidence/final-board-20261103/readme.md)、[使用说明](report/pynq-final-runtime.md)、[触屏操作](report/screen-product.md)、[整理范围](report/submit-final-scope.md)。正式设计报告位于report/design-report.docx；requirements保留赛事模板与规则。\n\n## 独立恢复与检查\n\n在submit目录运行，输出须为空且在本目录之外：\n\n```text\npython -B build/prepare_workspace.py --output ../soundsight_work\n```\n\n进入soundsight_work后：\n\n```text\npython -B tools/prepare_screen_s2.py --output ../s2_work\npython -B tools/check_current_software.py --output ../software_check\npython -B -m unittest discover -s software/tests -p test_current_runtime.py\n```\n\n恢复不依赖Git或原开发目录。S2配方49项，使用Vivado2025.2、xc7z020clg400-2；输出路径ASCII且最多78字节。准备脚本不运行EDA。软件检查需要Python、NumPy/Pillow及PATH中的gcc，使用合成输入进行主机逻辑回归。\n\n匹配bit/HWH/XSA在board/artifacts/screen_s2；原生工程导出和实现报告在build/handoff、build/reports。完整私人运行包依赖既有匹配PYNQ系统，公共提交不是SD镜像。现场测试、用户实测表、程序日志与主机验证分别记录。\n'

EXTRAS = {'src/README.md': '# 当前实现\n\nrtl仅收录S2配方依赖。software包含当前PS、屏幕、三维和共享C算法。\ncommon/s1及冻结头仍被当前求解器调用；文件中历史STM32命名不代表另带STM32固件。\n声纹核心的pipeline_bench、short_bench、stream_bench也是生产依赖，不能按名字删除。\n', 'sim/README.md': '# 当前验证源码\n\n软件与tetra3d测试可在恢复后的工作目录执行，见[根说明](../README.md)。\nrtl保留PS侧测试台和模型，属于模块验证资产；旧STM32整链测试和旧仿真启动配方不再交付。\n本批仅运行公开输入的软件回归，未重新执行RTL仿真。\n', 'build/README.md': '# 当前硬件与复现\n\nvivado/screen_s2及../src/rtl组成S2的49项配方；handoff/screen_s2是实际导出。\nreports/current为本次收到的工具报告，reports/ps_3d/screen_s2为S2原有审查报告。\nprepare_workspace.py从本提交独立恢复，tools/prepare_screen_s2.py只准备新工程目录。\n', 'board/README.md': '# 板端材料\n\nartifacts/screen_s2提供匹配bit/HWH/XSA；scripts为当前启动入口，instructions为屏幕操作。\n旧增量安装ZIP、旧位流及旧平台交付包已移除。\n实际安装说明见[完整运行包](../report/pynq-final-runtime.md)，公共源码不包含私人模型与用户配置。\n', 'data/README.md': '# 实验依据\n\nevidence保留当前屏幕、声纹、三维及技能交付的原始验证记录。当前软件测试自行生成合成输入。\n基线、被拒绝的优化数值与失败记录是对比依据，并不表示这些候选进入最终产品。\n[声纹指标](evidence/speaker-report-materials/metrics.csv)的不同计时边界不可相加。\n旧STM32迁移、六麦研究、海报草稿与历史发布包不在当前提交范围。\n', 'skill/README.md': '# 比赛技能包\n\nfpga-module-verification及pynq-overlay-dma-validation为实际技能源码、示例和许可证。\n恢复工作目录后可执行：\n\n```text\npython -B release/check_competition_skills.py --skills-root research/competition-skills --output ../skill_check\n```\n\n不提供--vivado-bin时只做离线检查。技能验收证据不等同当前整机验收。\n', 'report/README.md': '# 设计报告与支撑材料\n\n[设计报告](design-report.docx)介绍方案、实现、实测结果与AI协作，第9章给出硬件接线、环境准备、工程重建、软件安装、运行及结果比对步骤。\n\n配套材料：[实现报告](../build/reports/current/screen_s2_20261103/readme.md)、[实测数据](../data/evidence/final-board-20261103/readme.md)、[运行说明](pynq-final-runtime.md)、[触屏操作](screen-product.md)。requirements保存赛事模板与规则。\n', 'report/design-report.md': '# 当前系统与结果入口\n\n正式正文见[设计报告](design-report.docx)，复现步骤见其第9章。以下为配套工程与结果索引。PL承担同步四麦采集、特征/PCM导出、双轴PWM及保护；PS承担CF1A/C三维求解、筛选、CP1/VF1声纹和P1触屏管理。纯声音跟随、声纹许可跟随、手动标定分别保留。\n\n结果以[共同事实](handoff/report-update-20261103/facts.md)和[实测归档](../data/evidence/final-board-20261103/readme.md)为准：75次测角、60次声纹判定、机械计时、120分钟人工采样，以及975.374秒原生联合日志分别引用。原表文字更正保存在来源说明，数据图按原始行复算。\n\nS2同候选实现WNS+0.203ns、WHS+0.036ns；描述报告覆盖的已约束路径，不推广为全部接口签核。优化使用声纹和CF1A的同输入原件，各阶段计时不相加。实际技能源码和验证在skill、data；协作叙述以本轮用户TXT为准。\n', 'report/authoring-inputs.md': '# 三份产物独立完善\n\n共读[统一事实](handoff/report-update-20261103/facts.md)，分别使用[技术报告提示词](handoff/report-update-20261103/technical-prompt.md)、[设计报告提示词](handoff/report-update-20261103/design-prompt.md)、[双语海报提示词](handoff/report-update-20261103/poster-prompt.md)。只修改自己负责的稿件和生成源，数据与功能口径一致。\n'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'submit')
    args=ap.parse_args(); out=args.output.resolve()
    if out.exists(): ap.error('Output already exists; use a new directory, never overwrite other work')
    git=['git','-c','safe.directory='+ROOT.as_posix()]
    tracked=subprocess.check_output(git+['ls-files','-s','-z'],cwd=ROOT).split(b'\0')
    items={}
    for row in tracked:
        if not row: continue
        info,name=row.split(b'\t',1); name=name.decode('utf-8'); mode=info.decode().split()[0]
        target=destination(name)
        if target:
            if not (ROOT/name).is_file(): raise FileNotFoundError(name)
            items[name]=(target,mode)
    mapping={s:t for s,(t,mode) in items.items()}
    mapping['README.md']='README.md'
    for cat in CATEGORIES: mapping[cat+'/README.md']=cat+'/README.md'
    # Directories explicitly split across categories have a deliberate target, not a guessed parent.
    directories={'.':'.','project':'build/vivado','software':'src/software','software/tests':'sim/software','document':'report','document/evidence':'data/evidence','hardware':'board/hardware','simulation':'sim/rtl','models':'sim/models','research':'src/research','research/competition-skills':'skill','tools':'build/tools','release':'build/release','release/output':'data/history/releases','data':'data'}
    for s,t in mapping.items():
        sp,tp=PurePosixPath(s).parent,PurePosixPath(t).parent
        while str(sp) not in {'.',''} and str(tp) not in {'.',''}:
            directories.setdefault(str(sp),str(tp));sp=sp.parent;tp=tp.parent
    valid_dirs={str(p) for target in mapping.values() for p in PurePosixPath(target).parents}|{'.'}
    directories={s:t for s,t in directories.items() if t in valid_dirs}
    unavailable=[]
    def resolve(source,target,link):
        raw=link.strip().strip('<>')
        if re.match(r'^(?:https?://|mailto:|#|data:)',raw): return raw
        path,sep,anchor=raw.partition('#')
        path=unquote(path)
        old=posixpath.normpath(posixpath.join(posixpath.dirname(source),path))
        if old.startswith('submit/'):
            candidate=old[len('submit/'):]
            new=candidate if candidate in mapping.values() or candidate in valid_dirs else None
        else: new=mapping.get(old,directories.get(old))
        if new is None:
            unavailable.append({'document':target,'original_target':raw})
            return None
        return posixpath.relpath(new,posixpath.dirname(target))+(sep+anchor if sep else '')
    def rewrite(source,target,data):
        if not source.endswith(('.md','.html')): return data
        text=data.decode('utf-8-sig')
        if source.endswith('.md'):
            # Protect fenced source/log excerpts; only transform prose link destinations.
            parts=re.split(r'(```.*?```)',text,flags=re.S)
            def md(m):
                new=resolve(source,target,m[2])
                if new is None: return m[1]+'（历史引用：`'+m[2]+'`）'
                return '['+m[1]+']('+new+')'
            for i in range(0,len(parts),2):
                parts[i]=re.sub(r'\[([^\]\n]*)\]\(([^)\n]+)\)',md,parts[i])
            text=''.join(parts)
        else:
            def html(m):
                new=resolve(source,target,m[3])
                return m[1]+'='+m[2]+new+m[2] if new is not None else 'data-historical-target='+m[2]+m[3]+m[2]
            text=re.sub(r'(href|src)=(\x22|\x27)(.*?)\2',html,text)
        return text.encode('utf-8')
    destinations=set();records=[];counts={cat:0 for cat in CATEGORIES}
    for source,(target,mode) in sorted(items.items()):
        if target in destinations or not re.fullmatch(r'[a-z0-9_./-]+',target): raise ValueError('Invalid/colliding name: '+target)
        destinations.add(target);raw=(ROOT/source).read_bytes();data=rewrite(source,target,raw)
        p=out/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        counts[target.split('/')[0]]+=1
        # Navigation in submit uses rewritten links. Workspace reconstruction
        # must use the original bytes, including documents packaged into ZIPs.
        restore=target
        if data!=raw:
            restore='build/restore/'+target+'.bin'
            if restore in destinations: raise ValueError('Restore path collision: '+restore)
            destinations.add(restore)
            original=out/restore;original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(raw)
            counts['build']+=1
        raw_sha=hashlib.sha256(raw).hexdigest()
        records.append({'source_path':source,'submit_path':target,'restore_path':restore,
                        'mode':mode,'source_sha256':raw_sha,'restore_sha256':raw_sha,
                        'submit_sha256':hashlib.sha256(data).hexdigest(),
                        'transform':'documentation_links_only' if data!=raw else 'none'})
    for name,text in {'README.md':README,'build/prepare_workspace.py':PREPARE,**EXTRAS}.items():
        if name in destinations:
            # The skills root readme was an index; its actual packages remain copied.
            if name!='skill/README.md': raise ValueError('Generated file collision: '+name)
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')
    manifest={'schema':2,'baseline_commit':subprocess.check_output(git+['rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'standalone submission snapshot, no new hardware experiment','files':records,'counts':counts}
    (out/'build/file-map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'report/unavailable-references.json').write_text(json.dumps({'note':'Outside the selected final submission (historical or absent); preserved as text.','references':unavailable},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'copied_files':len(records),'counts':counts,'historical_missing_references':len(unavailable)},ensure_ascii=False))

if __name__=='__main__':main()
