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

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('src', 'sim', 'build', 'board', 'data', 'skill', 'report')


def destination(name):
    if name == 'research/competition-skills/README.md':
        return 'skill/package-overview.md'
    if name.startswith('submit/') or name in {'README.md', 'AGENTS.md', 'data/README.md'}:
        return None
    if name.startswith('.') or name.split('/')[0] in {'src', 'sim', 'build', 'board', 'skill', 'report'}:
        return None
    if '/.gitattributes' in name:
        return None
    if name == 'LICENSE': return 'report/licenses/license.txt'
    if name == 'THIRD_PARTY.md': return 'report/licenses/third-party.md'
    if name == 'tools.local.env.example': return 'build/config/tools.local.env.example'
    if name in {'soundsight.sh', 'soundsight-3d.sh', 'soundsight-screen.sh', 'soundsight-screen-i2c.sh', 'soundsight-panel.sh'}: return 'board/scripts/'+name
    if name.startswith('document/cf1a-handoff/'):
        return 'board/instructions/cf1a-handoff/'+name.rsplit('/',1)[1].lower()
    if name in {'document/screen-readme.md','document/screen-control.md','document/cf1-update.md'}:
        return 'board/instructions/'+name.rsplit('/',1)[1]
    if name.startswith('release/output/') and name.rsplit('/',1)[1] in {'soundsight_screen_ps_i2c_s2.zip', 'soundsight_three_d_coherent_cf1.zip', 'soundsight_screen_ps_i2c_s2_source.zip', 'soundsight_three_d_coherent_cf1a.zip', 'soundsight_screen_control_s3.zip', 'soundsight_a_cf1a_handoff_20261102.zip'}:
        return 'board/packages/'+name.rsplit('/',1)[1]
    pairs = [
        ('software/tetra3d/tests/', 'sim/tetra3d/'),
        ('research/coherent-study/', 'sim/research/coherent-study/'),
        ('release/output/screen_s2/', 'board/artifacts/screen_s2/'),
        ('project/rtl/', 'src/rtl/'),
        ('project/reports/', 'build/reports/'),
        ('project/', 'build/vivado/'),
        ('software/tests/', 'sim/software/'),
        ('software/vitis/', 'board/history/vitis/'),
        ('software/', 'src/software/'),
        ('simulation/', 'sim/rtl/'),
        ('models/', 'sim/models/'),
        ('tools/', 'build/tools/'),
        ('hardware/', 'board/hardware/'),
        ('document/evidence/', 'data/evidence/'),
        ('document/', 'report/'),
        ('research/competition-skills/', 'skill/'),
        ('research/six-mic/results/', 'data/research/six-mic/results/'),
        ('research/', 'src/research/'),
        ('release/output/ps_3d_latest_result/', 'board/artifacts/ps_3d_latest_result/'),
        ('release/output/', 'data/history/releases/'),
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

README = '''# SoundSight 比赛提交材料 — 2026-11-02

本目录可整体复制、压缩和上交。七类目录存放实际源码、脚本、产物和证据；无需外层仓库或发送方盘符。

```text
submit/
  README.md
  src/
  sim/
  build/
  board/
  data/
  skill/
  report/
```

## 当前候选与效果

唯一方案为Zynq-7020 PL+PS/PYNQ，四麦40mm正四面体，水平J3-2/M15、垂直J3-3/J14。硬件为S2 RGB/VDMA/GPIO + PS I2C0 EMIO，面板为S3，三维软件为CF1A。原有score_ttl_v2许可保留；普通声音模式与声纹模式分开，默认关轴。

S2既有实现WNS +0.203ns/WHS +0.036ns，仍有CDC和外部I/O时序缺项。用户两轮基础显示/触摸与停止已有证据。S3首板中断、CF1两轮最终输出0/4的失败现象保留。P02本人→到期→另一人本轮串行验证通过，不能写成总体识别率。CF1A历史PC回放4598完整/3833稀疏一致、74回归、前端wall下降45.5%，ARM实时性仍待A板测；真实三维精度、联合长稳未验收。

详见[本次来源与结果](report/release-20261102-submit.md)、[贡献报告](report/design-report.md)、[未完成项](report/pending-materials.md)。A总工程与B侧后续实现、用户现场操作和第三方模型贡献分别记载。

## 独立准备

在本目录执行（输出须为新的空目录）：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

只用包内文件恢复源码原路径和大小写；不需要Git、不联网、不启动EDA或硬件。进入生成的soundsight_work后：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
python -B tools/check_current_software.py --output ../software_check
```

第一条只复制49项S2硬件配方文件并生成可搬移BAT。Vivado2025.2（xc7z020clg400-2）由使用者安装；s2_work完整路径须ASCII且不超过78字节。后续人工运行build.bat只创建工程，显式synth/route才综合/实现；本次资料维护未执行EDA。

第二条需要Python、NumPy和PATH中的gcc，使用源码新编译C库，运行合成输入/逻辑回归，不访问硬件。历史私有录音回放和安装器测试另需未公开基线，不能作为本包独立验收；见[研究依赖](sim/research/coherent-study/readme.md)。

配套S2 bit/HWH/XSA位于board/artifacts/screen_s2。板端操作见[材料说明](report/release-20261102-submit.md)和board/instructions；原CF1A ZIP要求已经安装CF1，不能直接套到10月30日旧工程。个人模型、录音、声纹模板和机械标定不在本包。原S2源ZIP保留历史build.bat默认综合行为，当前可搬移准备入口以本页为准。

file-map记录实际来源和字节校验；源代码、原始JSON/日志/ZIP不作导航改写，Markdown/HTML仅调整链接。历史W16/PR30配方和失败按当时版本保留，不代表当前S2。当前整理没有新增实测，也没有向比赛平台提交。
'''

EXTRAS = {
 'src/README.md': '''# 设计源码

`rtl/`保存真实RTL与Hann数据；`software/ps`、`software/tetra3d`及`software/common`保存PS与算法实现。`software/stm32`和`research`包含已弃用路线/历史研究，不能误作当前部署。执行前按[根README](../README.md)生成独立工作目录；源码内容保持，文件名在提交目录统一小写。
''',
 'sim/README.md': '''# 仿真与离线检查

本目录包含RTL测试、软件测试、tetra3d回归及研究脚本。按[根说明](../README.md)恢复原目录后，运行tools/check_current_software.py，用公开合成输入及正式源码新编译C库检查CF1A/在线流程/声纹显示等行为。Windows仅提供resource导入shim，不模拟性能测量。历史私有录音研究依赖见[说明](research/coherent-study/readme.md)。本次不运行RTL或硬件。
''',
 'build/README.md': '''# 构建配方与报告

当前S2见vivado/screen_s2和reports/ps_3d/screen_s2，实际RTL位于../src/rtl。按[根说明](../README.md)恢复工作目录，再执行tools/prepare_screen_s2.py复制49项完整配方。旧PR30入口保留作历史，不包含屏幕；本次没有启动EDA。
''',
 'board/README.md': '''# 板端材料

当前S2匹配bit/HWH/XSA在artifacts/screen_s2，原增量包在packages，实际启动脚本在scripts，操作说明在instructions。S3与CF1A源码已经接回。CF1A安装前提为已装CF1；个人模型/标定需使用者提供。见[本次同步](../report/release-20261102-submit.md)。旧W16和短测证据按日期保留，不能代替当前联合验收。
''',
 'data/README.md': '''# 输入、参考结果与实验证据

`fixtures/`为真实已保存的合成测试输入与参考生成器，`evidence/`为原仓库实验原件，`research/`含六麦合成音频与结果，`history/releases/`为有版本范围的旧交付包。

B的原始指标在[evidence/speaker-report-materials/metrics.csv](evidence/speaker-report-materials/metrics.csv)，贡献总览见[对应报告](evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)。原日志、JSON/CSV、历史ZIP保留内容，不把新目录当成新实验。本目录不含新增私人录音、模板或模型权重。
''',
 'skill/README.md': '''# 比赛技能包

本目录已放入两个技能包的实际脚本、示例、测试与许可证：`fpga-module-verification/`和`pynq-overlay-dma-validation/`，不是外部链接占位。各自的`skill.md`是小写提交入口；需安装到要求`SKILL.md`的助手时在使用者副本恢复该名称，或用本包准备脚本恢复原目录。

在生成工作目录中可运行：

```text
python -B release/check_competition_skills.py --skills-root research/competition-skills --output ../skill_check
```

省略`--vivado-bin`仅做离线测试；XSim标NOT_RUN。真实PYNQ Skill验收仍未完成。许可、历史失败与实际AI纠错见[交付说明](../report/competition-skills-delivery.md)、[AI协作记录](../report/competition-skills-ai-corrections.md)。
''',
 'report/README.md': '''# 设计报告与协作资料

本目录包含实际设计文档、现有DOCX手册、第三方声明和AI纠错记录。先阅读[设计报告](design-report.md)、[现行架构](main-architecture.md)、[B贡献原稿](../data/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)和[材料缺项](pending-materials.md)。

历史设计/STM32路线按原时点理解。文件中的操作命令以准备脚本生成的工作目录为基准；本文档链接以submit目录为基准。原仓库中就未收录的历史引用转成文字线索，清单见`unavailable-references.json`；不会把不可访问本机链接包装成可复现入口。
''',
 'report/design-report.md': '''# SoundSight 设计与成员贡献报告

本稿依据包内已有源码和记录整理，不新增实验。现行方案为Zynq-7020 PL+PS/PYNQ，STM32方案保留为历史工作。

## 系统实现

PL完成四麦PDM采集、分窗预处理、FFT/PHAT/IFFT、六对时差特征和连续PCM输出，并实现双轴PWM、STOP及超时保护。计算/AXI域100MHz，采集/控制域61.44MHz。PS运行同一双核Linux/PYNQ，用Python调用C求解器；以六对时差和标称40mm正四面体几何求远场方位/俯仰，不输出距离。程序对通道、几何、质量、残差及极点处理进行检查，再经音量和多帧筛选形成目标。

声纹复用第三方CAM++和Silero，团队承担ARM适配、连续前端、缓存、采集进程、目标管理和许可接合。PCM格式为48kHz四路S24符号扩展S32；每包32字节头加512帧四通道数据，共8224字节。声纹前端使用mic0，48k→16k FIR降采样及Mel特征，嵌入与登记模板作余弦比较。身份结果时效、语音状态、音量及方向有效性分别约束，不能将可用评分视为身份验收。

`follow-sound`是显式纯声音跟随；`speaker`和`run --axes`要求声纹许可。默认不开轴，手动标定独立。当前S2为水平J3-2/M15、垂直J3-3/J14；屏幕由PS I2C0 EMIO及VDMA/RGB接合。

## 分工与成果

| 工作 | 归属、方法 | 已有结果 | 范围与未完成项 |
|---|---|---|---|
| PL、连续PCM、双轴保护与总工程 | A及原作者；2026-10-29起A全面维护 | PR #30完整配方创建、BD Validate、IP HDL/wrapper成功；W16报告见build/reports | 本次未运行EDA；最新导出实现缺垂直PWM输出延迟，声纹联合长稳未验收 |
| STM32 S1/S2 | B的C99算法、驱动和自检 | PC 4705/15980断言；本板11通过、0失败、11跳过 | 已弃用路线，不能写作跨板通信完成 |
| 二维PYNQ及存储修正 | B算法桥接、板测分析、8条/50ms批写 | 有声/静音各1000帧原件；后续长采2831/3000高水位停止 | 有效率不是参考角准确率；失败保留 |
| 三维与DAS | B的算法迁移、几何最小二乘、分数延迟及回退 | PC154组数值、17非法、15几何、4类CLI；DAS16项及70/8方向验证 | 真实三维精度、DAS实麦改善未验收 |
| 六项软件优化 | B方向稳定、可选质量加权、环缓冲、校准接口、几何缓存、双轴映射 | PC86项不同Python测试；DAS耗时下降35.50%、块分配峰值下降96.18% | 不是ARM或整机RSS效果，不等于全部候选已采用 |
| 声纹迁移/计算优化 | B对第三方模型的工程适配与RX4/CP1/VF1优化 | opt1 ARM离线前端下降40.55%；RX4校验CPU下降95.71%；同轮CP1+VF1离线并发下降18.12% | 计时边界不同不可相加；原性能门限未达；失败候选保留 |
| AF1入口 | B复用A runtime增加无声纹跟随入口 | 板端原21+新7离线检查通过 | 不代表机械或声纹验收；W15不动是历史失败 |
| 后续W16、短录入和目标管理 | A接续实现，用户执行现场测试 | 手动两轴可转；5秒录入成功、本人两次可用分数0.6103/0.5563 | 该行是10月29日历史；10月30日门限0.45两轮联合短测见release-20261030，10月31日P02串行他人对照已有本轮通过，非总体识别率 |

算法思想、CAM++、Silero、ONNX Runtime及厂商/PYNQ组件属于第三方。B的贡献是具体实现、迁移、优化与验证；A的后续成果不倒填为B当时完成；接线、下载、实际运行和观察按现场记录归属。

详细数值来源、失败候选与候选版本见[B贡献总览](../data/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)、[算法索引](../data/evidence/speaker-report-materials/06-b-algorithms.md)、[原始指标](../data/evidence/speaker-report-materials/metrics.csv)。AI协作可见记录见[纠错选编](competition-skills-ai-corrections.md)，不冒充完整原始对话。

## 10月31日至11月2日新增成果

见[详细来源与证据](release-20261102-submit.md)：B侧后续J3/S2屏幕硬件、S3控制面板、CF1相位一致性单DMA接合、CF1A滚动频谱与补历史。A提供原PL/PS/声纹许可总工程，用户执行现场测试。S2基础显示/触摸通过；S3首板中断及CF1输出0/4保留；CF1A45.5%仅PC前端wall改善，ARM待测。P02串行场景已通过，混声与空间身份绑定仍未验收。

## 当前未完成项

真实三维参考角精度与通道/几何标定、连续运行稳定性、全行程和机械闭环、声纹独立阈值/身份方向关联及DAS真实拾音效果仍未验收。缺失的整机照片/演示视频、签署文件和原始AI对话须由实际材料补齐；详见[pending-materials](pending-materials.md)。整理完整目录不改变这些结果。
''',
 'report/pending-materials.md': '''# 尚缺材料与验收 — 2026-11-02

| 项目 | 已收录 | 尚缺 |
|---|---|---|
| 完整代码 | S2/J3 RTL、BD/PS/IP/XDC/49项配方、S3完整驱动面板、CF1A最终增量与A基线依赖 | A尚未交回的新功能；个人运行环境/模型/标定由使用者提供 |
| 匹配硬件 | S2 bit/HWH/XSA与既有实现报告 | 当前CDC/外部delay缺项闭合，不冒充完整物理签核 |
| 屏幕 | S2两轮基础显示/触摸/停止；S3代码与19项历史主机测试/首板中断 | 正常STOP及声音/声纹/双轴联合、异常I2C恢复和长稳 |
| 三维 | CF1旧板测、CF1A离线优化及一份30秒ARM摘要：36组有效方向/22次动作/3次快照缺口，正常停止；用户另回报约几分钟双轴跟随 | 几分钟观察与30秒摘要的关联、长稳量化及实时期限、真实参考角精度、背面俯仰偏差根因 |
| 声纹 | P02本人→到期→他人本轮串行场景通过；旧联合短测 | 独立阈值标定、同时说话/空间身份绑定、总体识别率、联合长稳 |
| 其他效果 | DAS与旧软件优化的对应PC/ARM记录 | DAS实麦改善、机械全行程/精确标定、电源根因仪器证据 |
| 比赛材料 | 现有设计说明、板卡图片、S3预览、AI可见纠错与第三方声明 | 最终整机图/演示视频、正式定稿/签署/赛事表单、按赛事选取真实AI对话原文 |

本轮归档新增接收CF1A用户板测证据，不代表整理者重新执行测试。长稳分类中用户几分钟观察与30秒摘要分开记录，见data/evidence/cf1a-longrun-20261102；历史“待测”按日期保留，最新状态见report/current-status.md。
''',
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
    # Current operating instructions and actual manual reports belong in board, not a link-only index.
    board_docs=('pynq-three-d-sd.md','pynq-w16-update.md','pynq-speaker-3d.md','pynq-speaker-enrollment.md','pynq-three-d-dual-axis.md','ps-manual-calibration.md')
    for name in board_docs:
        src='document/'+name; items[src]=('board/instructions/'+name,items[src][1])
    for name in ('board-manual-result.md','board-unexpected-reboot.md'):
        src='project/reports/ps_3d/w16/'+name; items[src]=('board/results/'+name,items[src][1])
    src='document/evidence/speaker-enrollment-20261029/board-result.md'
    items[src]=('board/results/speaker-enrollment-board-result.md',items[src][1])
    mapping={s:t for s,(t,mode) in items.items()}
    mapping['README.md']='README.md'
    for cat in CATEGORIES: mapping[cat+'/README.md']=cat+'/README.md'
    # Directories explicitly split across categories have a deliberate target, not a guessed parent.
    directories={'.':'.','project':'build/vivado','software':'src/software','software/tests':'sim/software','document':'report','document/evidence':'data/evidence','hardware':'board/hardware','simulation':'sim/rtl','models':'sim/models','research':'src/research','research/competition-skills':'skill','tools':'build/tools','release':'build/release','release/output':'data/history/releases','data':'data'}
    for s,t in mapping.items():
        sp,tp=PurePosixPath(s).parent,PurePosixPath(t).parent
        while str(sp) not in {'.',''} and str(tp) not in {'.',''}:
            directories.setdefault(str(sp),str(tp));sp=sp.parent;tp=tp.parent
    unavailable=[]
    def resolve(source,target,link):
        raw=link.strip().strip('<>')
        if re.match(r'^(?:https?://|mailto:|#|data:)',raw): return raw
        path,sep,anchor=raw.partition('#')
        path=unquote(path)
        old=posixpath.normpath(posixpath.join(posixpath.dirname(source),path))
        if old.startswith('submit/'):
            new=old[len('submit/'):]
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
    (out/'report/unavailable-references.json').write_text(json.dumps({'note':'Already absent from source repository; preserved as text, not invented files.','references':unavailable},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'copied_files':len(records),'counts':counts,'historical_missing_references':len(unavailable)},ensure_ascii=False))

if __name__=='__main__':main()
