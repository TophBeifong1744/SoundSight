# STM32 主方案 FPGA 工程交接

本次已把用户在 Vivado 2025.2 中实际配置的 BD、PS7、IP 和运行设置接回正式目录。交接用源码与配方重建，不需要旧 F 盘工程数据库。这里交接的是 **FPGA 工程**，不包含 STM32 的完整 Keil 外设工程、PYNQ 镜像或可直接下载的 bit。

## 这次用了哪些原件

读取用户导出目录 `F:/AMD/work/SoundSight_STM32/handoff/20261018_153509` 的全部四份文件：

| 原件 | 用途 | 接回位置 |
|---|---|---|
| `stm32_bd.tcl` | 13 个 BD 单元、全部连线及 GUI 布局 | `project/bd/stm32.tcl` |
| 同一份 `stm32_bd.tcl` 内的 PS7 属性 | DDR、MIO、FCLK、复位和外设开关 | `project/ip/ps7_stm32.tcl` |
| `project.tcl` | 核对器件、源文件、Global 模式、综合/实现运行参数 | `project/script/vivado.tcl`、`stm32_settings.tcl` |
| `ss_fft29.xci` | 前向 FFT 实际参数 | 核对现有 `project/ip/create_fft_ip.tcl`，27 项显式参数一致 |
| `ss_ifft25.xci` | 逆向 FFT 实际参数 | 同上，27 项显式参数一致 |

此外读取外部工程的实际 `.bd`、生成的复位/PS7 IP 配置、26 份源文件和两份 STM32 XDC；核对未显式导出的默认参数及当前磁盘源码。四份导出原件原样保存在 [证据目录](evidence/stm32-handoff-20261018/README.md)。原件可能保留个人路径，只作证据，不能直接作为重建入口。

## 已接回的实际配置

- 器件：`xc7z020clg400-2`，Vivado `2025.2`，Verilog / Mixed，启用 XPM CDC、FIFO、Memory。
- PS7：DDR3 型号配置为 `MT41J256M16 RE-125`，总线 32 bit，约 533.333 MHz；这是用户工程配置值，不是本次重新核验 DDR 实物型号。
- QSPI 使用 MIO 1–6，UART0 使用 MIO 14–15；PS Bank0 为 3.3 V、Bank1 为 1.8 V。这是 PS MIO 电压，不能拿来替代 PL Bank13 的供电检查。
- FCLK0 为 100 MHz；一级 Clocking Wizard 输出 96 MHz 和 100 MHz，二级把 96 MHz 转为 61.44 MHz。
- 冷复位来自 `FCLK_RESET1_N`。两个 Processor System Reset 的外部/辅助复位均低有效；辅助复位接 1、调试复位接 0。两组 XPM 异步复位同步释放也均低有效，释放同步级数为 3。
- STM32 版未使用 GP0 AXI；`FCLK_RESET0_N` 未接业务逻辑。PL+PS 版继续使用独立配方，本次没有把 STM32 的 PS7 配置覆盖过去。
- 两个 FFT 均为 1024 点、Radix-2 Burst、定点、缩放、收敛舍入、自然序，输入分别 29/25 bit、相位因子 24 bit；运行时方向及缩放字仍由 RTL 给出。
- 两个 FFT 与 BD 均采用 Global 综合（`SYNTH_CHECKPOINT_MODE=None`），不复用原工程 DCP。综合/实现策略为 Vivado Defaults，保留实际导出的 77 项运行属性；布局后物理优化开启、布线后物理优化关闭。
- BD 共 13 个单元：PS7、两个时钟 IP、两个复位 IP、两个逻辑门、两个 XPM 复位同步器、两个常量、`compute` 和 `link`。共有 30 条普通网络和两条接口网络；没有 ILA。

## 交接实际需要哪些文件

**工程入口及完整依赖共 40 个文件**。逐文件准确清单在 [stm32-handoff-files.txt](build/stm32-handoff-files.txt)，全部路径相对项目根目录，打包时保留目录结构。

| 分类 | 数量 | 文件 |
|---|---:|---|
| 公共 RTL | 25 | 下面列出；均在 `project/rtl` |
| 初始化数据 | 1 | `project/rtl/hann-u18f17.mem` |
| STM32 约束 | 2 | `project/sdc/stm32/board_pins.xdc`、`interface_timing.xdc` |
| BD / PS / FFT / 运行设置 | 4 | `project/bd/stm32.tcl`、`project/ip/ps7_stm32.tcl`、`project/ip/create_fft_ip.tcl`、`project/script/stm32_settings.tcl` |
| 工程入口与源清单 | 4 | `project/script/run.bat`、`setting.bat`、`vivado.tcl`、`src_list.txt` |
| 入口辅助与准备结果记录 | 4 | `tools/run_vivado.py`、`tool_config.py`、`vivado_cli.tcl`、`audit_native.tcl` |

25 份 RTL 为：

```text
doa_math_pkg.sv           bd_clean_compute.v        bd_stm32_link.v
doa_math_serial.sv        doa_phat_client.sv        f1a_frame_store.sv
fft29_official.sv         i17_turntable_pwm_guard.sv ifft25_official.sv
motor_drive.v            pdm_cic3.v                ss_actuator_control.sv
ss_async_word.sv         ss_bist_source.sv         ss_clean_compute.sv
ss_control_regs.sv       ss_dual_compute.sv        ss_fft_frontend.sv
ss_pair_engine.sv        ss_pcm_windows.sv         ss_pdm_capture.sv
ss_preprocess.sv         ss_snapshot_queue.sv      ss_spi_mode0.sv
ss_stm32_link.sv
```

本次便于转发的包另外带上本说明、逐文件清单、`tools.local.env.example` 空模板、`.gitignore` 和原 `LICENSE`，**共 45 个文件**。不包含本机 `tools.local.env`、生成的 wrapper、`.xpr`、BD 数据库、缓存、运行结果。wrapper 和官方 IP 由 Vivado 根据配方生成；原始两份 XCI 已用于核对，不再作为重建时重复导入的第二份 IP。

包按当前本地工作区制作，包括用户已同步的三份 RTL 和两份 STM32 XDC；并不是只打包旧 Git 提交。用户另两份 PS XDC 和 Word 修改仍保留在仓库，不属于这份 STM32 FPGA 包。

## 接收人如何使用

1. 安装 Vivado 2025.2 和 Python 3。把 `tools.local.env.example` 复制为 `tools.local.env`，填写自己的 `VIVADO_ROOT`、`PYTHON_EXE`；若工具已在 PATH 中，可不填。不要沿用发送方的工具盘符。
2. 在解压根目录执行下面命令。`prepare` 在包内 `project/par` 创建新工程；已有工程时会停止，不覆盖。这里创建的是供接收人使用的工程，不会修改发送方 F 盘工作副本。

```powershell
.\project\script\run.bat --check-tools
.\project\script\run.bat prepare stm32
.\project\script\run.bat outputs stm32
.\project\script\run.bat open stm32
```

3. 在 Vivado 中查看 `soundsight_stm32_bd` 和 wrapper。综合、实现仍由使用者自行点击；脚本不会自动运行。输出生成后的准备检查针对尚未启动 run 的新工程，不应在已有综合/实现工作副本上当作通用检查命令使用。

导出的 PS 配置也不等于启动镜像：真实 PS 初始化、FCLK/复位释放、DDR 启动和 STM32 通信仍需实机验证。接收人若使用不同板卡，需按实物调整 PS 和引脚。

## 本次验证到哪里

已执行 Tcl 命令记录比对：整理后的 BD 与原导出的单元、显式属性、端口、连线和布局相同；两个 FFT 各 27 项显式参数及 77 项运行属性一致。40 个工程依赖齐全，活动配方无 F/E 盘依赖。外部工程 26 份源文件与仓库文本一致，仅 `ss_pair_engine.sv` 有行尾空白差异；两份 STM32 XDC 文本一致。

用户提供的布线后报告：WNS `+0.248 ns`、WHS `+0.036 ns`；LUT `13894`、FF `14458`、BRAM `25`、DSP `41`。这些是外部手工工程的已有结果，本次没有重新运行 Vivado、仿真、综合、实现或板测，不能把静态配方比对说成已经重建通过。当前磁盘比较也不能单独证明当时 DCP 的完整输入身份。

原始报告、比较脚本及实际结果见完整仓库中的 [证据说明](evidence/stm32-handoff-20261018/README.md)。轻量交接 ZIP 不带该证据目录；上述证据链接需要在完整仓库中打开，不属于重建依赖。本次没有修改电路行为、用户 XDC 或 Word；没有给既有 `par` 或 F 盘工程写入任何文件。
