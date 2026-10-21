# PL+PS 音量版工程复现交接

这次把用户SoundSight_PS_Volume的最新实际导出接回原有PS入口。继续使用`project/script/run.bat prepare ps`，不再使用仅配置通用PS时钟的旧简化配方。STM32目标的BD和板级配置保持独立。

## 正式文件在哪里

| 内容 | 路径 |
|---|---|
| 唯一公共RTL及Hann初始化数据 | project/rtl |
| 实际音量版BD连线、复位、AXI地址和IP参数 | project/bd/ps.tcl |
| 本次PS7 DDR/MIO与时钟配置 | project/ip/ps7_ps.tcl |
| 两个官方FFT的创建配方 | project/ip/create_fft_ip.tcl |
| 实际Global模式及综合/实现运行选项 | project/script/ps_settings.tcl |
| 实际PS约束 | project/sdc/ps |
| 用户实际实现报告 | project/reports/ps |
| 完整复现依赖清单 | document/build/ps-handoff-files.txt |
| 原始导出和静态接回结果 | document/evidence/ps-volume-handoff |

实际外部BD沿用旧名字soundsight_stm32_bd，但内容是PL+PS。正式配方统一生成soundsight_ps_bd和对应wrapper；内部实例名称、端口、连线及约束定位保留，寄存器地址固定0x40000000/4KB。两个模块LEVEL_ENABLE=1、ACTUATOR_BOUND=0。无需额外SPI、ILA或新物理引脚。

## 接收方重建

安装Vivado 2025.2及Zynq-7000器件支持、Python3。取得仓库，或解压`release/output/soundsight_ps_volume_handoff.zip`，进入其中SoundSight目录。建议使用短工作路径；工具位置由PATH或本机`tools.local.env`配置，参考空模板，不复制发送方安装路径。

```powershell
.\project\script\run.bat --check-tools
.\project\script\run.bat prepare ps
.\project\script\run.bat outputs ps
.\project\script\run.bat open ps
```

生成目录为`variants/pl_ps/project/par`。已有工程时不会覆盖，应直接open；不要为重建删除在途成果。prepare和outputs只准备工程/官方IP，不自动综合、实现、生成bit或下载。物理构建由使用者在GUI点击。运行设置来源于本次用户导出，不能只拿一个BAT而不带清单中的依赖。

当前PS7配置来自用户这块板，DDR为MT41J256M16 RE-125、参考时钟33.333333MHz。其他板卡必须按实际板级资料调整，不能把此配方当通用DDR预设。旧PYNQ镜像的加载时钟修正与SD软件操作见[pynq-volume-sd.md](pynq-volume-sd.md)。

## 两个包用途不同

- `soundsight_ps_volume_handoff.zip`：给电脑上的Vivado重建使用，包含完整PS源/约束/配方/说明/报告依赖。
- `soundsight_pynq_volume.zip`：给SD卡搬运使用，包含本次实际bit/HWH及PS软件；无需在板上安装Vivado。软件内的C库由ARM端编译。

原始export ZIP仅作证据，其中可能存在历史本机路径。正式配方和源依赖使用项目相对路径，不依赖F盘工程，也不依赖旧仓库。BD内部XCI不重复作为产品维护；外部导出保存的小型原件用于核对配置。

## 验证边界

用户实际实现报告为WNS +0.265ns、WHS +0.021ns，setup/hold失败端点0；实际bit/HWH与同次XSA字节一致。音量RTL沿用既有6项XSim定向/回归结果，软件解压包15项门限与19项RAM测试通过。该用户工程的通过不能自动视为本次归一化配方重新综合通过。

本次接回以导出为基准核对Tcl配置/连线事件、FFT参数、运行选项、全部源/约束与相对路径依赖；没有重新运行Vivado重建、综合、实现或板测。新音量版ARM与实板仍待用户执行，多帧统计和3°死区未接入在线路径，舵机仍禁用。
