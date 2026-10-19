# V3第二、三次比较：第三次仅复位STM32

最新用户决定：三次全部保留并按[统一统计表](RUN-STATISTICS.md)分类。下文记录先前对第一次的临时采用范围；现在H01重新纳入现象分类，操作存疑备注仍保留。

2026-10-19。用户在聊天提供第三次完整串口，并明确补充：**“我只按了STM32上的reset”**。未复位FPGA、未重新加载PL/进行新的PS初始化。下方保留第三次关键原文摘录，完整输出来自本次聊天；不将摘录称为完整日志。

## 采用哪些记录

- 第二次：[RETEST-2.md](RETEST-2.md)及[完整原文](user-uart-retest-2.txt)，作为当前主要问题定位依据：同帧重读/标准BIST数值不符，有效读回SPI_FORMAT+STOP=0x41。
- 第三次：本记录，作为仅复位STM32后准备阶段检出混合故障并拒绝启动的证据。不能作为第二次数据不一致的独立重复实验，也不能据此推算故障率。
- 第一次：[原记录](BOARD-RESULT.md)及[原文](user-uart-retest.txt)保留。用户怀疑首次测试操作不正确，标记为**操作条件存疑，不作为当前主要定责依据**；不能从第二、三次推出第一次数值记录虚假或故障已经修复，不删除历史原件。

## 对照

|项目|第二次|第三次|
|---|---|---|
|STM32固件|P4_ACQUIRE_V3|P4_ACQUIRE_V3|
|板间测试前初态|未补充准确PL复位记录|明确只按STM32 reset，沿用PL状态|
|本板自检|13/0/11|13/0/11|
|ID/ABI|通过|通过|
|prepare|status0|status10，SS_DEVICE_FAULT|
|ss_start|step13成功|未调用，start_step0|
|取帧/解算|40事务/status0，但同帧与标准值检查失败|没有执行|
|FPGA故障证据|SAFETY有效读回0x41|准备阶段故障读取后缓存0x41；后续SAFETY被隔离返回12|
|跨板汇总|18通过/4失败/5跳过|14通过/3失败/5跳过|

第三次没有重现第二次的数值错误，因为没有进入取帧。第二次结束时PL存在粘滞0x41，仅复位STM32不会清除它；第三次行为与这一残留故障完全相容，不应当作新的独立故障样本。它也不能独立证明期间绝无新SPI格式事件。

准备代码先ss_disable，然后ss_acknowledge_stop读取FAULT_STATUS；只允许清除孤立STOP(0x40)，发现其他位即返回10。0x41含SPI_FORMAT(0x01)，所以按合同拒绝自动清错，进入recovery_required。第三次的本板自检/APP初始fault0只是重新初始化后的软件状态，不证明FPGA当时故障寄存器为0。后续SAFETY三读返回12是隔离连带，不能当硬件安全读回。

## 第三次关键原文摘录

```text
FIRMWARE_DIAG,P4_ACQUIRE_V3
SUMMARY,scope=BOARD_ONLY,pass=13,fail=0,skip=11,result=PASS_WITH_SKIPS,NOT_SYSTEM_ACCEPTANCE
DATA,FPGA_ID_ABI,status=0,id=0x5A5A2026,abi=0x00010000
CHECK,FPGA_ID_ABI,PASS
DATA,DIAGNOSTIC_PREPARE,status=10,only_isolated_STOP_acknowledged
CHECK,FPGA_SPI_BIST_REJECT,FAIL
CHECK,REMAINING_FPGA_TESTS,SKIP,PRIOR_BIST_FAILED
DATA,SAFETY_READ_STATUS,act=12,watchdog=12,fault=12,last_error=10,recovery=1
DATA,SAFETY,INVALID_READBACK,values_not_reported
CHECK,FPGA_MOTION_DISABLED,FAIL
CHECK,FPGA_NO_UNEXPECTED_FAULT,FAIL
SUMMARY,scope=FPGA_DIAGNOSTIC,pass=14,fail=3,skip=5,result=FAIL,NOT_SYSTEM_ACCEPTANCE
LINK_DIAG,last_error=10,recovery=1,start_result=0,start_step=0
APP,status=0,state=0,active=0,frames=0,rejected=0,queued=0,drops=0,max_step_ms=0,producer_idle=0,motion_gate=0,motion_state=0,commit_outcome=0,fault=0x00000041,first_error=0,max_frames=8,duration_ms=2000,print_every=4
```

## 下一步

A继续准备ILA诊断。独立复测前由A/现场按其工程的既定方法建立明确PL冷复位/加载与PS时钟初始化状态，之后启动STM32并确认准备检查通过，再运行一次fpga流程及对应ILA采集。不能把再次按STM32 reset当作两板都回到初态；不修改驱动以忽略/批量清除0x41。

当前无需新增STM32代码、重新编译或反复测试；保留V3，动作关闭。本次只更新结果适用范围和进度，不操作板卡、不删除历史材料。
