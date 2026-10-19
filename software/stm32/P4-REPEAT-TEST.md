# P4 统一重复测试操作

2026-10-19。目标是统计故障首次出现的阶段，保留每次记录，取得可对照的串口/ILA证据。当前STM32固定使用P4_ACQUIRE_V3（产品提交e6f1a2d），动作关闭。无需修改或重建STM32固件。

## 当前采用规则

- 既有三次全部保留为H01/H02/H03。H01用户曾怀疑操作不正确，保留这一备注并纳入异常现象分类，不删除、不将它标为已证实无效。
- H01/H02的准确PL复位初态和映像身份未完整记录，不追认成标准独立试次。H03确认只复位STM32，为保留PL状态的后续观察。
- 新做独立测试批G01，先做5次（R01～R05，计划数量，不代表已执行）。使用同一STM32固件、同一FPGA映像/PS启动方式、接线、SPI1MHz及串口设置。
- 新增ILA、更换bit、改代码、改接线或速率时新开G02等批号，不能混在同一批里算。即使功能逻辑不变，插入ILA也可能改变布局和时序。
- 保留PL状态的测试单列C类并注明依赖的前次编号，不与明确重新初始化后的R类合计故障率。本轮先完成R类，暂不主动增加C类；已有H03可作为残留状态样本。

## 每次R类测试的固定步骤（由现场人员执行）

1. **先记编号并开启日志。** 第一轮写G01-R01，之后顺序递增。记录日期时间、FPGA bit文件名/来源版本及是否含ILA；用同一串口设置115200/8N1、CRLF。不必反复刷写STM32。
2. **先初始化FPGA，再复位STM32。** 由A按当前交付确认的同一流程重新加载/冷初始化PL，并完成PS时钟/复位初始化。必须使SPI、寄存器故障和快照槽回到冷复位初态；仅重跑PS应用、仅PS复位、仅按STM32 reset都不能自行视为已满足。A确认一次准确菜单/脚本/步骤后，每轮照做并在试次信息中记录；当前尚未取得A新映像的精确操作清单，不臆造FPGA按键作用。可以沿用A确认有效的Vitis加载方案，不要求新增重建工程。
3. **按STM32 reset一次。** 等待BOOT及BOARD_ONLY SUMMARY完整输出。确认标记P4_ACQUIRE_V3、APP_PROFILE=0、motion=DISABLED，本板预期13通过/0失败/11跳过。若不符合，记录本板/版本问题，此轮不继续fpga，也不能悄悄丢弃该次。
4. **串口单次发送`status`，带CRLF。** 等输出结束。这个status主要为软件状态，不能用APP fault0证明FPGA已经清零。
5. **如有ILA，先由A布置触发并进入等待采集。** 保留事件前史，记bit/LTX和触发条件；无ILA则记NO_ILA。随后单次发送`fpga`，带CRLF，等待FPGA_DIAGNOSTIC SUMMARY及COMMANDS结束。不要开启串口循环发送。
6. **单次发送`status`，带CRLF。** 保存本轮全文和ILA结果，然后结束本轮。文件名建议`G01-R01-uart.txt`，波形用同编号。命令回显/空行可保留，不要只截PASS/FAIL段。
7. **不在同一轮清错、recover、ackstop、discard或再次fpga。** 不发送stream/motion，不通过重试掩盖首错。若误操作，记录内容和时点，保留原日志，标PROCEDURE_DEVIATION；下一轮重新从第1步开始。若需调查恢复链，另列明确子试验，不混入本批。

### 发回聊天的简短格式

```text
试次：G01-R01
时间：2026-10-19 HH:MM（香港时间）
FPGA映像：文件名/来源版本；ILA：有/无
FPGA已按A确认流程重新加载/冷初始化并完成PS初始化：是/否/不确定
STM32：P4_ACQUIRE_V3；初始化PL后按了STM32 reset
操作：status → fpga（一次）→ status
偏离步骤：无/具体说明
随后粘贴完整串口，或提供原日志文件路径；ILA资料用同编号。
```

## 我们如何统计

使用[同一结果表](../../document/evidence/stm32-p4-acquire-diag-20261019/RUN-STATISTICS.md)和[CSV](../../document/evidence/stm32-p4-acquire-diag-20261019/run-statistics.csv)。先记录**第一个失败位置**，再列后续伴随现象；一轮的多个FAIL不算多次独立故障。

分类：BOARD/ID_ABI → PREPARE → START → ACQUIRE_FORMAT → RELEASE/REACQUIRE_CONSISTENCY → BIST_VALUE → IRQ/FINAL_FAULT → TIMEOUT_RECOVERY → PASS_WITH_SKIPS。若现有日志无法细分则写UNKNOWN，不用后续故障码倒推出首错时点。

- 每项同时区分PASS、FAIL、SKIP、未执行。第二BIST/恢复未执行不能记通过。
- 只对同一配置、明确执行冷初始化流程的R类记录计算“本批测试失败次数/试次数”；准备阶段失败也计入，只要初始化流程确实执行，不能因测试未启动就剔除。
- 操作/初态未知及C类单独列，不能稀释或抬高R类比例。新增5次只用于定位和粗略重复性观察，不代表可靠性验收或实际连续流的故障概率。
- PASS_WITH_SKIPS只代表已执行诊断检查通过，物理波形、真实流、运动等SKIP继续保留。

## A与B分工

A确认准确PL映像及冷初始化步骤；如加ILA，安排format_error前史、commit/address/write_data、pair_select和读回链路采集。B保持V3、读取用户每轮输出并更新同一统计表，按证据解释故障；现场人员执行加载/复位/串口操作。当前没有AI自动操作板卡或复位。
