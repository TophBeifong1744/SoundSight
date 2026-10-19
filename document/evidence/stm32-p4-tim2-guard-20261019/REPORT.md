# P4 STM32 SPI 最小保护延时修正

2026-10-19；基于c01e3b9，用户授权执行修改。软件修正和二维Template构建已完成，尚未下载/实板回测，不能据此关闭原0x41故障。

## 改了什么

- `software/stm32/keil/soundsight_f407/User/soundsight_board.c`：非零微秒等待从计数差达到us改为达到us+1。TIM2仍为1MHz；首次取样可能紧邻下次跳变，多等待一个计数增量消除起始相位少等的问题。`wait_us(1)`等待两个增量，理想稳定计时下从首次取样起超过1us、不超过2us到达阈值；指令和中断可增加实际耗时。0请求仍立即成功，timer_ready、100000us上限、无符号回绕及有限循环保护保留。
- CS拉低和拉高后增加`__DSB()`，让GPIO写完成后再开始建立/空闲等待。最后BSY=0检查及CS拉高前的保持等待保留；正常SPI事务格式、数量、速率、超时和错误隔离不变。计时器故障时仍有界失败并释放CS，不声称故障路径也满足正常帧时序。
- `soundsight_selftest.c`：固件标记改为`FIRMWARE_DIAG,P4_TIM2_GUARD_V2`。双BIST、故障检测和动作禁用未放宽。冻结ABI、S1/S2解算和FPGA RTL未改。

核心代码：

```c
if (!ss_board_stats.timer_ready || us>100000U) return 0;
if (us==0U) return 1;
while ((uint32_t)(ss_board_us()-start)<us+1U)
    if (--n==0U) return 0;
```

## 实测结果（PC模型及编译）

|验证|预期|实测|
|---|---|---|
|实际C等待函数的768组相位/回绕场景|1/2/10us请求不短于请求时长|1549断言通过；1us请求模型最短129/128us=1.0078125us|
|旧谓词替换负例|被最小时长断言拒绝|退出1；首个失败等待127/128us，小于1us|
|停转/未就绪/越界/0请求/大步跳变/最大合法请求|有界失败或符合约定|包含在1549断言中，通过|
|S1/S2回归|数值与错误传播不变|4705/15980断言通过|
|主机自检与命令|原分类保持，动作禁止|5场景及命令通过；成功模型仍32通过/0失败/4跳过、302事务|
|启动诊断回归|原首错保留、无效读回不输出伪值|1459断言、8读回/52传输故障及UART检查通过|
|AC5二维Template完整构建|0错误/0警告，生成AXF/HEX|退出0；Code29862、RO2286、RW48、ZI10104|

相位测试直接提取当前产品函数编译运行，以128MHz粒度模拟1MHz计数器，并测试U32回绕。它没有模拟完整SPI外设、GPIO物理边沿、异步同步器或电气干扰；模型数值不冒充仪器测量。用户本地uvprojx构建前后内容一致，原有未提交修改保留且不纳入提交。三维超限目标未构建，许可未修改。

复现：

```text
python software/stm32/tests/run_board_delay_tests.py
python software/stm32/tests/run_start_trace_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <日志绝对路径>
```

## 下载与双方接续

1. B/现场在原Keil工程选择二维Template，通过DAP/SWD下载本地`software/stm32/build/keil/atk_f407.axf`（同目录也有HEX）。没有新增源文件需要加入Keil。
2. 记录A实际加载的FPGA映像及是否包含同拍fall检查修正。原0x41是粘滞故障，仅下载STM32不会清除PL历史故障；由A/现场按约定建立明确的复测初始状态，保留此前日志。本固件不自动清除混合故障、不自动复位PL。
3. 启动确认`FIRMWARE_DIAG,P4_TIM2_GUARD_V2`；BOARD_ONLY预期13/0/11。按`status`→`fpga`→`status`逐条发送CRLF，回传全文。无异常时主机模型预期FPGA_DIAGNOSTIC为32/0/4，这不是本次板端实测。
4. 若再出现0x41，保留首错并抓CS/SCK/MOSI/MISO；测最后SCK下降沿到CS拉高及其他最小间隔。B的软件最低延时补齐不证明该故障根因已经确认，更不替代A对同拍fall提交条件的修正/验证。

保持动作关闭，暂不进入stream或运动。本次仅源码/PC测试/本地构建/同步，不执行下载、复位或板端命令。必要日志归本目录，产物仅在既定build目录；未创建codex_out或额外工程副本，未删除用户文件。
