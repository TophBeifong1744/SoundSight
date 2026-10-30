# Reliaze 三条 CDC-10 控制跨域修复

后续接收：用户12:47新构建已确认三条CDC-10消除，WNS +0.229ns且资源不增加；bit/HWH/XSA匹配。新板包、剩余Warning及上板步骤见[CDC修复PCM包](pynq-pcm-cdc-first-run.md)。以下保留源码修复阶段记录。

日期：2026-10-24。针对用户已完成 PCM 接入的 `SoundSight_PS_Reliaze` 工作工程；用户负责重新综合、实现和生成 bit。

## 改了什么

原来三个同步器的入口前都有组合逻辑，短毛刺可能被另一时钟域采到。现在先在 61.44MHz 源时钟下寄存，再用官方 XPM 两级同步到 100MHz。

| 原告警位置 | 本次处理 |
|---|---|
| `compute/u_core/enable_sync` | 启用 `SRC_INPUT_REG=1`，源时钟使用已有 `io_clk` |
| `audio_capture/core/run_sync` | 删除重复同步器，音频直接复用计算模块的 `core_enable` |
| `audio_capture/core/drain_sync` | 移到 `ss_dual_compute/with_audio`，使用真实源时钟和源端寄存；音频接收已同步的状态 |

`ss_dual_compute` 与 `bd_clean_compute` 增加两个 **1 位、100MHz域** 输出 `audio_run`、`audio_draining`。`ss_audio_capture` 与 `bd_audio_capture` 对应输入改为 `run_enable`、`compute_draining`，删除原 `_async` 输入及内部两套同步器。

已接入 PCM 的 BD 只迁移两根控制线：

```text
compute/audio_run      -> audio_capture/run_enable
compute/audio_draining -> audio_capture/compute_draining
```

PS 仍接收原 61.44MHz 域的 `compute/draining`。主控制域的 STOP 与舵机保护路径保留。音频包格式、地址、DMA、缓存深度、PCM位宽、时钟、复位和引脚均沿用既有设计；没有新增 IP、FIFO、DSP 或 BRAM，也没有增加 false path 或屏蔽 CDC 告警。

按这三处控制同步结构计算：原来 3×2=6 个触发器；现在两条链各为源端1级＋目的端2级，共6个。整体实际 LUT/FF 数以新实现报告为准。`AUDIO_ENABLE=0` 的旧目标不生成 drain 同步链，公共 enable 链增加1个源端触发器。源端寄存使控制传播增加约一个61.44MHz周期（16.28ns），不改变PS本地STOP的即时保护。

## 怎么更新

完整转发包为 `release/output/soundsight_reliaze_cdc_update.zip`，根目录 `SoundSight_Reliaze_CDC_Update`。这是新增包，原 Servo、PCM 板包和旧工程更新包均保留。**只发送 Tcl 不够，必须附带同包16份RTL依赖。** 包内没有新 bit/HWH。

1. Vivado 2025.2 打开 `F:/AMD/work/SoundSight_PS_Reliaze/SoundSight_PS_Reliaze.xpr`，确认没有正在运行的综合/实现。
2. 在 Tcl Console 执行当前仓库入口：

```tcl
source {E:/Users/Toph Beifong/Documents/GitHub/SoundSight/project/bd/update_ps_reliaze.tcl}
```

转发包则完整解压，使用解压目录下 `project/bd/update_ps_reliaze.tcl` 的实际路径。无需先执行旧 manual/PCM 脚本。

脚本先检查当前旧/新控制连线、工程路径、器件和运行状态；备份到工作工程 `handoff/before_pcm_*`，复制RTL、刷新模块引用、迁移两根线，执行 BD Validate 与输出生成。已完成的新接线允许重复执行；混合接口或控制线来源不符时拒绝更新。备份不是自动回滚事务，中途报错应保留日志和备份。

成功末尾应出现：

```text
RELIAZE_PREPARED: manual + timed PCM; DMA=0x40400000 audio=0x43C00000; T15/W15 unchanged
RELIAZE_CDC_CONTROL_V2: source-registered controls; shared compute/audio run; rebuild bit/HWH required
NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED
```

首次刷新模块时，Vivado可能显示 `Coretcl 2-1280`，对应新增两个compute输出、替换两个audio输入；脚本随后完成接线。检查最终 Validate/输出生成是否成功；其他报错不能据此忽略。隔离验证还发现 Vivado 首次打开BD会污染调用者临时变量，入口已用独立过程隔离，避免误判工程目录。

## 验证和剩余边界

定向验证包括共享控制毛刺/启停/收尾/复位，音频样本及封包、完整双时钟算法的正常帧/在途取消/恢复、关闭音频与旧模式、手动保护；完整结果见[验证记录](../data/evidence/ps-cdc-control-fix-20261024/readme.md)。测试使用官方 XPM 和相应官方 FFT/IFFT 仿真模型；PCM为已知夹具输入，不是实麦录音。控制测试仅在明确的收尾互锁场景强制内部 busy，真实计算取消由完整链路回归覆盖。

隔离工程已测试旧PCM BD升级、再次执行、Validate与输出生成；两次更新后的BD结构相同。前后核对两根控制线之外的BD字段与显式PS配置，HWH中DDR/MIO/时钟等参数相同；八个未启用的交叉触发器选择项由 `DISABLED` 序列化为 `<Select>`，交叉触发使能仍为0，PS端口未变化。详细差异保留在证据中。

**本次仿真不能证明布线后CDC消失或时序收敛。** F盘工程未由AI改写；以下由用户执行：

1. 更新成功后，重新综合、实现、生成 bit，并导出同次 HWH/XSA。不要复用旧运行结果或旧HWH。
2. 打开新 Implemented Design，检查 `report_cdc -details`：原三条CDC-10路径应消失，新增两条控制链应识别为源端寄存＋两级同步，且没有新增Critical。原CDC-15 Warning及其他RDC/DRC须分别判断，本次没有将其整体关闭。
3. 检查 Timing Summary 的 setup/hold/pulse-width 失败端点，`check_timing` 的时钟/约束覆盖，DRC、层级资源与高扇出/拥塞情况；比较旧实现 WNS +0.165ns、WHS +0.036ns，但旧数值不能用于接受新候选。
4. 新报告与 bit/HWH 核对后再更新独立PYNQ包、做无动作PCM接收。原 `soundsight_pynq_pcm.zip` 仍含旧位流，不包含本次修复；既有板包打包脚本仍绑定旧候选，不能绕过其哈希拒绝来混装。

当前交付范围是源码、Tcl和仿真/BD准备证据；新综合、实现、布线CDC、资源、bit及板测均未执行。
