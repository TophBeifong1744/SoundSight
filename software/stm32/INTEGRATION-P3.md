# P3 参数、诊断与固件接合

2026-10-18：软件接合、PC 模型与 AC5 完整固件构建完成；新固件未下载，真实 FPGA 联调未测。128 MHz 时钟、S1、冻结 ABI、板级物理写门禁不变，三维不接入。

## 本批改动

- `include/ss_app.h` / `src/ss_app.c` 集中运行参数、诊断统计和 P1/P2 调度，共用一个 S2 上下文。初始化只做一次，恢复和重复自检保留帧序及提交历史。
- 非动作路径由 P1 取帧；P2 ARMED 时只由 P2 取帧，不再经过 P1 诊断消费。生产配置 `allow_submission=0`，编译默认 `SS_ENABLE_MOTION_WRITES=0`，板级拦截继续保留。
- 按父提交 RTL 的实际语义修正停止：STOP 置内部锁存而不清 enable，因此 P1 发送 STOP 后另行关闭 enable，保留模式位，再有界检查排尾。没有修改 RTL 或 ABI。
- 新 `ss_acknowledge_stop` 仅在 enable=0、draining=0、ACT_CTRL=0、WATCHDOG=0 且故障为 0 或单独 `FAULT_CANCEL_STOP=64` 时允许确认 STOP；其他或混合错误不清除。W1C 后重新读回，通信错误隔离。
- `fpga` 自检在两组 BIST 之间及结束时显式禁用并确认孤立 STOP，避免上一次 BIST 的 STOP 粘滞状态影响下一组。失败仍报告 FAIL，不能通过批量清故障掩盖。
- Keil 工程已加入 P1/P2/app 三个源文件，用户不需要逐行追加代码。

## 操作

打开 [Keil 工程](keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx)，使用 AC5 Rebuild，按原 DAP 配置由用户下载。接线和电平条件见 [统一自检说明](BOARD-SELFTEST-README.md)。本批未改变接线。

串口 115200、8N1，每条命令以 CRLF 结束：

|命令|行为|
|---|---|
|`board` 或复位启动|本板自检，不访问物理 SPI；预期 13 PASS / 0 FAIL / 11 SKIP|
|`fpga`|用户明确请求跨板诊断；ID/ABI、双 BIST、RELEASE/CONSUME、IRQ、软件超时恢复及最终禁用。未接 FPGA 不应运行；请求后身份不符会 FAIL|
|`config 8 2000 4`|最多 8 帧，运行期限 2000 ms，每 4 帧输出一次，首帧总输出；只允许空闲时改参数|
|`stream`|主循环分步运行真实模式，达到帧数或时限后请求 STOP；可在运行时处理 status/stop|
|`status`|输出状态、帧数、拒绝数、queued 观察次数、设备累计 DROP_COUNT、最大 step 毫秒、停止观察、fault、首错误、配置和动作门禁|
|`stop`|停止后续取帧并请求停止/禁用/排尾；不会清故障或消费 READY 队列|
|`ackstop`|空闲后显式恢复传输、禁用、只确认孤立 STOP，再恢复主机状态；不会启动或消费|
|`recover`|空闲时重新识别、撤销许可、释放 LOCKED，恢复软件；保留粘滞故障，不自动重启|
|`discard`|空闲、未 ARMED 时，显式诊断读取并消费一帧，输出帧号，不提交动作；隔离状态先 recover。此命令会丢弃该帧用于后续动作的机会|
|`motion`|保留诊断入口，本固件拒绝动作许可，不会驱动舵机|

参数只接受三个十进制非负整数字段：帧数 1..4096、期限 1..60000 ms、日志间隔 1..4096。符号、溢出、多余字段和长命令拒绝。运行中重复 `board/fpga`、配置或恢复返回 BUSY，避免多个路径争用锁帧。

正常一轮后先看 `STREAM,END` 和 `status`，再 `ackstop`。若仍有 READY 帧，明确决定是否用 `discard` 消费；不自动清队列。然后才 `stream` 开下一轮。其他故障需按 fault 排查；`ackstop` 不能清除混合错误，也不会伪装重新初始化来绕过历史。

## 输出含义与预算

- `DIAGNOSTIC_COMPLETE`：取得配置帧数并结束；可包含方向拒绝帧，不表示声学或系统验收通过。
- `SKIP_NO_FRAMES`：期限内没有帧；`INCOMPLETE`：期限内帧数不足；`STOPPED`：用户请求停止；`FAIL`：运行错误。均保留 `NOT_SYSTEM_ACCEPTANCE`。
- 新 BOARD_ONLY 的 13/0/11 是 PC 验证的预期。原用户实板记录仍是旧固件 11/0/11，不能替代本固件重测。
- P1 有效帧 41 次事务，本应用额外读 DROP_COUNT，共 42 次（1 MHz 纯线上 1.68 ms）；测试专用 P2 动作路径 58+1=59 次。原 S2 40 次完整读帧合同不变。
- 配置期限触发停止，之后仍需有限排尾时间；不是精确硬实时截止。`step_us` 包括当次取帧/解算/状态读取，不包含随后的串口打印；`max_step_ms` 分辨率为 HAL 毫秒。串口仍为阻塞输出，STOP 要等当前有限操作和打印返回，不能抢占 SPI。
- status 的 fault 是最近驱动观察缓存，首错误保留历史；该命令不额外访问 SPI，缓存 0 不证明当前设备无故障。
- queued 是“读到 QUEUED 位的成功帧次数”，不是唯一积压帧总数；drops 是设备累计值，不是本轮差值。帧统计是主机确认成功的数量，可能不含不确定 CONSUME 的硬件效果。
- 无动作接受 ACK、无采集时间戳的接口限制保留；不得把传输成功等同动作接受或实物运动。默认动作始终关闭，示例舵机映射/看门狗不是现场标定。
- 链接器给出的栈深有间接调用未知部分；8 KiB 栈是配置值，未测实际高水位。

## 可复现验证

仓库根目录执行，编译器路径由本机配置/参数指定：

```text
python software/stm32/tests/run_host_tests.py
python software/stm32/tests/run_runtime_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_motion_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_app_tests.py --armcc <armcc.exe>
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -o <构建日志绝对路径>
```

[本批结果和失败记录](../../document/evidence/stm32-integration-p3-20261018/REPORT.md)。下一步先由用户下载本固件、返回 BOARD_ONLY 日志；匹配 PL 映像及接线就绪后进入 P4。这里不自动操作板卡、不开始 P4/P5 或恢复三维。
