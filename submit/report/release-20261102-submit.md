# 2026-11-02 比赛资料同步：S2 / S3 / CF1A

后续范围决定：本页保留收件时的结果与缺口。当前最终功能以[统一说明](final-function-scope.md)为准；DAS已取消，相关实现和材料已移除。CF1A后续已接回[板测摘要](../data/evidence/cf1a-longrun-20261102/readme.md)，完整运行包见[当前操作单](pynq-final-runtime.md)。

基于main `9259eac4d59caea32114e1932cf95d16a3f47e50`，接回用户更新清单指定的既有代码和结果。本次只有源码归档、目录准备和PC离线检查，没有运行Vivado、下载或操作硬件；A手中新功能尚未交回，不在本次快照中。

## 本批真实来源与接合

| 材料 | 仓库实际位置 | 来源与边界 |
|---|---|---|
| J3与S2硬件 | project/rtl、project/sdc/ps/screen_s2、project/screen_s2 | 最终S2源码ZIP；水平J3-2/M15、垂直J3-3/J14，RGB/VDMA/GPIO及PS I2C0 EMIO；不再叠装纯J3或旧S1 |
| S2匹配bit/HWH/XSA | release/output/screen_s2 | 与S2原源包输出逐字节一致；不是为本次资料整理重新实现 |
| S3驱动与面板 | software/screen、soundsight-screen.sh、soundsight-screen-i2c.sh、soundsight-panel.sh | 完整S3 runtime已含S2驱动；S2源ZIP内旧UI仅属历史，不覆盖现行S3 |
| CF1A最终源码 | software/tetra3d/linux、software/tetra3d/tests | 最终9项增量，包括CF1单DMA接合及CF1A滚动频谱；原运行库/门禁来自A基线 |
| 发布原件 | release/output下6个本批ZIP | S2源包、S2更新、S3更新、CF1、CF1A及A交接包，保持原字节和适用前提 |

逐项来源见[导入记录](../data/evidence/submit-maintenance-20261102/import-sources.json)。源包中部分RTL注释仍写历史T15/W15，实际管脚以同候选XDC和HWH为准；没有修改原件来制造一致。源包重建需要的49项文件由`project/screen_s2/source-map.json`映射到正式目录，公共RTL只维护一份。

## 可以报告的效果

| 批次/环境 | 结果 | 限制 |
|---|---|---|
| S2，既有Vivado2025.2实现 | WNS +0.203ns、WHS +0.036ns；LUT19971/FF22358/BRAM36/DSP41；40846网完成 | CDC-10=1、CDC-11=2、CDC-15=1252；3输入/30输出缺外部delay，非完整物理签核 |
| S2，用户实板 | PS I2C0/Cadence绑定；两轮设置60秒关轴显示/触摸并正常退出；第一轮用户确认触摸，第二轮fault/drops=0 | 不是精确120秒计时，也不是屏幕与声纹/双轴联合验收 |
| S3，主机及首板 | 19项历史主机测试；首板安装/prepare/I2C/面板启动，设备停止读回正常 | 首轮KeyboardInterrupt/runtime_code=1原件保留；正常STOP、双轴/声纹联合未闭合 |
| P02，用户串行发声 | 0.45/TTL10/axes off：本人授予→EXPIRED→另一人15个新有效分数0.0372–0.2200，未重授权 | 限本轮串行场景，不能当总体识别率、混声身份或空间绑定 |
| CF1，真实板测失败现象 | 两轮各2811完整PCM，快照缺口452/441，最终输出0/4 | 程序正常结束不能写成跟随通过；累计drops不是当轮PCM丢包 |
| CF1A，历史PC回放/计算 | 完整4598窗及稀疏3833窗分类/有效向量一致；74回归；前端wall中位下降45.5% | Windows主机纯前端，不含DMA/屏幕/声纹；ARM实时性和实板输出待A测 |

证据：[S2](../data/evidence/screen-s2-20261031/board-result.md)、[S2构建](../data/evidence/screen-s2-20261031/validation.md)、[S3](../data/evidence/screen-s3-20261031/board-first-result.md)、[P02](../data/evidence/p02-ttl-20261031/p02-ttl-result.md)、[CF1](../data/evidence/cf1-board-20261101/board-run-1.json)、[CF1A](../data/evidence/cf1a-20261102/verification/report.md)。历史研究见[相位一致性来源](../data/evidence/joint-peaks-20261101/report.md)，当时“未接入”的结论按当时日期保留。

## 复现与安装边界

当前S2准备入口：在仓库根或submit恢复的工作目录运行：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
```

只复制完整配方到新的短ASCII目录，不运行EDA。随后由使用者在新目录配置Vivado2025.2的PATH或XILINX_VIVADO，手动执行`build.bat`只创建工程/BD/IP；显式`build.bat synth`/`build.bat route`才启动综合/实现，须使用新副本。本次未重跑这些EDA步骤。此入口仅去掉发送方工具路径并改变BAT默认动作；49项原配方及负载逐字节保持。PR30的`rebuild_ps_3d.bat`保留为10月29日旧硬件配方，不能生成S2屏幕候选。

板端说明：[S2安装](../data/evidence/screen-s2-20261031/sd-install.md)、[屏幕驱动](../board/instructions/screen-readme.md)、[S3控制](../board/instructions/screen-control.md)、[CF1A更新](../board/instructions/cf1-update.md)、[A交接](../board/instructions/cf1a-handoff/start-here.md)。CF1A原ZIP要求先有CF1和安装回执，不可直接装到10月30日旧工程；完整仓库源码接合不等于绕过增量安装器前提。S2硬件、S3面板、A基线PS和CF1A源码的组合已经收录，但不是包含个人模型/标定/登记信息的全新SD镜像。

历史研究/回放/安装器测试中依赖的私人录音、旧实验目录、DLL或完整A运行包没有公开。见[研究依赖](../sim/research/coherent-study/readme.md)。公开合成PCM回归可从源码编译C库后运行；不能称私有录音回放天然可在此包独立重跑。

## 贡献与未完成项

A及原作者提供PL声学/双轴、PS运行与score_ttl_v2基线；B侧后续任务接回J3/S2屏幕、S3面板、相位一致性研究及CF1/CF1A接合与计算优化，AI执行代码和离线验证；本次整理不改写原作者署名。接线、下载、现场运行和观察归用户/现场成员。CAM++、Silero、ONNX Runtime、PYNQ及厂商IP属于第三方。A已接手新功能和CF1A板测，交接待执行。

仍缺CF1A ARM实板时限/有效输出/停止、屏幕与声纹双轴联合长稳、真实三维参考角精度及背面俯仰偏差解释、独立声纹阈值标定/身份空间绑定、完整物理签核，以及最终整机图视频、赛事表单和签署。资料包检查不改变这些验收状态。
