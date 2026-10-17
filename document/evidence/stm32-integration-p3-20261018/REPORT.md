# P3 软件接合验证记录

日期：2026-10-18。父提交 `d5899f4b2136ed84c2308a326261855312eb73f3`；任务分支 `codex/stm32-integration-p3`。状态：软件与完整固件构建完成，新本板/跨板验证待用户执行。

## 改了什么

新增 ss_app，将 P1/P2 接入统一主循环、共用一个 S2 上下文；集中有限运行参数及日志，stream 可响应 status/stop。按父提交真实 RTL 的 STOP 锁存行为，显式禁用 enable 再等待排尾；独立 ackstop 仅确认孤立 STOP，拒绝混合错误。双 BIST 间及结束显式停止确认。默认编译、运行配置和物理适配三层动作门禁保持关闭。ABI、S1、FPGA RTL、128 MHz 时钟与板级驱动未改。

核心顺序：

```c
/* ss_runtime_step: STOPPING */
s = ss_stop(&r->link);
/* check transfer and quarantine */
s = ss_disable(&r->link); /* preserve mode, explicitly clear enable */
/* DRAINING then verifies enable=0 and draining=0 */

/* ss_app_step: only one acquisition owner */
if (runtime_running && motion_armed) ss_motion_poll(...);
else ss_runtime_step(...);
```

上述省略片段只说明顺序，完整错误处理在正式源码中。

## 实际运行

|输入/范围|预期|实际结果|
|---|---|---|
|S1 原二维向量与边界|数值/资格不变|4705项，0失败|
|S2 原协议模型|40次读帧与故障隔离不变|15980项，0失败|
|P1 严格 STOP 模型|STOP保留enable，软件显式禁用；排尾/恢复保留|27104项，0失败；164组取帧+152组生命周期故障|
|P2 默认/测试开启|默认无动作；同锁帧有限提交且不重放|43/74240项，0失败；340组故障组合|
|P3 默认/测试开启|配置过滤、单一所有者、有限停止/恢复|2900/3113项，0失败|
|P3 8帧输入，其中1帧残差拒绝|消费8次，拒绝1次，无动作|相符；STOP故障64，ackstop后0，下一轮frame9|
|STOP确认7事务各生效前后IO/超时|出错隔离，不产生动作|28组通过；排尾时BUSY，混合故障拒绝|
|测试专用P2接合|同一帧只取/消费一次|59事务含统计读；消费1次，P1取帧0次|
|实际串口分发函数的主机模型|参数/长命令拒绝、运行中自检BUSY、停止可响应|185项，0失败；两帧单次消费，禁动作|
|AC5 两配置对象|S2/P1/P2/app C99编译通过|均通过；测试开启配置仅对象，未做开启动作的固件|
|Keil AC5完整默认固件|链接且生成HEX|UV4退出0，0错误、0警告|

主机自检场景（均不是实板）：

|场景|PASS/FAIL/SKIP|模型事务数|解释|
|---|---|---|---|
|board|13/0/11|0|新增应用初始化和编译门禁两检查|
|live|32/0/4|302|模型有匹配FPGA，含两BIST切换及最终停止确认|
|no_peer|13/1/10|1|身份失败如实FAIL，非通过|
|dead_tick|12/1/11|0|计时失败阻断FPGA操作|
|bad_config|12/1/11|0|GPIO配置失败阻断FPGA操作|

Keil真实工具输出：Code=29218、RO-data=1994、RW-data=48、ZI-data=10080字节。默认固件 AXF/HEX 在 `software/stm32/build/keil/`。栈配置8 KiB；链接器静态最大深度1192字节加未知循环/间接调用，不能据此宣称实际栈高水位已测。

## 命令

仓库根目录；工具路径由本机配置或参数提供，原始日志保留实际执行命令：

```text
python software/stm32/tests/run_host_tests.py
python software/stm32/tests/run_runtime_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_motion_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_app_tests.py --armcc <armcc.exe>
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -o <日志绝对路径>
```

GCC严格C99/O2/警告视为错误；AC5 5.06 update7、C99、Cortex-M4.fp.sp、microlib。对象测试开启配置不进入实际板端。Keil重建没有下载参数。

## 失败与修正

1. 首轮GCC对两处同一行if后语句报告 misleading-indentation；拆行修复。原日志 `compile-selftest-first-failure.log`。
2. 新增本板两检查后，旧主机runner仍期望11项，出现预期计数不匹配；更新为13并回归。是测试期望更新，不把旧板端11项改成13项实测。
3. 新增fault状态打印使用 `application.runtime.link` 时撞到本文件 `link` 宏；GCC/AC5均拒绝编译，改为已有宏引用。原日志 `host-diagnostic-field-failure.log`、`keil-diagnostic-field-failure.log`。
4. 为对齐物理适配补充测试WATCHDOG门禁时，地址误写0x1C（FEATURE_SELECT），live测试拒绝取帧；按冻结头修为0x60，保留 `host-watchdog-model-address-failure.log`，最终五场景及命令测试通过。
5. 文档更新脚本第一次以Windows默认GBK读UTF-8失败，后续显式UTF-8修正。未影响产品代码或验证预期。

## 剩余与交付边界

- 新固件未下载、未实板运行。原用户BOARD_ONLY仅旧固件11/0/11；新固件13/0/11仍是预期。
- 主机寄存器模型不是RTL或电气SPI测试；严格STOP模型用于防止旧模型误清enable。A最新实际映像仍需P4核对。
- 新增诊断状态中的fault是最近驱动观察缓存，status不额外访问SPI；首错误保留历史，不能把缓存0认定当前硬件无故障。
- 无ACK/采集时间戳、机械参数未标定、真实波形/IRQ/连续帧/声学/动作均未测。三维暂停。
- 正式源码在software，说明/必要日志在document/evidence。本批未创建codex_out副本或ZIP，无临时副本需删除；可再生成构建产物保留在既定build目录，未提交二进制。
- 下一步：用户下载后返回BOARD_ONLY日志；A映像和接线就绪后按现有入口做P4。完成本P3子任务后暂停。
