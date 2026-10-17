# P1 运行控制状态机

2026-10-18：独立软件完成，PC 寄存器模型验证与 ARM Compiler 5 对象编译通过。后续 P3 已接入 Keil 主循环并修正 STOP 的显式禁用步骤；未下载新固件、未做真实 FPGA 联调。详见 [P3](INTEGRATION-P3.md)；三维保留暂停。

代码：[接口](include/ss_runtime.h)、[实现](src/ss_runtime.c)、[测试](tests/test_ss_runtime.c)。复用原 S1、S2 和冻结 ABI，没有修改它们，没有新增跨板寄存器或更改 STOP 语义。

## 状态与交接

|入口／状态|行为|结果|
|---|---|---|
|init → IDLE|初始化主机上下文，不访问设备|不声称 FPGA 已停止|
|start → PROBING → STARTING|核对 ID/ABI，关闭运动许可和看门狗；等待排尾／队列空后按原 S2 启动|成功 RUNNING；BUSY 在启动总时限内等待，不清空旧队列|
|RUNNING|周期检查 fault，再读取、解算、消费一帧|有效方向或拒绝方向事件；无帧继续等待，不依赖 IRQ 新边沿|
|stop → STOPPING → DRAINING|只发送一次 STOP，显式清 enable 并保留模式；有界回读 enable=0 且 draining=0|STOPPED 且 producer_idle_observed=1；保留 READY 队列|
|FAULT|清除当前结果，保留错误和帧序历史|不自动访问设备，不自动重发消费命令|
|recover → RECOVERING|重新核对设备、撤销许可、释放实际 LOCKED 槽、读取故障|无故障才回 IDLE，既不消费也不启动；sticky fault 保留|
|resume → RESUMING|仅允许此前成功启动且未请求 STOP 的会话；回读原 enable、模式及 BIST 选择|匹配才回 RUNNING；不写 enable、不切模式、不清队列|

所有请求只排队变更状态，不做 I/O；`ss_runtime_step()` 执行有限同步工作。主循环独占整个 runtime 和 SPI link；IRQ 只能记录通知，不调用这些接口。每次 step 或请求（包括被拒绝的请求）都会使上次结果失效。只在 `fresh_result` 为真且返回帧事件的当次读取结果；需要长期日志时由调用者复制。

```c
/* bus is the existing S2 adapter; static storage avoids a large main stack. */
static ss_runtime_t runtime;
const ss_runtime_config_t config = {10U, 200U, 100U};
/* Check every API status in the actual application. */
ss_runtime_init(&runtime, &bus, &config);
ss_runtime_start(&runtime, SS_RUN_REAL);
/* Each main-loop iteration, after processing a user stop/recover request: */
event = ss_runtime_step(&runtime);
if (event == SS_RT_FRAME_VALID || event == SS_RT_FRAME_REJECTED) {
    /* Log runtime.frame/runtime.result now; this frame is already consumed. */
}
```

配置数值是软件模型的示例，不是实际采集率或响应时限的验收值。配置均须大于 0 且小于 2^31 ms；调用方提供单调、允许 uint32 回绕的时钟，不能停跳，调度间隔也须小于 2^31 ms。poll 间隔从上次操作结束计；无帧不超时，通信操作仍按 S2 时限终止。启动时限包括 PROBING 和 BUSY 等待；排尾时限从接受 STOP 请求算起，逾期不能报告已确认停止。

## 消费、停止与恢复的边界

- 成功帧为原 S2 **40 次事务**，额外提前读一次故障，共 **41 次**。1 MHz 纯线上时间 1.64 ms；原 40 次单帧合同仍为 1.60 ms。这里不包含片选间隔、调度和算法时间。无帧轮询为 3 次事务（fault、ACQUIRE、status）。
- 一个 RUNNING step 最多调用一次单寄存器读取和一次有整帧时限的 S2 解算；错误时 S2 可额外尝试一次有界 REVOKE。RESUMING 最多三个单寄存器读取，DRAINING 最多两个。STARTING、PROBING、RECOVERING 分别使用 S2 的有限操作。没有等待帧的内部无限循环；主循环 STOP 要等正在执行的 step 返回，不能抢占 SPI。
- 方向拒绝、取消和来源错误属于已完成帧的诊断结果，单次消费；总线错误、畸形字段、重复帧或设备故障进入 FAULT。运行前的 fault 读取不是原子全帧故障屏障；后续发生的源故障仍由帧字段／下次检查反映，P1 不提交动作。
- CONSUME 可能已生效但回调返回错误。此时不发布该帧结果、不自动重试；显式 recovery 读取实际槽，必要时 RELEASE，**不执行 CONSUME**。显式 resume 可继续仍启用的同一会话。设备若已经消费，结果保持丢失，不伪造补回；`frames` 计数只统计主机确认成功的帧，不等于这种情况下的设备消费次数。
- 恢复保留成功消费的单调帧号水位。不能靠反复 init 消除 stale 错误；设备重置、帧号回卷或接到另一会话需要明确的新会话处理。通信恢复不能证明物理设备从未被复位或替换。
- STOP 请求立即取消后续软件取帧，已识别设备才发送 STOP。`stop_sent=1` 只代表传输成功；回读满足条件才设 `producer_idle_observed=1`，仍不能证明实物 PWM 电平。未识别设备只停止主机，标志保持 0；隔离状态下即使 STOP 发出，也不绕过 S2 恢复门禁去声称已确认停止。
- STOP 产生的 sticky fault 不由 P1 清除；因此 STOPPED 不意味着可以立即重新启动。旧 READY 数据也不自动丢弃，故可能保持 BUSY，超时后要求检查来源／明确重建会话。失败的 STOP 不自动重发，故障恢复也不自动恢复运动或运行。
- P1 所有正常写入均来自原 S2：许可只撤销、WATCHDOG 只写 0，没有 ACTUATOR_CMD、PERMIT 或 COMMIT。解算不传舵机映射配置，`servo_cmd_valid=0`。**P1 输出已消费，P2 必须另行实现同一 LOCKED 帧内的动作管理，不能拿本输出补交动作。**

## 运行测试

在仓库根目录运行（GCC 位置沿用 tools.local.env／环境变量；AC5 路径由参数传入）：

```text
python software/stm32/tests/run_runtime_tests.py --armcc <ARMCC可执行文件绝对路径>
python software/stm32/tests/run_host_tests.py
```

不提供 `--armcc` 时明确记录 ARMCC SKIP。GCC 使用 C99、O2、严格警告视为错误；AC5 使用 Cortex-M4.fp.sp、C99、microlib、O2、strict 和警告视为错误。日志和可再生成二进制在 `software/stm32/build/runtime-p1/`；必要交付日志在 [P1 验证记录](../../document/evidence/stm32-runtime-p1-20261018/REPORT.md)。

P1 测试复用现有 literal-address 寄存器模型，实际调用 S1/S2，不是 RTL、电气 SPI 或真实板测。原批 164 组取帧故障和 140 组启停恢复故障（P3修正后启停恢复增至152组）覆盖事务生效前／后各两类返回错误；并覆盖持续 IRQ、取消、残差拒绝、来源错误、重复帧、回绕、总时限、排尾、错误身份与保留 sticky fault。原 S1/S2 和五种统一自检主机模型另跑回归。没有独立审阅者或新硬件结果的声明。

P2/P3软件已完成；P3最新P1回归27104项、0失败，模型保留STOP时的enable。下一步用户本板复测，真实跨板放在P4。当前不要求A改ABI。
