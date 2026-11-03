# PL+PS按音量大小决定是否输出方向

本批只增加音量门限，不做人声识别。低音量时，新的应用方向输出无效且角度为null；采集、求解原始结果和记录仍保留，因此可以诊断和标定，不把低音量当丢帧或STOP故障。没有接入舵机，多帧平滑仍是独立离线试验。

## 音量怎么测

在100MHz计算域现有1024点、四通道预处理里，复用每通道均值，取**去直流后、乘Hann前**的PCM绝对值。四通道共4096项相加后除以4096向下取整：

```text
mean[c] = RNE(sum(PCM[c,0..1023]) / 1024)
level = floor(sum_c,sum_n(abs(PCM[c,n] - mean[c])) / 4096)
```

单位是数字PCM采样计数，不是声压分贝，也不是RMS/平方能量。固定直流偏置会被去掉；正常声音越大，通常此值越大。四路平均代表整阵列窗口幅度，不声称每个麦克风都达到门限。

没有新增开方、乘法、除法IP或外部接口。绝对值25位、累加37位、除4096为右移12位，输出32位。每个domain0样本在原MULTIPLY状态累计一次，OUT背压不重复累加；第4通道最后样本被接受后有效。复用现有样本周期，不增加FFT单元/窗长/步进或状态等待。实际资源和时序仍需用户对新候选综合、实现验证。

## PS专用接口扩展（STM32冻结合同不变）

用户已授权先接入独立PL+PS版本。公共头和`FROZEN_SSOT_ABI.md`仍描述STM32 v1.0，本说明定义PS专用v1.1；不把新语义偷偷写回STM32合同。

| 项目 | LEVEL_ENABLE=0（原行为） | LEVEL_ENABLE=1（PS扩展） |
|---|---|---|
| ABI寄存器0x6c | 0x00010000 | **0x00010001** |
| STATUS bit17 | 0 | 1，支持真实幅度测量 |
| STATUS bit5 | 原真实帧0、BIST1 | 当前锁帧的幅度测量有效位；取消/源错误/未完成测量为0 |
| 0x14（旧名SIGNAL_ENG） | 原真实0、BIST100000 | 锁定真实帧的level计数；仅bit5有效时可用；BIST仍100000 |
| 六对words、原因码、STOP、快照命令 | 不变 | 不变 |

所有新增RTL参数默认0。STM32配方及控制寄存器源码没有更改，既有采集/数值链照旧；PS准备配方显式启用。启用时，音量32位及有效位随六对在同一输出槽锁存，并和整帧共同经过1025位XPM FIFO跨域；禁用时保留原992位路径。到PS已有双槽后，音量与帧号/六对一起锁定。没有“实时音量寄存器”混进旧快照，也不增加队列容量。

## 软件输出与门限

`run_buffered.py`新增两个互斥选项：

- `--measure-level`：只记录测量，尚无标定门限，真实应用方向始终无效。
- `--min-level T`：T为1..16777215整数，level ≥ T且原求解有效、帧无故障/取消，才输出有效方向。固定门限，不自适应、不做人声判断、不新增滞回。

这两个选项要求新ABI和能力位；连接旧bit会在写控制寄存器前拒绝，不能把旧的0当静音。原入口不带音量选项时仍只认旧ABI，因此新bit必须使用音量选项；旧bit仍用原命令。BIST的100000是合成值，保留数值自测但不能作为音量标定点或应用方向。

记录分工：

| 字段 | 用途 |
|---|---|
| `frame.energy`、STATUS bit5/17 | 原始锁帧幅度及有效性 |
| `result` | 原C求解器的原始结果，仅用于数值审计；低音量时其中可能仍有原始角度 |
| `volume.level_counts/threshold_counts` | 本帧真实幅度、配置门限，及明确单位 |
| **`direction_output.valid/angle_q8/reason`** | **应用实际应使用的输出**；低音量为false/null/`below_volume_threshold` |

不要把`result.direction_valid`当成音量门限后的许可。无效角度用null，不能当0°目标；历史目标也不能当新观测。低音量帧仍先存入RAM再释放PL槽，磁盘失败仍按原机制保帧；不重写冻结S1拒绝码，不截断原始记录。VolumeClient显式拒绝arm/command/motion调用，当前包不授权执行器动作。

## 本次替换的RTL（共10份）

全部来自唯一`project/rtl`，复制到用户自己的**PL+PS工作工程中原来的源文件位置**，不要又登记另一份同名源：

```text
ss_preprocess.sv
ss_fft_frontend.sv
f1a_frame_store.sv
ss_pair_engine.sv
ss_clean_compute.sv
ss_dual_compute.sv
bd_clean_compute.v
ss_ps_control_regs.sv
ss_ps_link.sv
bd_ps_link.v
```

接口明细补充：前处理/FFT输出`frame_level[31:0]`与`frame_level_valid`；后端/F1a在发布拍转换为`feature_level[31:0]`与`feature_level_valid`。所有阶段用参数`LEVEL_ENABLE`贯穿，默认0。数值端口不变。

## 用户后续Vivado步骤

### 推荐：一次执行源码复制与BD更新

用户已复制工作工程，当前目标为 **SoundSight_PS_Volume**。先在Vivado打开这个副本及其中的BD，保存编辑，确认没有正在运行的综合/实现。在Tcl Console执行：

```tcl
source {<SoundSight仓库>/project/bd/update_ps_volume.tcl}
```

脚本自动读取当前工程目录，不写死工程名或盘符。它先备份旧BD、XPR和10份旧源码到当前工程`handoff/before_ps_volume_*`，把10份新RTL实际复制进工作工程、重新登记。随后会**保存BD，自动关闭并重新打开当前工程**，清除会话中旧的模块参数状态，再按实际IP对象刷新`compute`/`ps_link`的端口。最后启用音量参数、连接两条内部信号、Validate并生成BD输出文件。开始前请先保存编辑器中尚未保存的源码。

现有Wrapper和顶层不变；BD使用Global生成模式，脚本不启动综合/实现。若RTL仍指向原PS工程或仓库，会复制到当前Volume工程的`ps_volume_sources`再改引用，不覆盖原文件。若两份有效约束`board_pins.xdc`和`interface_timing.xdc`仍在原PS工程，则把**当前实际约束原样复制**到Volume工程`ps_constraints`，保留已有约束属性，不使用仓库默认约束覆盖用户修改。备份的`sources.tsv`记录RTL原位置与新位置，原约束也随本次备份保留。

看到`PS_VOLUME_READY_FOR_GENERATE_BITSTREAM`且没有ERROR后，可直接点击 **Generate Bitstream**，确认Vivado提示的重新综合/实现。脚本成功只是准备完成，**不代表新候选时序通过**；生成后仍检查实际实现时序/DRC并导出配套HWH。发生错误则停止本轮构建并保留Console原文；脚本不是自动回滚事务，失败前的修改和备份都保留。

不需要先手动复制源码，也不需要再组合执行`resume_ps_volume.tcl`和`enable_ps_level.tcl`。此前停在模块刷新时，也统一执行上面的完整入口；每次备份目录不同，不覆盖首次备份。完整入口已在Vivado 2025.2的干净隔离副本中实际通过复制、刷新、Validate和输出生成，另有7项离线Tcl流程测试通过。实际验证记录及先前失败原因见[evidence/ps-volume-gate/TCL-UPDATE.md](evidence/ps-volume-gate/TCL-UPDATE.md)。

### 手工方式（备用）

增量包为`release/output/soundsight_ps_volume_update.zip`，ZIP根直接是`project`、`software`、`simulation`、`tools`、`document`，没有外套工程目录。它依赖现有SoundSight项目/板端软件，不是完整工程，也没有新bit/HWH。包内测试、说明和小型原始日志可用于核对；不要把整个ZIP当Vivado工程导入，只替换上节10份设计源码。

1. 保留当前已通过bit/HWH和源版本。确认无正在运行的构建；只更新上面10份外部PL+PS工程源码。不要覆盖STM32实机工程。
2. 打开现有PL+PS BD，对`compute`和`ps_link`执行模块引用刷新，让两个新端口和`LEVEL_ENABLE`参数出现。
3. 手工把两者`LEVEL_ENABLE`都设为1，再连接：`compute/feature_level[31:0] → ps_link/feature_level[31:0]`、`compute/feature_level_valid → ps_link/feature_level_valid`。原时钟、复位、AXI、六对与控制线不改。没有新增IP或外部引脚。
4. 也可以在刷新后执行本包的`project/bd/enable_ps_level.tcl`完成第3步；脚本检查模块和已有网络冲突后Validate并保存BD，不启动任何综合/实现/下载。该脚本尚未在用户BD执行，若报错原样回传，不换顶层或忽略错误。
5. 用户自己Generate Output Products、综合、实现，检查新候选时序/资源/DRC；通过后才生成配套bit/HWH。旧bit不包含这项功能，软件包不能单独让旧bit测量音量。

## 初次测量与门限选择（等待新bit/HWH）

不能从之前1000帧固定为0的energy反推音量，也不编造一个“合适”的门限。新位流验证加载、时钟复位和新ABI后，先保持执行器未绑定，分别录一段安静环境和正常说话/发声的音量分布；选两者之间的整数门限。安静时风扇、音乐、其他噪声超过门限也会通过，这是单纯音量检测的预期边界。

更新软件到板端原目录后，可先做自测：

软件更新保留现有`ps_client.py`、`run_capture.py`、`run_smp.py`、C库及日志，把包内`software/ps`的4份文件及`software/tests`的2份文件复制到板端原`SoundSight_PYNQ`对应目录。`run_buffered.py`同时带入此前已验证的20秒启动等待修复。旧位流期间仍能使用原无音量参数命令；新位流运行必须添加音量选项。SD搬运时仍不覆盖启动文件。配套新bit/HWH等用户本批实现通过后再一起更新。

```text
python3 -B software/tests/test_volume_gate.py -v
```

以下命令仅供**新bit/HWH、ABI0x00010001和现场就绪条件确认之后**使用，仍无动作；清错只允许已解释的历史STOP位：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_buffered.py --hwh soundsight.hwh --output volume-quiet-001.jsonl --mode real --frames 100 --measure-level --clear-faults 0x40
```

用户随后明确采用“先假设一个起点，再通过实际调试修正”。初始试调值定为 **1000个采样计数**，只是便于开始的可修改参数，不是已标定值、底噪估计或有效性结论。初次试调可用`--min-level 1000`替代`--measure-level`；若安静时仍频繁产生有效方向，则结合安静音量分布调高；若正常发声也被压掉，则结合发声音量分布调低。如果两者分布严重重叠，单一门限不能同时保证两者，不能仅靠反复调数值宣称解决。

本次不安排用户立即执行板端命令。第一次可先量测安静与发声分布，也可按上述1000起点启用门限并保存原始幅度；都等新bit/HWH确认后进行。门限改动仅需修改软件参数，不用重新综合。1000并未隐藏为程序默认值，启动时必须显式指定，日志逐帧保存所用门限。

## 验证与交付边界

定向XSim、Python自测和旧模式回归结果见[evidence/ps-volume-gate](evidence/ps-volume-gate/README.md)。隔离工程已完成真实Vivado准备检查，用户实际工作工程的更新仍由用户执行。仿真和BD检查不等于实际资源/时序通过；完整自然PDM实板、实际音量门限、综合、实现和新bit均待用户执行。没有修改C求解数值、机械映射或冻结SPI协议。
