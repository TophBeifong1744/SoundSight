# 最新三维双轴 Vivado 工程复现

最新手工工程的导出入口为 `project/script/export_portable_handoff.tcl`，见[可搬移导出说明](portable-handoff-export.md)。它收集当前工程实际依赖，不仅导出旧目录路径清单；本页既有发布ZIP仍代表其注明的候选。


本入口从正式源码重建完整工程，不依赖发送方的旧工程或盘符。器件为 `xc7z020clg400-2`，要求 Vivado **2025.2** 和 Python 3。只准备工程、生成 IP HDL、检查 BD 和生成顶层 wrapper；**综合、实现、位流和上板由使用者操作**。

## 使用

下载 `release/output/soundsight_vivado_ps_3d.zip` 并解压。打开包内目录；把 Vivado 的 bin 和 Python 加到当前环境的 PATH，或复制 `tools.local.env.example` 为 `tools.local.env`，仅在本机填写 `VIVADO_ROOT` 和 `PYTHON_EXE`。本机配置不得提交或转发。

在 Windows 命令提示符中运行，输出目录可以自由选择，必须是新建空目录。Vivado 的 FFT 生成器对中文输出目录存在文件查找失败，部分 IP 仍受 Windows 路径长度限制；**输出目录仅用英文字符且完整路径最多 78 字节（本配方针对最长生成文件采用的保守上限，不是 Vivado 通用规格）**，可以有空格。源包解压位置支持中文和空格。入口提前检查输出路径，不更改已有工程：

```bat
project\script\rebuild_ps_3d.bat --output "..\My SoundSight Work"
```

完成后打开输出目录中的 `SoundSight_PS_3D.xpr`。RTL、初始化数据和约束已经复制进工程，GUI 修改不会直接修改仓库源码。仓库中无参数双击 `project/script/run.bat` 也进入这一最新配方，默认输出 `project/par`；已有工程时拒绝覆盖，改用上面的显式目录命令。

也可在 Vivado Tcl Console 中先关闭当前工程，然后：

```tcl
source {project/script/rebuild_ps_3d.tcl}
ss_rebuild::create {../My SoundSight Work}
```

`source` 路径相对于当前 Tcl 工作目录；应先切到解压根目录。准备完成不表示综合、实现或板测通过。由用户依次运行综合、实现、检查时序和资源，再生成 bit；导出配套 HWH/XSA 后才能更新 PYNQ 包。

## 包含的内容

- `project/script/ps_3d_sources.txt`：31 个实际 RTL 与一个 Hann 初始化文件，唯一源码在 `project/rtl`。
- `project/ip/ps_3d_fft.tcl`：从实际工程提取的两个 FFT v9.1 完整用户配置；不复用旧生成目录或 DCP。
- `project/bd/ps_3d_export.tcl`：实际 BD、PS DDR/MIO、时钟复位、AXI DMA 和连接/地址配置。BD 的历史名称 `soundsight_stm32_bd` 为保持层级而保留，当前运行架构是 Zynq PL+PS。
- 5 份 XDC：板级引脚、接口时序、垂直引脚、垂直输出时序和原来已禁用的 SPI ILA 约束。后者继续禁用，不会建立旧 SPI 调试逻辑。水平 T15、垂直 W16。
- BAT/Python/Tcl 入口及空白本机工具配置模板。完整文件表见 ZIP 的 `FILES.txt`。

控制地址 `0x40000000`、PCM 控制 `0x43c00000`、DMA `0x40400000`，HP0 DDR 窗口 1 GiB；保持实际工程配置。100 MHz 计算/AXI 与 61.44 MHz 采集/控制域不变。

不包含运行缓存、旧增量检查点、发送方 XPR、绝对路径报告、bit/HWH、PYNQ 程序或声纹模型。这是可编辑工程源交接包；SD 卡软件/位流包继续单独交付。

## 维护与验证

```bat
python -B tools/package_vivado_ps_3d.py
```

打包前逐文件检查依赖和硬编码绝对路径；ZIP 检查 CRC。重新生成的本地 XPR/日志包含接收方路径属于本机工作状态，不得倒放入源交接 ZIP。原始历史报告保留原文，不以替换路径的方式伪造。

本次运行证据由仓库 `document/evidence/portable-vivado-20261029` 单独记录；源包不携带可能包含本机路径的原始日志。历史用户时序通过不能代替接收方重建后的 STA。
