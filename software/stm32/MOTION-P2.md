# P2 水平动作命令管理

2026-10-18：独立 C99 软件和寄存器模型验证完成，ARM Compiler 5 两种配置的对象编译通过。尚未接入 Keil 主循环、下载或进行物理运动。P3 再接合运行状态机和原 board/fpga/stream；P4/P5 取得跨板及机械结果。

入口：[ss_motion.h](include/ss_motion.h)、[ss_motion.c](src/ss_motion.c)、[模型测试](tests/test_ss_motion.c)。S2 新增私有的同一 deadline 组合入口和受限动作写入，原公共 API 保持；冻结 ABI、S1、P1 源码、FPGA RTL 和板级写门禁均未改。

## 唯一所有者与动作顺序

`ss_motion_t` 引用已初始化的 `ss_link_t`。使用时必须由一个主循环独占；不能同时调用 P1 的 `ss_runtime_step` 或 S2 的 `ss_poll_solve`。后两者会消费诊断帧，不能将它们的结果转交 P2 补做动作。

初始化只配置软件，不声明硬件已经撤销许可。设备先经过 S2 probe/start REAL；P2 冷启动为 DISARMED，必须显式 arm，recover 后也不会自动 arm。启动、模式改变仍属于 P1/S2；P2 不写 SYS_CTRL，也不清除 sticky fault。

|入口|执行顺序／状态|
|---|---|
|init|验证时限、看门狗非零和显式舵机映射配置；不访问总线|
|arm|核对真实模式、fault、profile、执行器绑定、无gap/排尾；REVOKE及读回；WATCHDOG=0及读回；写入并读回指定watchdog；单独请求PERMIT及读回；再查fault。成功ARMED|
|poll|查mode/fault/permit；ACQUIRE后完整读取六对；S1带映射解算；检查同锁帧、设备条件、watchdog；写水平shadow并读回；再次查同锁帧/fault/permit；COMMIT；查fault/permit；最后CONSUME|
|无帧|返回SS_NO_FRAME；不重配watchdog、不续期、不重新申请许可|
|方向／映射拒绝或取消/BIST诊断帧|REVOKE、WATCHDOG=0并核实，然后消费一次；返回拒绝诊断，转DISARMED|
|disarm|撤销许可、watchdog归0并读回，转DISARMED；已有隔离状态需要recover|
|stop|立即关闭软件后续动作入口，发送一次STOP；重复调用不自动重发。传输完成不代表排尾或PWM实物已停止|
|故障|输出清零、FAULT；S2最多尝试一次有界REVOKE，不重复清理；原错误和提交状态可读|
|recover|调用S2重新识别/撤销/释放实际锁槽；不消费、不提交、不启动、不清fault。无fault才回DISARMED；保留提交帧号防重复记录|

`COMMIT=8` 单独写，PERMIT=1先发并确认；不将二者合在一次写入。原基线RTL中COMMIT不会清除既有许可。WATCHDOG使用61.44MHz处理域周期数，不是HAL毫秒；只在无许可时配置，仅硬件实际接受的新动作续期。软件不以空轮询或重复arm充当心跳。

有效路径共 **58事务**，COMMIT在第55次，CONSUME在第58次。1MHz纯线上2.32ms，另加CS间隔、HAL、算法和调度时间。原40事务完整帧合同保持；动作相关检查和写入是额外开销。arm为12事务，disarm为4事务，无帧轮询5事务；模型拒绝路径47事务。一次poll的所有读/解算/提交/消费共享S2 operation_timeout，不逐阶段重新开始计时；失败另有一次有界撤销。

## 三层门禁

1. **编译门禁默认关闭**：`SS_ENABLE_MOTION_WRITES=0`。默认构建会拒绝shadow、非零watchdog、permit和commit；STOP/REVOKE仍可用。测试脚本只对PC模型单独编译一个`=1`的可执行文件。
2. **运行配置必须显式允许**：`allow_submission=1`，再显式调用arm；配置本身不执行动作。机械映射、watchdog、最大持锁时间均由调用方提供，不能将模型示例当作实物标定。
3. **现有板级物理写门禁保持**：`soundsight_board.c`仍拦截动作和非零watchdog写入；本次没有链接P2到现有固件，也没有解除该门禁。未来需要真实动作时另行按用户授权和现场参数接合。

私有写入口只接受水平有效shadow、单独PERMIT/COMMIT、撤销/STOP及watchdog；拒绝垂直轴、组合PERMIT+COMMIT和其他地址。不提供通用寄存器写接口来绕过限制。配置与context字段只读，不能在ARMED时由调用者修改或重新init绕过帧序记录。

## 新鲜度、提交不确定性与恢复

- 软件保留成功消费的S2帧序水位；COMMIT尝试前另记录`last_attempted_frame`，即使该写返回错误、实际上未生效，也不对同一帧重试。这条保守记录在recover、disarm、STOP及再次arm后保留。
- 若COMMIT可能已生效但CONSUME未完成，recover可能把锁槽RELEASE回READY。P2再次看到相同或更旧帧会报SS_STALE_FRAME，保持证据，不偷偷消费或重新提交。需要调用方明确选择诊断读取/消费该帧（先恢复并保持无动作），或经明确设备复位开始新会话；P3接合此恢复交互，不能仅memset绕过。
- `max_frame_hold_ms`从本次poll开始计，COMMIT前预留完整单次传输超时。它仅约束MCU持帧时间。冻结ABI没有采集时间戳，无法证明队列中READY帧的真实年龄；不将此检查称为“真实声源时效已通过”。
- 冻结ABI没有动作接受序号／ACK。`SS_OK + SS_MOTION_SUBMITTED_UNCONFIRMED`只表示COMMIT传输成功、后续fault/permit检查符合预期并已消费；**不证明FPGA接受了动作，更不证明舵机移动**。测试专门让模型静默忽略COMMIT，驱动仍只报告UNCONFIRMED，没有伪造接受回执。
- `commit_attempted`、`commit_transfer_completed`、`consume_completed`和report_frame/target用于解释异常；出错后输出结构清零，不能作为新的有效目标。frame/result中的servo_cmd_valid是S1数学资格，不是执行器确认。模型内部accepted只用于核对测试，不是新增线协议字段。
- 软件检查与COMMIT之间存在总线时间间隔，最后一刻的许可丢失、故障或锁帧资格依赖PL硬件保护。当前配置不能检测所有设备复位/更换，也不能替代实际PWM波形测量。

## PC与ARM验证

```text
python software/stm32/tests/run_motion_tests.py --armcc <ARM Compiler 5 armcc.exe绝对路径>
python software/stm32/tests/run_runtime_tests.py --armcc <ARM Compiler 5 armcc.exe绝对路径>
python software/stm32/tests/run_host_tests.py
```

测试脚本分别编译默认关闭和PC模型开启配置，使用严格C99/警告视为错误。AC5对S2/P2两配置做对象编译，未链接固件。源码参考是本任务父提交`139a8da`中的`ss_actuator_control.sv`、`ss_control_regs.sv`；本轮仅只读这些RTL，没有运行RTL仿真，也不声称验证了A最新映像。

结果和首错：[正式记录](../../document/evidence/stm32-motion-p2-20261018/REPORT.md)。默认关闭配置43项、模型开启配置74240项，均0失败；340组故障组合另外列示。这些是寄存器模型结果，不是硬件验收。

## P3必须处理的接合项

- P1和P2共用同一link，取帧所有权只能有一个；diagnostic与motion模式明确选择。现有板级门禁默认保留。
- **STOP回读差异已静态发现**：当前基线`ss_control_regs.sv`在STOP时置`stop_latched`，未直接清`sys_ctrl[0]`。P1现在等待`SYS_CTRL.enable=0`才确认生产者停止，其旧模型则在STOP时清enable，因此主机回归通过不能覆盖此差异。P3需按真实RTL调整停止确认/显式禁用步骤及模型，或与A对齐，不能直接声称当前P1已可跨板确认STOP。P2本身只报告STOP传输结果。
- 实物机械上下限、零点/方向、PL ACTUATOR_BOUND/时钟参数、watchdog预算和持锁时限需按当前映像/机构绑定；示例90°偏置及100ms watchdog没有被当作现场参数接受。
- 若要求证明动作接收或真实采集年龄，需要A/B共同讨论可观察接口，不能由STM32自行改变冻结ABI；本批保留UNCONFIRMED和未知年龄边界。
