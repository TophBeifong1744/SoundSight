# SoundSight 比赛提交材料

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

PR #30提供最新完整Vivado源码配方：31个RTL、Hann数据、真实BD/PS配置、双FFT参数及5份约束。已有工程创建/BD Validate/IP HDL/wrapper成功记录，不代表重新综合或上板通过。双轴手动可转已有用户回报；纯声音跟随长稳发生整板重启，原因未定。5秒声纹录入与本人关轴评分已有回报，门限、他人对照及声纹联合双轴仍未验收。

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
project\script\rebuild_ps_3d.bat --output "..\soundsight_vivado"
```

新Vivado输出目录完整路径须ASCII且不超过78字节。成功后打开`SoundSight_PS_3D.xpr`。该步骤创建工程/BD/IP；综合、实现、STA、生成位流和硬件操作由使用者后续执行。本次提交整理没有执行这些动作。

5. 仿真输入与执行说明见[sim说明](sim/README.md)。板端安装与运行见[board说明](board/README.md)，必须配套当前候选bit/HWH、PYNQ环境以及使用者自己的模型和登记配置。包内历史STM32/Vitis/旧SD包有日期与范围，不能当成当前W16运行镜像。

源码/脚本中的原相对路径是生成工作目录中的路径；包内Markdown链接已改为本包相对链接，阅读请直接在`submit`内进行。报告/历史证据中的旧机器路径仅记录来源，不是本包运行依赖。`build/file-map.json`记录出处和转换，原始日志、JSON、CSV、图片、二进制与归档ZIP保持内容。

## 材料边界

设计说明、源码、现有结果和协作记录已实际装入七类目录；缺失的最终整机照片/视频、签署文件和原始AI对话不得编造。见[尚缺材料](report/pending-materials.md)。PC、ARM离线、真实采集、用户观察及Vivado结果各自标明，不能把目录或包检查作为整机验收。
