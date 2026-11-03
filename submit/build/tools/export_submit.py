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
    p = PurePosixPath(relative)
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
    inputs=[]; seen=set()
    for entry in manifest['files']:
        source = safe(ROOT, entry['submit_path'])
        target = safe(output, entry['source_path'])
        if str(target).casefold() in seen: raise ValueError('Duplicate output path')
        seen.add(str(target).casefold())
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['submit_sha256']:
            raise ValueError('Submission file differs from manifest: '+entry['submit_path'])
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

README = """# SoundSight 最终提交材料 — 2026-11-03

最终范围：RGB触屏、四麦三维定位、声纹验证、双轴指向。已包含PR #40、#41后的源码。
当前组合为S2硬件＋P1/S3面板＋CF1A前端＋CP1/VF1声纹与score_ttl_v2许可。
水平J3-2/M15、垂直J3-3/J14；默认不开轴。

P1新增开机自启、触屏录入及确认关机，见[产品化操作与验收](report/screen-product.md)。
[最新软件更新包](board/artifacts/soundsight_screen_product_p1.zip)已包含在本目录，供已有匹配S2/S3/CF1A板端安装。
用户已回报C的此前功能测试通过；P1冷启动等新增流程尚待本板测试，不将离线检查记为板测。

七类目录均含实际文件，可整体复制上交。旧平台工程、旧安装包、非最终研究和过时海报副本已移出。
保留的历史数据用于解释已采用优化的基线和失败，不作为可安装的另一套工程。
详情见[清理范围](report/submit-final-scope.md)、[系统与结果](report/design-report.md)、[待补材料](report/pending-materials.md)。

## 独立恢复和检查

在本目录执行，输出目录须为空且位于submit之外：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

进入soundsight_work后：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
python -B tools/check_current_software.py --output ../software_check
python -B -m unittest discover -s software/tests -p test_current_runtime.py
```

恢复不依赖Git或外层仓库。S2准备复制49项配方，不执行EDA；使用Vivado2025.2、xc7z020clg400-2，
输出路径须ASCII且最多78字节。生成目录中的build.bat默认只创建工程，显式synth/route才综合/实现。
软件检查需要Python、NumPy和PATH中的gcc，从包内C源码新编译，运行公开合成输入/逻辑测试。

匹配bit/HWH/XSA见board/artifacts/screen_s2；实际GUI导出和报告见build/handoff及build/reports。
板端步骤见[当前完整运行包说明](report/pynq-final-runtime.md)和[屏幕操作](board/instructions/screen-control.md)。
公共提交不含私人模型、声纹模板、原始录音或机械标定；它不是可直接覆盖SD卡的完整私人运行ZIP。
完整私人包的安装器源码仍收录，旧增量包与旧打包入口不再作为当前操作路径。

没有新增板测、综合或实现。真实精度、身份与声源绑定及联合长稳的缺项仍按证据记录。
原件与失败不改写；file-map记录恢复路径。被移出的历史材料仍可从源仓库及Git历史追溯。
"""

EXTRAS = {
 'src/README.md': """# 当前实现

rtl仅收录S2配方依赖。software包含当前PS、屏幕、三维和共享C算法。
common/s1及冻结头仍被当前求解器调用；文件中历史STM32命名不代表另带STM32固件。
声纹核心的pipeline_bench、short_bench、stream_bench也是生产依赖，不能按名字删除。
""",
 'sim/README.md': """# 当前验证源码

软件与tetra3d测试可在恢复后的工作目录执行，见[根说明](../README.md)。
rtl保留PS侧测试台和模型，属于模块验证资产；旧STM32整链测试和旧仿真启动配方不再交付。
本批仅运行公开输入的软件回归，未重新执行RTL仿真。
""",
 'build/README.md': """# 当前硬件与复现

vivado/screen_s2及../src/rtl组成S2的49项配方；handoff/screen_s2是实际导出。
reports/current为本次收到的工具报告，reports/ps_3d/screen_s2为S2原有审查报告。
prepare_workspace.py从本提交独立恢复，tools/prepare_screen_s2.py只准备新工程目录。
""",
 'board/README.md': """# 板端材料

artifacts/screen_s2提供匹配bit/HWH/XSA；scripts为当前启动入口，instructions为屏幕操作。
旧增量安装ZIP、旧位流及旧平台交付包已移除。
实际安装说明见[完整运行包](../report/pynq-final-runtime.md)，公共源码不包含私人模型与用户配置。
""",
 'data/README.md': """# 实验依据

evidence保留当前屏幕、声纹、三维及技能交付的原始验证记录。当前软件测试自行生成合成输入。
基线、被拒绝的优化数值与失败记录是对比依据，并不表示这些候选进入最终产品。
[声纹指标](evidence/speaker-report-materials/metrics.csv)的不同计时边界不可相加。
旧STM32迁移、六麦研究、海报草稿与历史发布包不在当前提交范围。
""",
 'skill/README.md': """# 比赛技能包

fpga-module-verification及pynq-overlay-dma-validation为实际技能源码、示例和许可证。
恢复工作目录后可执行：

```text
python -B release/check_competition_skills.py --skills-root research/competition-skills --output ../skill_check
```

不提供--vivado-bin时只做离线检查。技能验收证据不等同当前整机验收。
""",
 'report/README.md': """# 当前设计说明

从[设计与结果](design-report.md)、[提交范围](submit-final-scope.md)、[运行说明](pynq-final-runtime.md)开始。
P1见[产品化说明](screen-product.md)，本轮原生BD/资源/时序见[报告索引](../build/reports/current/readme.md)。
requirements保留赛事原始模板及规则，不能当作已完成的设计报告。
旧海报含已取消功能，已移出本提交；正在其他聊天修改的源稿没有被覆盖。
unavailable-references.json记录当前交付之外的历史引用，不提供失效链接。
""",
 'report/design-report.md': """# 当前系统与可报告结果

Zynq PL完成四麦采集、时差特征、连续PCM、双轴PWM和停止保护；PS运行CF1A四面体定位、
CP1/VF1声纹评分与score_ttl_v2许可，P1在S3面板上增加开机自启、触屏声纹录入、模式保存和确认关机，
通过S2的RGB/VDMA和PS I2C0 EMIO显示与触摸。
纯声音跟随与声纹跟随是两个独立模式，默认关轴。当前三维不估计距离。

A及原作者提供PL/PS和许可基线，B侧后续负责算法迁移、声纹计算优化、J3/S2/S3及CF1/CF1A实现与验证；
用户及现场成员执行真实上板操作。CAM++、Silero、ONNX Runtime和厂商IP归各第三方。

| 证据 | 结果及适用范围 |
|---|---|
| S2既有实现 | WNS +0.203ns、WHS +0.036ns；CDC与外部I/O约束仍有缺项，非完整物理签核 |
| S2实板 | 两轮设置60秒的显示/触摸及正常退出；非联合长稳 |
| P02串行测试 | 本人授予许可，过期后另一人15个有效分数0.0372–0.2200未重授权；非总体识别率 |
| 声纹优化 | RX4校验CPU下降95.71%；CP1+VF1同轮离线并发下降18.12%；不同计时边界不可相加 |
| CF1A PC | 4598完整窗/3833稀疏窗分类与有效向量一致，前端wall中位下降45.5%；非ARM端到端延迟 |
| CF1A板测 | 摘要30.016秒，36组方向、22次动作、3次快照缺口、正常停止；现场另有几分钟观察，不能混成定量长稳 |
| C功能验收 | 用户回报声纹、三维转向和屏幕三项通过；不扩展为定量误差或完整识别率 |
| P1产品化 | 141项离线测试通过，其中新增43项；开机、触屏录入、确认关机及两轮冷启动实板待测 |

可安装更新包：[P1 ZIP](../board/artifacts/soundsight_screen_product_p1.zip)；
操作见[安装与测试](screen-product.md)，已有S2/S3/CF1A板端安装本包即可，不能将其用作空白SD系统镜像。
原生硬件报告见[本轮脚本导出](../build/reports/current/screen_s2_20261103/readme.md)，
产品化软件验证见[P1证据](../data/evidence/screen-product-p1-20261103/readme.md)。
硬件未变，硬件时序不能用于证明新增软件功能已上板通过。

来源：[声纹原始指标](../data/evidence/speaker-report-materials/metrics.csv)、
[CF1A板测](../data/evidence/cf1a-longrun-20261102/readme.md)、
[CF1A离线验证](../data/evidence/cf1a-20261102/verification/report.md)、
[S2实板](../data/evidence/screen-s2-20261031/board-result.md)。
没有精确测角，不生成随机误差或宣称最大误差≤5°。失败与缺口保留在相应证据中。
""",
 'report/pending-materials.md': """# 尚缺材料

- 三维定量参考角误差、几分钟观察与原生日志关联、联合长稳和端到端响应。
- 独立声纹门限标定、混声场景与身份/空间声源绑定；TTL串行测试不能替代这些。
- 当前候选CDC、外部接口时序及完整物理签核。
- P1安装后首次自启、触屏录入与关机、正常断电后两轮冷启动；板子离线，本轮未执行。
- 最终整机图/视频、按最终四项功能更新的正式报告与海报、赛事签署材料。

本次同步包含P1产品化软件和用户脚本重新导出的S2报告；位流、算法及底层参数未改。
此前C功能通过按用户回报记录，新P1实板验收单独保留待测。
""",
}



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
        records.append({'source_path':source,'submit_path':target,'mode':mode,'source_sha256':hashlib.sha256(raw).hexdigest(),'submit_sha256':hashlib.sha256(data).hexdigest(),'transform':'documentation_links_only' if data!=raw else 'none'})
    for name,text in {'README.md':README,'build/prepare_workspace.py':PREPARE,**EXTRAS}.items():
        if name in destinations:
            # The skills root readme was an index; its actual packages remain copied.
            if name!='skill/README.md': raise ValueError('Generated file collision: '+name)
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')
    manifest={'baseline_commit':subprocess.check_output(git+['rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'standalone submission snapshot, no new hardware experiment','files':records,'counts':counts}
    (out/'build/file-map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'report/unavailable-references.json').write_text(json.dumps({'note':'Outside the selected final submission (historical or absent); preserved as text.','references':unavailable},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'copied_files':len(records),'counts':counts,'historical_missing_references':len(unavailable)},ensure_ascii=False))

if __name__=='__main__':main()
