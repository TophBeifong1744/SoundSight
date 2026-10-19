# P4 诊断固件真实回测：双BIST通过，SPI格式故障阻断收尾

2026-10-19；用户回传[完整串口原文](user-uart-retest.txt)，启动标记P4_START_V1。文本按原字节保存，非AI操作板卡采集。

## 结论与数值

BOARD_ONLY为13通过/0失败/11跳过。FPGA_DIAGNOSTIC为26通过/3失败/4跳过，尚未完成P4。

|项目|本次实测|
|---|---|
|身份|ID=0x5A5A2026，ABI=0x00010000，PASS|
|两次BIST启动|均step13，REG_SYS_CTRL=0x04，期望/实际0x0B，bus_status=0/result=0/recovery=0|
|拒绝BIST|frame1，40事务/status0，ux46831/uy-171729，residual590912626，valid0/reason3，PASS|
|通过BIST|frame2，40事务/status0，ux749295/uy0，residual0，valid1/reason0，PASS|
|RELEASE/重读/CONSUME|两组同帧重读和40软件事务检查均PASS|
|IRQ|两组锁定时高、消费后低、EXTI边沿检查均PASS|
|取帧+解算耗时|拒绝2926us（374481 cycles），通过2971us（380245 cycles）；不含此前启动/释放等整个流程，不是1.6ms纯线上预算或最坏时延|
|新的首错|第三次DIAGNOSTIC_PREPARE,status=10，FPGA_TIMEOUT_PREPARE FAIL|
|末尾缓存|link.last_error10/recovery1，fault=0x00000041|

## 首错解释

冻结ABI：0x01=FAULT_SPI_FORMAT（事务格式），0x40=FAULT_CANCEL_STOP（取消/STOP）；0x41为两者并存。

准备流程先ss_disable，再ss_acknowledge_stop。该次打印DIAGNOSTIC_PREPARE说明ss_disable已返回成功，随后ss_acknowledge_stop返回SS_DEVICE_FAULT。其故障读取把FAULT_STATUS保存到link.faults；当前0x41包含非STOP错误，按原策略拒绝仅STOP确认，保留混合错误并进入隔离是正确行为。日志尚不能定位是哪一个先前事务触发bit0，也不能唯一确定波形/接线、主机发送、从机边沿判定或映像版本哪项是根因。

live_timeout在prepare失败后立即返回：未执行软件超时注入、显式恢复和恢复后BIST。不能把本次称为“超时恢复失败”，也不能称超时恢复已测。

安全读取三个返回码均12（SS_RECOVERY_REQUIRED），INVALID_READBACK正确阻止伪零值；末尾APP的fault0x41是较早成功读取的缓存，不是最终安全读回。这两项安全FAIL是隔离连带结果。本次原start_trace结果0来自前两次成功启动，不涵盖失败的STOP准备。

上次BIST启动失败这次未复现；没有修改相关功能判断，只增加记录/返回后打印与少量CPU开销，不能把前次问题标已修复。现象变化提示需要抓实际事务，不能凭一次通过认定稳定。

## 下一步给FPGA/STM32协作

保持动作关闭，不运行stream，不批量清故障或反复复位抹掉记录。优先用逻辑分析仪/示波器捕获一次完整fpga测试的CS/SCK/MOSI/MISO（可同时IRQ），集中看第二组BIST消费后到第三次准备阶段。核对Mode0/约1MHz、每个CS低窗40个上升沿、CS建立保持、SCK高低宽度及毛刺/多余边沿；软件40事务计数不证明每个物理CS窗口40 clocks。

A侧核对准确映像的ss_spi_mode0.sv格式错误触发条件：位数不等40、CS释放时SCK高/同步上升沿、边沿/片选间隔过短或malformed锁存，并与所用61.44MHz处理域对应。静态条件检查不等于根因已确认；不要直接放宽门槛。

若现场暂无仪器，下一小批可设计有界RAM事务记录/首个故障位置采样以缩小范围，并明确额外读事务对时序的影响；不能因此宣布物理波形通过。本次只分析和归档，没有自动修改代码、重构建、清故障或操作板卡；三维构建仍暂停。
