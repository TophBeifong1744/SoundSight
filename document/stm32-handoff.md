# STM32 主方案 FPGA 工程交接（无 ILA）

【历史资料，2026-10-29状态更新】STM32路线已弃用；当前唯一主方案是Zynq-7020的PL＋PS/PYNQ。下文保留当时的设计、命令、分工及验证范围，不再作为当前派工或验收要求。当前入口以仓库README.md和document/main-architecture.md为准。

当前正式入口为一份公共源码与可搬移重建配方，目标`xc7z020clg400-2`、Vivado 2025.2。2026-10-19已将用户外部工程的有效RTL修改接回。此入口不创建ILA、不加载调试XDC、不依赖发送方F盘目录。

## 本次接回了什么

| 项目 | 核查与处理 |
|---|---|
| 公共RTL | `project/rtl/ss_spi_mode0.sv`接回CS释放时的`!fall`检查，避免SCK刚下降时用旧`edge_age`提交；无公共ABI变化 |
| 其他源码和数据 | 25份RTL、Hann系数、两份STM32 XDC共28项，与当前外部副本忽略换行/行尾空格后匹配；不复制第二套RTL |
| BD、PS、时钟和复位 | 最新导出的63项功能事件与现有配方一致；保留原配方和既有GUI布局 |
| 独立FFT IP | 两份XCI与此前原件相同；每个27项显式参数匹配正式创建配方，不重复导入XCI |
| 工程运行设置 | 77项属性匹配现有`stm32_settings.tcl`；保留Global综合模式 |
| ILA | 外部导出登记的`spi_ila_debug.xdc`为禁用状态；正式入口完全不登记此文件，也不创建ILA或调试hub |
| 实现资料 | 原位置更新用户最新时序、布局后资源报告，并保留路由后DRC警告原件 |

最新导出中的BD内部XCI只用于核对，不再作为另一套维护对象。原始导出作为证据可能含历史绝对路径和禁用调试引用，不能直接作为正式重建入口。当前工程配方的功能配置未变，因此不为同步日期重写它们。

本次材料及比较结果见[10月19日接回证据](evidence/stm32-handoff-20261019/README.md)。首次接回的历史配置与原件见[10月18日记录](evidence/stm32-handoff-20261018/README.md)。

## 正式依赖与唯一维护位置

完整FPGA工程输入仍为[40项文件清单](build/stm32-handoff-files.txt)，没有新增第二套工程目录：

| 类别 | 正式位置 |
|---|---|
| 25份公共RTL与Hann初始化数据 | `project/rtl` |
| 两份STM32引脚/时序约束 | `project/sdc/stm32` |
| BD和PS配置 | `project/bd/stm32.tcl`、`project/ip/ps7_stm32.tcl` |
| 官方FFT创建配方 | `project/ip/create_fft_ip.tcl` |
| 工程创建、源清单与运行设置 | `project/script` |
| 工具查找与准备辅助入口 | `tools` |

STM32和PL+PS目标共用公共RTL；各自使用BD和约束。生成的wrapper、官方IP输出、综合/实现结果在接收方生成，不提交工作缓存。相同工程后续更新原位置，旧版由Git历史保留；任务证据不作为另一套产品源码。

## 接收方如何重建

1. 安装Vivado 2025.2、Zynq-7000器件支持和Python 3；按所用官方IP满足许可要求。
2. 取得完整仓库，或按40项清单保留相对目录。将`tools.local.env.example`复制为本机`tools.local.env`并填写本机工具位置，或配置PATH。不要照搬发送方工具路径。
3. 在仓库根目录执行：

```powershell
.\project\script\run.bat --check-tools
.\project\script\run.bat prepare stm32
.\project\script\run.bat outputs stm32
.\project\script\run.bat open stm32
```

`prepare`在`project/par`准备工程；已有输出时拒绝覆盖，不能拿它重置用户在途工程。`outputs`生成官方IP/BD输出；两者不运行综合、实现或下载。综合、实现、生成bit由用户在Vivado执行，启动和烧录也由用户完成。

本次未重新执行上述EDA步骤。静态核查确认所列依赖存在、活动入口没有本机工作区路径或ILA引用；不等于已实际重建通过。

## 已有硬件报告与未完成范围

用户10月19日最新报告记录：布线后WNS +0.379 ns、WHS +0.036 ns；布局后LUT 13895、FF 14458、BRAM 25、DSP 41。报告在[project/reports/stm32](../project/reports/stm32/README.md)，其中历史布局截图明确保留10月18日标签。路由后DRC仍有警告及报告数量截断，没有新的同候选专项CDC报告。

本次只同步用户已实施的板级修正，按当前工作流不重复仿真；新构建、新板测与Flash回读均未执行。首发CS短脉冲导致的SPI_FORMAT仍待排查，禁用ILA不构成故障修复。原始ILA诊断与当前无ILA实现分别记录，不混称同一候选。

本次不更新`software/vitis/stm32`中的旧XSA、组件ZIP、ELF或配套bit，也不改B侧STM32固件。复现Flash上电运行还需与新FPGA候选匹配的XSA、PS初始化/FSBL、启动镜像和STM32固件；现有旧软件包不能自动视为最新候选配套。PL+PS目标、声学精度和机械闭环不继承此次STM32物理结果。
