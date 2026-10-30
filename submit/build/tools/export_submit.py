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
    if name in {'soundsight.sh', 'soundsight-3d.sh'}: return 'board/scripts/'+name
    pairs = [
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

README = '''# SoundSight 比赛提交材料

此文件夹包含实际文件，可整体复制、压缩或上交。无需外层仓库或B电脑盘符。源码基线及逐文件来源见`build/file-map.json`；这是固定交付快照，后续开发在原仓库进行，再统一更新提交副本。

```text
submit/
  README.md
  src/       RTL、PS软件、三维/C算法及历史研究源码
  sim/       testbench、软件测试、参考模型和仿真脚本
  build/     Vivado配方、构建工具、实现报告、独立工作目录准备脚本
  board/     上板脚本、操作说明、硬件资料与现场回报
  data/      测试输入、原始结果、匿名指标和历史归档
  skill/     两个完整技能包：脚本、示例、测试、许可
  report/    设计说明、贡献报告、AI协作资料和第三方声明
```

## 项目与当前结果

唯一主方案为Zynq-7020 PL+PS/PYNQ：四麦40mm标称正四面体定位、双轴运动控制和可选声纹许可。水平T15、垂直W16。A维护PL和当前总工程；B的历史STM32/PYNQ、三维/DAS、声纹适配与优化贡献见[设计与贡献报告](report/design-report.md)。CAM++、Silero、ONNX Runtime及厂商组件属于第三方。

当前配方沿PR #30接入LAT1两槽最新定位结果策略，保留31个RTL、Hann数据、实际BD/PS配置、双FFT参数及5份约束。2026-10-30用户两轮声纹双轴测试正常结束并确认跟随，建议TTL10秒；第二轮淘汰1个旧结果。对应已导出实现WNS+0.176ns/WHS+0.029ns，但实际四约束候选缺垂直PWM输出延迟，不能称完整I/O签核。纯声音供电重启后用户接12V适配器报告长稳正常，未测电源波形。声纹门限/其他人对照及声纹联合长稳仍待验证，见[本次集成说明](report/release-20261030.md)。

## 从零复现

1. 完整解压或复制本`submit`文件夹。安装Python 3；Vivado复现另需2025.2与器件`xc7z020clg400-2`支持，软件C测试需C编译器。仅阅读资料不需要安装EDA。
2. 在本文件夹根目录执行：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

这一步只读取本包中的实际文件，复制到新的独立工作目录；不下载、不调用Git、不启动EDA或硬件。它恢复原源码/脚本使用的目录与大小写，避免为提交改名而修改算法、厂商文件或运行逻辑。输出须不存在或为空，拒绝覆盖既有工作。

3. 进入生成的`soundsight_work`，先执行包依赖离线检查：

```text
python -B -m unittest discover -s software/tests -p test_vivado_portable.py
```

4. 将Vivado 2025.2和Python加入PATH，或按生成目录中的`tools.local.env.example`填写仅供本机使用的`tools.local.env`。在Windows终端执行：

```bat
project\\script\\rebuild_ps_3d.bat --output "..\\soundsight_vivado"
```

新Vivado输出目录完整路径须ASCII且不超过78字节。成功后打开`SoundSight_PS_3D.xpr`。该步骤创建工程/BD/IP；综合、实现、STA、生成位流和硬件操作由使用者后续执行。本次提交整理没有执行这些动作。

5. 仿真输入与执行说明见[sim说明](sim/README.md)。板端安装与运行见[board说明](board/README.md)，必须配套当前候选bit/HWH、PYNQ环境以及使用者自己的模型和登记配置。包内历史STM32/Vitis/旧SD包有日期与范围，不能当成当前W16运行镜像。

源码/脚本中的原相对路径是生成工作目录中的路径；包内Markdown链接已改为本包相对链接，阅读请直接在`submit`内进行。报告/历史证据中的旧机器路径仅记录来源，不是本包运行依赖。`build/file-map.json`记录出处和转换，原始日志、JSON、CSV、图片、二进制与归档ZIP保持内容。

## 材料边界

设计说明、源码、现有结果和协作记录已实际装入七类目录；缺失的最终整机照片/视频、签署文件和原始AI对话不得编造。见[尚缺材料](report/pending-materials.md)。PC、ARM离线、真实采集、用户观察及Vivado结果各自标明，不能把目录或包检查作为整机验收。
'''

EXTRAS = {
 'src/README.md': '# 设计源码\n\n`rtl/`保存真实RTL与Hann数据；`software/ps`、`software/tetra3d`及`software/common`保存PS与算法实现。`software/stm32`和`research`包含已弃用路线/历史研究，不能误作当前部署。执行前按[根README](../README.md)生成独立工作目录；源码内容保持，文件名在提交目录统一小写。\n',
 'sim/README.md': '# 仿真与离线验证\n\n本目录包含实际`rtl/tb`、`rtl/script`、`software`测试及`models`参考模型。在按[根README](../README.md)生成的工作目录运行原测试路径。\n\n```text\npython -B -m unittest discover -s software/tests -p test_vivado_portable.py\npython -B -m unittest discover -s software/tests -p test_volume_gate.py\n```\n\nRTL仿真使用Vivado 2025.2 XSim，原入口为`simulation/script/run.bat batch <case>`。用例及实际历史结果见[运行说明](../report/run-guide.md)和[data/evidence](../data/evidence)。本批只验证提交包的脱离仓库复现，不重跑RTL/板测；软件测试不等于ARM实测。\n',
 'build/README.md': '# 构建配方与报告\n\n`vivado/`内为实际BD、PS/IP Tcl、XDC和工程脚本，`tools/`为Python/Tcl助手，`reports/`内为已有实现报告。完整PR #30配方和31个RTL在本包中，不需回到原仓库取文件。\n\n先在submit根运行`python -B build/prepare_workspace.py --output ../soundsight_work`，然后按[根README](../README.md)在生成目录启动工程配方。`prepare_workspace.py`只复制本包文件，不执行EDA/硬件。原配方的详细说明见[复现说明](../report/vivado-ps-3d-rebuild.md)。\n\n提交目录用小写路径；准备脚本按`file-map.json`恢复工具所需的原名。报告的结果只适用于其记录的候选，不能代替新工程STA。\n',
 'board/README.md': '# 上板与现场资料\n\n`scripts/`是实际板端启动脚本，`hardware/`为板卡/麦克风/接线原件，`instructions/`为当前安装和操作说明，`results/`为用户现场回报。`artifacts/ps_3d_latest_result/`保存当前匹配bit/HWH/XSA；私人声纹模型和档案不进入公开交付。历史Vitis与旧SD包不能当成当前部署。\n\n从[三维SD说明](instructions/pynq-three-d-sd.md)、[W16更新](instructions/pynq-w16-update.md)、[声纹操作](instructions/pynq-speaker-3d.md)阅读；脚本在按[根README](../README.md)准备的工作目录运行。所有硬件命令仅供后续由使用者操作，本批未运行。\n\n双轴用户观察见[手动回报](results/board-manual-result.md)，长期运行失败见[重启回报](results/board-unexpected-reboot.md)，短录入/评分见[声纹板测](results/speaker-enrollment-board-result.md)。\n',
 'data/README.md': '# 输入、参考结果与实验证据\n\n`fixtures/`为真实已保存的合成测试输入与参考生成器，`evidence/`为原仓库实验原件，`research/`含六麦合成音频与结果，`history/releases/`为有版本范围的旧交付包。\n\nB的原始指标在[evidence/speaker-report-materials/metrics.csv](evidence/speaker-report-materials/metrics.csv)，贡献总览见[对应报告](evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)。原日志、JSON/CSV、历史ZIP保留内容，不把新目录当成新实验。本目录不含新增私人录音、模板或模型权重。\n',
 'skill/README.md': '# 比赛技能包\n\n本目录已放入两个技能包的实际脚本、示例、测试与许可证：`fpga-module-verification/`和`pynq-overlay-dma-validation/`，不是外部链接占位。各自的`skill.md`是小写提交入口；需安装到要求`SKILL.md`的助手时在使用者副本恢复该名称，或用本包准备脚本恢复原目录。\n\n在生成工作目录中可运行：\n\n```text\npython -B release/check_competition_skills.py --skills-root research/competition-skills --output ../skill_check\n```\n\n省略`--vivado-bin`仅做离线测试；XSim标NOT_RUN。真实PYNQ Skill验收仍未完成。许可、历史失败与实际AI纠错见[交付说明](../report/competition-skills-delivery.md)、[AI协作记录](../report/competition-skills-ai-corrections.md)。\n',
 'report/README.md': '# 设计报告与协作资料\n\n本目录包含实际设计文档、现有DOCX手册、第三方声明和AI纠错记录。先阅读[设计报告](design-report.md)、[现行架构](main-architecture.md)、[B贡献原稿](../data/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)和[材料缺项](pending-materials.md)。\n\n历史设计/STM32路线按原时点理解。文件中的操作命令以准备脚本生成的工作目录为基准；本文档链接以submit目录为基准。原仓库中就未收录的历史引用转成文字线索，清单见`unavailable-references.json`；不会把不可访问本机链接包装成可复现入口。\n',
 'report/design-report.md': '''# SoundSight 设计与成员贡献报告

本稿依据包内已有源码和记录整理，不新增实验。现行方案为Zynq-7020 PL+PS/PYNQ，STM32方案保留为历史工作。

## 系统实现

PL完成四麦PDM采集、分窗预处理、FFT/PHAT/IFFT、六对时差特征和连续PCM输出，并实现双轴PWM、STOP及超时保护。计算/AXI域100MHz，采集/控制域61.44MHz。PS运行同一双核Linux/PYNQ，用Python调用C求解器；以六对时差和标称40mm正四面体几何求远场方位/俯仰，不输出距离。程序对通道、几何、质量、残差及极点处理进行检查，再经音量和多帧筛选形成目标。

声纹复用第三方CAM++和Silero，团队承担ARM适配、连续前端、缓存、采集进程、目标管理和许可接合。PCM格式为48kHz四路S24符号扩展S32；每包32字节头加512帧四通道数据，共8224字节。声纹前端使用mic0，48k→16k FIR降采样及Mel特征，嵌入与登记模板作余弦比较。身份结果时效、语音状态、音量及方向有效性分别约束，不能将可用评分视为身份验收。

`follow-sound`是显式纯声音跟随；`speaker`和`run --axes`要求声纹许可。默认不开轴，手动标定独立。当前水平T15、垂直W16。

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
| 后续W16、短录入和目标管理 | A接续实现，用户执行现场测试 | 手动两轴可转；5秒录入成功、本人两次可用分数0.6103/0.5563 | 该行是10月29日历史；10月30日门限0.45两轮联合短测见release-20261030，其他人对照待做 |

算法思想、CAM++、Silero、ONNX Runtime及厂商/PYNQ组件属于第三方。B的贡献是具体实现、迁移、优化与验证；A的后续成果不倒填为B当时完成；接线、下载、实际运行和观察按现场记录归属。

详细数值来源、失败候选与候选版本见[B贡献总览](../data/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md)、[算法索引](../data/evidence/speaker-report-materials/06-b-algorithms.md)、[原始指标](../data/evidence/speaker-report-materials/metrics.csv)。AI协作可见记录见[纠错选编](competition-skills-ai-corrections.md)，不冒充完整原始对话。

## 当前未完成项

真实三维参考角精度与通道/几何标定、连续运行稳定性、全行程和机械闭环、声纹独立阈值/身份方向关联及DAS真实拾音效果仍未验收。缺失的整机照片/演示视频、签署文件和原始AI对话须由实际材料补齐；详见[pending-materials](pending-materials.md)。整理完整目录不改变这些结果。
''',
 'report/pending-materials.md': '''# 仍需补充的比赛材料与验收

| 项目 | 已有内容 | 尚缺内容 |
|---|---|---|
| 完整源码与工程配方 | 本submit的RTL、PS程序、PR #30 BD/IP/XDC与准备脚本 | 匹配bit/HWH/XSA已在board/artifacts；运行环境及个人模型配置仍由使用者提供 |
| 设计报告 | design-report.md、算法贡献、现有手册与接口说明 | 参赛者按最终结果确认定稿、必要签署与赛事表单 |
| 实验 | PC/ARM离线、采集、W16用户观察及失败原件 | 真三维精度/标定、电源原因仪器确认、身份方向关联、声纹联合长稳及DAS实麦效果 |
| 图片/视频 | 已有麦克风/板卡材料与实现截图 | 当前整机、连接/机构、界面和真实演示视频 |
| AI协作 | 可见请求与纠错选编、代码和失败修复证据 | 按赛事要求选择真实提示词/回答原文；禁止补写伪造聊天 |
| 声纹 | 第三方适配、离线优化、5秒录入与本人评分 | 独立他人对照、门限标定、稳定延迟及联合双轴验收 |

本次只整理现有资料，无硬件操作或新增实验；没有替参赛者向赛事平台提交。
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
