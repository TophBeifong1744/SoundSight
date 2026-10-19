# P4 第一次真实两板日志：BIST启动失败

2026-10-19；来源为用户在对话提供的完整串口文件，[原文](user-uart.txt)按原字节保存。没有AI操作板卡或重跑测试。

## 实际结果

- BOARD_ONLY：13通过、0失败、11跳过。
- FPGA_DIAGNOSTIC：14通过、3失败、5跳过；首错为DATA,START,status=10，第一组拒绝BIST尚未成功开始；不是其解算结果不符合预期。
- DATA,FPGA_ID_ABI,status=0,id=0x5A5A2026,abi=0x00010000及CHECK PASS，证明本轮身份寄存器读通信成功，不证明全部SPI写/快照/IRQ通过。
- DIAGNOSTIC_PREPARE,status=0，表明该轮显式禁用及仅孤立STOP确认路径成功返回。
- 两个S1本地BIST仍通过，674us/719us属于本地解算，不是跨板BIST耗时。

## 首错定位与连带输出

fpga_link.h中10为SS_DEVICE_FAULT，2才为SS_BUSY，6为SS_TIMEOUT。ss_start/start_inner会因SYS_CTRL禁用写回不一致、FAULT_STATUS非零、BIST_SELECT写回不一致、SYS_CTRL模式0x0A或启用0x0B读回不一致返回10。现有日志未记录具体失败操作及实际读值，不能唯一裁定FPGA、STM32或电气原因，也不能仅按提示reset_PL_if_BUSY_or_FAULT判成需复位。

ss_start失败后fail()设置recovery_required，后续ss_read_register先将输出清0，再因SS_RECOVERY_REQUIRED拒绝读总线。因此SAFETY行act=0/watchdog=0/fault=0是此失败路径的无效输出，不能当成真实安全寄存器读回。两项安全FAIL属隔离后的连带结果，不是已证明出现两项新的硬件故障。

APP,status=0/first_error=0是application运行状态，不是独立自检link.last_error；末尾fault是缓存，不能据此抹掉BIST首错。此日志的link.faults缓存仍0，使启动写回不一致成为优先排查项，但仍需逐步骤原始值确认。

## 下一步

保留现有接线及首错记录，不运行stream、不启用动作、不先批量清故障或反复复位。下一有界诊断应在STM32启动路径记录失败步骤、寄存器地址、期望/实读值及SPI返回值；安全读回同时标明返回码/无效，避免零值误导。优先检查REG_SYS_CTRL 0x04的0x08→0x0A→0x0B写回，以及REG_BIST_SELECT 0x2C和REG_FAULT_STATUS 0x64。

A侧可据准确加载映像核对同一控制寄存器/SPI写提交路径；本轮仅只读核对main b486b567对应RTL，没有修改RTL或要求重新生成bit。需要进一步寄存器现场证据后再决定修哪一端。三维超限构建仍暂停。

本批仅保存证据及静态源码解释，没有产品修改、构建或硬件操作；用户Keil uvprojx改动保留。
