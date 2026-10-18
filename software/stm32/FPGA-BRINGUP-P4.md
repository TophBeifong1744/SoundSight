# P4 两板基础联调：先运行无动作双 BIST

2026-10-18。状态：已启动准备，等待现场确认映像/启动/接线及首次fpga串口；尚无P4实板结果。使用已通过用户BOARD_ONLY 13/0/11的二维Template固件，无需重新构建。三维超限构建按用户要求暂停。

## 当前双方基线

- B：P3用户串口13 PASS/0 FAIL/11 SKIP；二维APP_PROFILE=0、动作门禁关闭。[记录](../../document/evidence/stm32-p3-board-ready-20261018/REPORT.md)。
- A：main `24f063a54efcfebd27e8f1281f870d4da77eb36a`，PR [#6](https://github.com/TophBeifong1744/SoundSight/pull/6)/[#7](https://github.com/TophBeifong1744/SoundSight/pull/7)已合入。STM32主方案实际配置/报告已接回，器件xc7z020clg400-2，顶层soundsight_stm32_bd_wrapper。已有外部工程报告WNS+0.248ns/WHS+0.036ns；不能据此声明当前板上映像身份或通信已通过。
- 本轮直接读取A上述提交的冻结ABI文档/头，与本机规范化换行后全文一致；读取ss_control_regs.sv，ID=0x5A5A2026、ABI=0x00010000；双BIST源码向量与现有S1一致；STM32 XDC五信号/3.3V标准一致。这是静态核对，不替代真实SPI。
- [A交接说明](https://github.com/TophBeifong1744/SoundSight/blob/24f063a54efcfebd27e8f1281f870d4da77eb36a/document/stm32-handoff.md)明确不含可直接下载bit或PYNQ启动镜像。现场bit文件名/路径、加载方法、PS初始化状态仍需用户/A补充。
- 三维D5 Issue #5尚无回复；它不阻断本次二维P4。此次未合并A的main，也未覆盖用户Keil工程在途修改。

## 第一步：确认现场与接线

使用 **STM32主方案** 映像，不使用PL+PS实验目标。由A/现场人员按其实际环境加载匹配bit和必要PS初始化；记录文件名/路径、来源工程版本、加载方式及是否完成启动。不在未明确加载环境时猜测PYNQ或JTAG命令。

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
