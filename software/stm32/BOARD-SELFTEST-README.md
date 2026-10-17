# 探索者 V3.5 统一自检

硬件 STM32F407ZGT6；Keil uVision5 / ARM Compiler 5.06 update 7 / DAP-SWD。S1 与 ABI 引用仓库唯一 `software/common`，S2 源码位于 `src` / `include`。

## 打开、编译、下载

1. 打开 `keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx`，目标 Template，选择 ARM Compiler 5.06 update 7，DFP 2.15.0。
2. 项目已列全需要的 C 文件、头路径、8 KiB 栈和启动文件，不添加 PC `tests` 到 Keil。
3. Rebuild；确认 0 Error 后使用 `software/stm32/build/keil/atk_f407.axf` 或 `.hex`。全部构建产物均在此被忽略目录。
4. 本机已保留原 DAP uvoptx 作为本地文件，不上传个人调试状态。其他机器首次打开时，在 Options for Target → Debug 选择 CMSIS-DAP、SWD；Utilities 使用相同调试器，Flash 算法选 STM32F4xx 1 MB。串口 115200、8N1。
5. 下载由用户执行。复位默认 BOARD_ONLY，不发送 FPGA SPI 事务。

## 统一入口（串口发 CRLF）

|命令|覆盖|
|---|---|
|`board` / 启动|128/128/32/64 MHz 时钟；TIM2 1 us、HAL 毫秒、DWT；SPI/GPIO、安全片选；S2 初始化；禁动作写；S1 双 BIST 各 32 次|
|`fpga`|本板检查后探测 ID/ABI、SPI 双 BIST、锁帧释放再读、消费、IRQ 电平/边沿、软件超时隔离与恢复、运动禁用读回|
|`stream`|最多 2 秒 / 8 帧真实输入，记录帧号、方向/拒绝原因、IRQ；结束 STOP。重新完整联调前复位 PL，避免把粘滞故障误作新错误|

BOARD_ONLY 预期 `pass=11,fail=0,skip=11,result=PASS_WITH_SKIPS,NOT_SYSTEM_ACCEPTANCE`。这是模式预期；真实原板日志单独保存于 `document/evidence/stm32-board-20261017`。
主动请求 fpga 却探测不到身份时报告 FAIL，后续依赖项 SKIP。ID 预期 `0x5A5A2026`，ABI `0x00010000`。

## 配置与接线

保留 `sys_stm32_clock_init(256,8,2,8)`、`delay_init(128)` 与 USART1 PA9/PA10。HCLK 128 MHz，PCLK1 32 MHz，PCLK2 64 MHz；SPI1 /64 = 1 MHz（寄存器计算值）。TIM2 PSC=63、ARR=0xFFFFFFFF，无中断；原 HAL_IncTick 保留；DWT 不启用 SWO。

|信号|STM32|U16|FPGA J4|FPGA 球号|
|---|---|---|---|---|
|SCK|PB3|5|5|V7|
|CS_N|PG7|4|6|U7|
|MOSI|PB5|6|7|W8|
|MISO|PB4|7|8|V8|
|IRQ|PG8|8|9|U9|
|GND|GND|1|37 或 39|—|

先核对匹配 ABI 的 PL 映像、Bank13 实际 3.3 V 与 LVCMOS33。两板分别供电、共地，不连接电源输出。拔下 U16 无线模块；PB14 Flash CS 保持高；不用 RS485、SWO/JTAG，只用 SWD。U16-2 电源及 U16-3 PG6 不接。具体针脚方向按 [接线表](../../hardware/stm32/SPI-WIRING.txt)。

动作提交始终禁用；适配层拒绝 ACTUATOR_CMD、许可/COMMIT 和非零 WATCHDOG 写入。数学 BIST 通过不提交动作。PLLQ 当前非 48 MHz，不用于 USB/SDIO/RNG。

物理波形、总线电气卡死、PWM 运动和真实声学未验证；软件超时注入发生在 CS 前，仅验证软件隔离/恢复。SPI 1 MHz/40 时钟/CS 建立保持仍需外部仪器确认。主机 HAL 模型不执行实际板级寄存器轮询。
