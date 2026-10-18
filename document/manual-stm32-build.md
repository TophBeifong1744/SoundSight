# FPGA＋STM32：仓库外手工搭建

本页适用于Vivado 2025.2、xc7z020clg400-2。用户选择仓库外工作目录；当前不使用仓库run.bat建工程。先建RTL Project，勾选Do not specify sources at this time，再选择准确器件。

## 添加源码

Add Sources → Add or create design sources → Add Files，从仓库project/rtl选择以下文件，勾选Copy sources into project。不要添加整个RTL目录；清单含旧参考模块的排除边界。完成后核对源文件属性路径位于外部工程。

```text
doa_math_pkg.sv
bd_clean_compute.v
bd_stm32_link.v
doa_math_serial.sv
doa_phat_client.sv
f1a_frame_store.sv
fft29_official.sv
i17_turntable_pwm_guard.sv
ifft25_official.sv
motor_drive.v
pdm_cic3.v
ss_actuator_control.sv
ss_async_word.sv
ss_bist_source.sv
ss_clean_compute.sv
ss_control_regs.sv
ss_dual_compute.sv
ss_fft_frontend.sv
ss_pair_engine.sv
ss_pcm_windows.sv
ss_pdm_capture.sv
ss_preprocess.sv
ss_snapshot_queue.sv
ss_spi_mode0.sv
ss_stm32_link.sv
hann-u18f17.mem
```

共25个HDL文件和1个内存初始化文件。doa_math_pkg.sv需在使用该包的SystemVerilog文件之前编译；.sv按SystemVerilog识别，.v按Verilog识别，hann-u18f17.mem作为内存初始化数据。Target language选Verilog，Simulator language选Mixed。为已有XPM原语启用库，在当前外部工程Tcl Console输入：

```tcl
set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY XPM_FIFO} [current_project]
```

当前尚未生成IP和BD，因此部分层次暂时未解析，不选择内部tile作为最终顶层。不要添加PS版封装、旧单域tile或旧时钟模块，也不要复制旧生成IP目录。

## 两个独立FFT IP

从IP Catalog添加两个Fast Fourier Transform (xfft 9.1)，组件名必须分别为ss_fft29和ss_ifft25，RTL按这些名字实例化。它们在RTL内部连接，不另放入BD。

| 配置 | ss_fft29 | ss_ifft25 |
|---|---|---|
| Channels | 1 | 1 |
| Transform length | 1024 | 1024 |
| Implementation | Radix-2 Burst I/O | 相同 |
| Runtime configurable length | 关闭 | 相同 |
| Data format | Fixed Point | 相同 |
| Input width | 29 | 25 |
| Phase factor width | 24 | 24 |
| Scaling | Scaled | 相同 |
| Rounding | Convergent Rounding | 相同 |
| Output ordering | Natural Order | 相同 |
| Throttle scheme | Non Real Time | 相同 |
| ACLKEN | 关闭 | 相同 |
| ARESETn、OVFLO、XK_INDEX | 开启 | 相同 |
| Cyclic prefix | 关闭 | 相同 |
| Target clock / throughput | 100 MHz / 50 MSPS | 相同 |
| Data / phase factors / reorder memory | Block RAM | 相同 |
| Stages using block RAM | 0 | 0 |
| Hybrid memory | 关闭 | 相同 |
| Complex multipliers | Use Mults Resources | 相同 |
| Butterfly | Use LUTs | 相同 |
| Super sample rate | 1 | 1 |

当前准确配置见project/ip/create_fft_ip.tcl；界面中未展示或被架构固定的字段按该配方核对。前向/逆向和每级缩放由RTL的运行时配置字控制，不能只凭组件名推断方向。生成输出时不启动OOC综合；选择Global模式生成输出（若出现该对话框）。暂不运行综合/实现。

## 随后创建BD时的清单

BD名称soundsight_stm32_bd。加入两个Module Reference：bd_clean_compute实例名compute、bd_stm32_link实例名link。官方IP如下：

| IP | 数量 | 实例名 |
|---|---|---|
| ZYNQ7 Processing System | 1 | ps7 |
| Clocking Wizard | 2 | clk_main、clk_audio |
| Processor System Reset | 2 | core_reset、io_reset |
| Utility Vector Logic | 2 | core_reset_gate、io_reset_gate |
| XPM CDC Generator | 2 | core_release、io_release |
| Constant | 2 | zero、one |

共13个BD单元。不要照PS版添加AXI总线/寄存器链。时钟经PS FCLK100→clk_main输出96与100→clk_audio输出61.44；复位极性与失锁保护逐项按document/design/stm32/时钟复位.txt配置。完整线表见document/design/stm32/BD连线.txt。实际DDR/MIO由用户配置。

先完成源码和两个FFT IP，再逐步配置BD；添加单元不代表连线或配置已完成。约束从project/sdc/stm32复制进工作工程，外部端口名与XDC一致；最终顶层是BD生成的wrapper。后续接回与交付按AGENTS.md和git-workflow.md执行。

本次测试安排：阶段完成并导出后，在空目录检查重建；这不是长期交接前置要求，也不自动授权AI启动EDA。
