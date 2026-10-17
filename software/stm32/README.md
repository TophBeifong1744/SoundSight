# STM32 工作区入口

2026-10-18 已接入 B 侧 S2、探索者 V3.5 板级适配和统一自检工程。主方案为 STM32F407ZGT6 + PL，保留 128 MHz / USART1 115200、SPI1 1 MHz。默认关闭动作提交。

当前完成范围及剩余模块见 [STM32模块进度表](../../document/STM32-MODULE-PROGRESS.md)。

|内容|路径|
|---|---|
|唯一冻结 ABI、S1|`../common/`、`../common/s1/`|
|S2 通用驱动|`src/fpga_link.c`、`include/fpga_link.h`|
|Keil 工程|`keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx`|
|板级实现与统一入口|`keil/soundsight_f407/User/soundsight_board.c`、`soundsight_selftest.c`|
|主机回归|`tests/run_host_tests.py`|
|生成物|`build/`（Git 忽略）|
|操作和接线|[板级自检说明](BOARD-SELFTEST-README.md)、[接线表](../../hardware/stm32/SPI-WIRING.txt)|
|原板端日志|[2026-10-17 记录](../../document/evidence/stm32-board-20261017/board-only-user-uart.log)|

在仓库根目录运行 `python software/stm32/tests/run_host_tests.py`。工具位置由环境变量、被忽略的 tools.local.env 或 PATH 提供。

已完成范围：S1 PC 4705 项、S2 PC 15980 项；原硬件 BOARD_ONLY 11 PASS / 0 FAIL / 11 SKIP。本次搬移后的编译/测试见 [迁移记录](../../document/stm32-workspace.md)。原板端输出不能替代搬移后固件上板测试；实际跨板 SPI/IRQ/快照仍未测。

同一功能只在当前工作区修改；原工程作为保留副本。公共 S1/ABI 未修改，不能在 STM32 目录另建分叉。动作写门禁继续保留，未连接 FPGA 的项目显示 SKIP。
