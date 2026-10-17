# STM32 工作区同步 — 2026-10-18

仓库 https://github.com/TophBeifong1744/SoundSight ，分支 codex/stm32-bringup，基于 9e344f4d0639369ae44f1b6ccfa89db02bdc2444。不改 main 和 FPGA RTL。

接入 S2 通用驱动、测试、SPI/GPIO/TIM2/DWT 适配、board/fpga/stream 入口及完整 Keil 源工程。保留128 MHz与禁动作策略。冻结 ABI/S1 与原验证版文本一致，仍只维护 software/common 一份。

Keil 使用项目相对路径，生成物进入 software/stm32/build，个人 DAP/窗口状态不上传。旧厂商 GBK/Windows-1252 注释转无 BOM UTF-8，原声明保留；首次编码整理遇到西文注释字节后补充处理，见 encoding-conversion.txt。main.c 已包含文件头两个非法字节的修复。

|验证|实际结果|
|---|---|
|新目录S1 C99|4705项，0失败|
|新目录S2 C99|15980项，0失败|
|主机自检模型|board/live/no_peer/dead_tick/bad_config 五场景符合预期；无禁止动作写入|
|新目录Keil AC5|0错误、0警告；Code22946 / RO1386 / RW48 / ZI9120；AXF/HEX已生成|
|新目录固件上板|未执行；原板BOARD_ONLY为11通过/0失败/11跳过|
|跨板SPI/IRQ/快照及物理时序、动作|未测；保持禁动作提交|

[本次结果](evidence/stm32-workspace-20261018/)与[迁移前板端串口](evidence/stm32-board-20261017/board-only-user-uart.log)分开保存，旧日志路径仅为来源，不构成构建依赖。

运行：仓库根目录 python software/stm32/tests/run_host_tests.py；Keil打开 software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx 并Rebuild。详见[操作说明](../software/stm32/BOARD-SELFTEST-README.md)。

本机新入口 F:/NUEC/SoundSight-stm32，可打开根目录 SoundSight-STM32.code-workspace。当前为浅克隆、稀疏检出，包含software、STM32接线、顶层说明和tools，其余目录仍在远端；按需用git sparse-checkout补齐，历史可git fetch --unshallow。

后续STM32在新工作区修改，旧F:/NUEC/stm32保留，不双向同时编辑。下一步等待匹配ABI的PL映像与接线就绪，用户运行fpga加CRLF。

未创建codex_out工程；已将本次旧ListingPath产生的两份列表移入build/keil并清除重复件。原源码、历史工程和他人输出保留。
