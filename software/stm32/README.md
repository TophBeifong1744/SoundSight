# STM32组入口

已收到探索者V3.5 / STM32F407ZGT6、Keil uVision5+DAP可下载的确认，以及v2接线和三方分工。

- 冻结合同和共享头：`../common/FROZEN_SSOT_ABI.md`、`../common/fpga_stm32_abi_frozen.h`。
- 已完成S1：`../common/s1/`，两种CPU目标共用同一份代码；不要再复制一份后各改各的。
- B原文：`board-handoff/`。
- 当前接线：`../../hardware/stm32/SPI-WIRING.txt`。

**S2 SPI驱动、会话/快照管理、STM32时钟/外设配置及Keil工程尚未收到。** 本目录不是已经能下载运行的完整STM32固件，迁移没有代替B实现这些任务。

后续收到源码后，放`src/`、`include/`、`board/`、`keil/`和`tests/`；构建输出统一放`build/`并忽略。必要启动文件、链接脚本、实际型号、库/Pack版本和配置归Git；调试器个人状态与Objects/Listings等生成物不归Git。

SPI Mode0、1MHz、40位事务和独立动作许可保持冻结规则。STM32独占主方案的ACQUIRE/RELEASE/CONSUME与动作提交。不能直接套用PS版AXI物理访问实现。
