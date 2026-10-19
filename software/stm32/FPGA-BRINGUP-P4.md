# P4 两板基础联调：先运行无动作双 BIST

2026-10-19最新实板：[V2回测](../../document/evidence/stm32-p4-tim2-guard-20261019/BOARD-RESULT.md)20通过/3失败/5跳过。新版已下载，A修改尚未加载；第一组BIST通过，第二组启动成功但取帧status8。暂缓重复尝试及stream，下一定位取帧首错，以下保留原修正/回测说明。

2026-10-19。最新待回测固件为`P4_TIM2_GUARD_V2`，已修正STM32最小等待并完成二维Template构建；下载及回测步骤见[本批报告](../../document/evidence/stm32-p4-tim2-guard-20261019/REPORT.md)。不需新增Keil源文件，但必须下载新AXF/HEX才应用修正。先与A确认FPGA候选及复测起始状态，旧粘滞故障不会因下载STM32而消失。

上一次[P4_START_V1实板回测](../../document/evidence/stm32-p4-start-diag-20261019/BOARD-RESULT.md)为26通过/3失败/4跳过；双BIST、40事务、同帧重读、IRQ通过，第三次准备被fault=0x41阻断，超时注入/恢复未执行。本次软件测试不关闭此板端问题；下文保留原接线/首轮步骤，后续先按本批报告回测，不进入stream或动作。三维超限构建仍暂停。

## 当前双方基线

- B：P3用户串口13 PASS/0 FAIL/11 SKIP；二维APP_PROFILE=0、动作门禁关闭。[记录](../../document/evidence/stm32-p3-board-ready-20261018/REPORT.md)。
- A：main `24f063a54efcfebd27e8f1281f870d4da77eb36a`，PR [#6](https://github.com/TophBeifong1744/SoundSight/pull/6)/[#7](https://github.com/TophBeifong1744/SoundSight/pull/7)已合入。STM32主方案实际配置/报告已接回，器件xc7z020clg400-2，顶层soundsight_stm32_bd_wrapper。已有外部工程报告WNS+0.248ns/WHS+0.036ns；不能据此声明当前板上映像身份或通信已通过。
- 本轮直接读取A上述提交的冻结ABI文档/头，与本机规范化换行后全文一致；读取ss_control_regs.sv，ID=0x5A5A2026、ABI=0x00010000；双BIST源码向量与现有S1一致；STM32 XDC五信号/3.3V标准一致。这是静态核对，不替代真实SPI。
- PR8已补齐Vitis/JTAG材料：[交付入口](https://github.com/TophBeifong1744/SoundSight/tree/b486b567db3cb20f1c56f98c89a7f081e265dc9b/software/vitis/stm32)。2026-10-19新版vitis_components.zip（1554条目）及位流/PS初始化一致性已核对，详见[核对记录](../../document/evidence/stm32-p4-pr8-20261018/REVIEW.md)。材料足够进入首轮无动作P4，现场加载/PS初始化/接线仍待确认；不要求为此补PYNQ或SD启动镜像。
- 三维D5 Issue #5尚无回复；它不阻断本次二维P4。此次未合并A的main，也未覆盖用户Keil工程在途修改。

## 第一步：确认现场与接线

使用 **STM32主方案** 映像，不使用PL+PS实验目标。将当前目录六文件同放一处（含新版unpack_local.py和外置path-bases.json），按当前README解包vitis_components.zip；Vitis2025.2 Set Workspace打开已有组件，重新选择本机JTAG连接。已有first_app_hw_1配置指向first/_ide/bitstream/pl_stm32.bit及first/build/first.elf，启用PS7 Init/Post Init。由现场人员启动并确认PS串口出现PS application running.，保留启动日志；不要求重建或只单独下载bit。此串口提示不能替代随后SPI身份检查。

此设计FCLK0=100MHz，经Clocking Wizard得到96/100MHz及61.44MHz；冷复位来自FCLK_RESET1_N。需要PS实际提供时钟和正确释放复位，不能把下载PL成功当成接口已经运行。无应答时优先核查这两项。

断电接线；两板分别供电、共地，确认Bank13实际3.3V和LVCMOS33。J4在板下边缘“7020 ONLY”，按丝印/针号核对方向，不按左右位置猜。

|信号|STM32引脚|探索者U16针|FPGA J4针|FPGA球号|
|---|---|---|---|---|
|SCK|PB3|5|5|V7|
|CS_N|PG7|4|6|U7|
|MOSI|PB5|6|7|W8|
|MISO|PB4|7|8|V8|
|IRQ|PG8|8|9|U9|
|GND|GND|1|37或39|—|

不连接U16-2、J4-38/40等电源输出。拔下U16无线模块，不启用SWO/JTAG/RS485，DAP仍用SWD。首轮无需麦克风和舵机，动作许可保持关闭。完整原表见[接线说明](../../hardware/stm32/SPI-WIRING.txt)。

## 第二步：同一固件运行一次fpga

只有现场映像/PS初始化和接线确认后执行。串口115200/8N1、命令以CRLF结束；保存完整输出。

```text
status
fpga
status
```

逐条发送，等待上一条完成。第一条status可补P3命令回读；fpga会先执行本板检查，再进行身份、拒绝/通过双BIST、锁帧释放/重新读取/消费、IRQ及软件注入超时恢复，最后显式停止/禁用并检查无动作。状态查询本身不启动生产者。

首轮先不发送stream、motion、discard或批量清故障。若出现FAIL，保留首次完整日志；不要靠反复复位/清故障把原因抹掉。发送fpga即授权该次BIST启动、快照消费及停止，不是被动寄存器浏览。

## 应观察到的结果（均为预期，待实测）

|检查|预期|
|---|---|
|身份|DATA,FPGA_ID_ABI,status=0,id=0x5A5A2026,abi=0x00010000|
|两组BIST|FPGA_SPI_BIST_REJECT/PASS两项均PASS；每组直接重读的transfers=40、status=0|
|拒绝数值|ux=46831，uy=-171729，residual=590912626，valid=0，reason=3|
|通过数值|ux=749295，uy=0，residual=0，valid=1，reason=0；servo_valid仍0|
|快照|FPGA_RELEASE_SAME_FRAME和SPI_SOFTWARE_40_TRANSACTIONS均PASS|
|IRQ|LOCKED时高，CONSUME后低，IRQ_EXTI_EDGES通过|
|恢复|INJECTED_TIMEOUT_ISOLATION、FPGA_EXPLICIT_RECOVERY、FPGA_AFTER_RECOVERY_BIST通过|
|结束|FPGA_IDLE_AFTER_TEST、FPGA_MOTION_DISABLED、FPGA_NO_UNEXPECTED_FAULT通过；SAFETY act=0、watchdog=0、fault=0|
|汇总|SUMMARY,scope=FPGA_DIAGNOSTIC,pass=32,fail=0,skip=4,result=PASS_WITH_SKIPS,NOT_SYSTEM_ACCEPTANCE|

32/0/4来自现有成功主机模型与入口代码；本轮未重跑模型，不将其冒充板测。剩余4项为物理SPI波形、电气卡死超时、真实连续流及实际运动，仍应SKIP。软件在CS前注入超时不证明真实总线卡死保护。

## 首错处理与后续

- ID读0/全1/错值或超时：先返回原始DATA/FAIL；检查映像目标、供电/共地、MOSI/MISO方向、PS时钟/复位，再按需要观察SCK/CS/MISO。未读到身份时不进入真实流。
- ID正确但BIST/释放/IRQ失败：保留完整前后顺序、帧号、transfers、status、fault；B据此定位。不得修改预期或放宽断言来“通过”。
- 若有逻辑分析仪：测SPI Mode0、MSB first、约1MHz，每个CS低窗40 clocks及CS建立/保持；这与软件报告40次事务是不同指标。仪器未测就保留未测。
- 收到首轮日志后，先判定已覆盖的P4软件/板端通信子项；物理波形及其他未测项继续列待办。P5连续真实帧另行开始，不自动开动作。

本次只准备联调和核对公开工程记录，无构建、下载、复位或板端命令执行。Git稀疏对象直连读取曾失败，已改GitHub API读取准确提交完成核对，不影响本机产品文件。
