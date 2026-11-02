# Screen S2：PS I2C0 / EMIO 硬件候选

本目录是独立硬件候选，已用 Vivado 2025.2 完成官方 IP 生成、综合、布线、BIT/HWH/XSA 导出及正式 XPR 实际重开。原 ss-screen-s1、ss-j3-servo 和旧屏幕工程未改。没有 ILA、JTAG、下载或板卡操作；功能仿真按本次板端故障修复范围 SKIPPED。硬件作者不独立签署验收，需结合非作者审阅和板端 PS/Linux 归属证据。

## 打开与构建

实际工程：`project/par/SoundSight_PS_3D.xpr`，目标 `xc7z020clg400-2`。已完成 `synth_1` 和 `impl_1` route，工程已由新 Vivado 进程实际打开并验证 BD。当前目录可直接打开 XPR 查看实现结果；重新从源码构建应使用不含旧 project/par 的新副本。

- `build.bat`：默认只综合。
- `build.bat route`：综合、布线、原有检查及候选硬件导出。
- 本次实际命令：`vivado.bat -mode batch -source build.tcl -log build.log -journal build.jou -tclargs route`。
- Vivado 2025.2 SW6299465/IP6300035，jobs 16，general.maxThreads 8；综合实际最多 7 个辅助进程。仅修改当前 BAT 进程的工具 PATH，不需要 PowerShell 作为正式运行依赖。

产物：`output/soundsight.bit`、`soundsight.hwh`、`soundsight.xsa`、`screen-ps-i2c-s2-routed.dcp`。XSA 内 BIT/HWH 与独立文件逐字节一致。哈希和大小见 `reports/hardware-artifacts.json`。

## 改动及保持项

S2 删除 AXI IIC 2.1 模块 `screen_iic`，启用 `ps7/IIC_0` 经 EMIO 接到原同名外部接口。control_bus 从 6 个输出缩为 5 个，GPIO 从 M05 改接 M04，没有留下未终结的 AXI 主口。其余模块地址不变。官方迁移配方为 `ps_i2c_integration.tcl`，由 `screen_integration.tcl` 调用；官方生成 BD 位于 payload/SoundSight_PS_3D.srcs/sources_1/bd/soundsight_stm32_bd。

所有 32 份原声学源码、已有 XDC 和屏幕引脚 XDC 与 S1 逐字节一致。音频 HP0、显示 HP1/VDMA/RGB、100 MHz/61.44 MHz 时钟、像素 33.3 MHz、声学算法、舵机 M15/J14 和 GPIO 复位默认保持。详见 `reports/bd-connection-delta.json`。

|对象|S2 合同|
|---|---|
|PS I2C0|固定物理地址 0xE0004000..0xE0004FFF，经 EMIO|
|旧 AXI IIC|0x41600000 已移除，不可再按旧后端访问|
|screen_gpio|0x41200000；ch1 bit0=RST/M19，bit1=INT/U19，bit2=BL/M20；默认 DATA=0/TRI=2|
|screen_gpio ch2|bit0 为同步后的视频 locked|
|screen_vdma|0x43000000；双缓冲 MM2S，软件提供 PYNQ 分配的合法缓冲地址|
|SCL/SDA|R19/P20，LVCMOS33，官方 IOBUF；外部名 screen_iic_scl_io/screen_iic_sda_io 不变|

HWH 可识别身份：没有 `screen_iic` AXI MODULE；`ps7` 参数 PCW_EN_I2C0=1、PCW_EN_EMIO_I2C0=1、PCW_I2C0_I2C0_IO=EMIO；I2C1 保持禁用。原音频/PL IRQ 不变，PS I2C0 使用其原生 PS 控制器路径。

## 时钟、复位与 PS 初始化边界

Cycle Contract Delta 仅涉及 I2C：从 PL 100 MHz AXI IIC/总线复位，改为 PS I2C0 的 CPU_1x 时钟和 PS 控制器复位/软件状态；重审影响范围是 PS I2C0/EMIO、wrapper IOBUF、控制总线 GPIO 槽位迁移及受影响的物理实现。音频、RGB、舵机数据通路的采样/流水/有效握手没有源代码改动。新 I2C 事务延迟和板上波形尚未测量。

官方生成的 `ps7_init.c` 与 S1 逐字节一致，且与旧 g_signal_analyzer hw_platform_1 的 501 条 EMIT 初始化命令逐条一致。SLCR 初始化增量为零：ARM_CLK_CTRL 0xF8000120 的 mask/value 为 0x1F003F30/0x1F000200；APER_CLK_CTRL 0xF800012C 为 0x01FFCCCD/0x01DC000D，I2C0/1 gate 位 18/19 原本均为 1；CLK_621_TRUE 0xF80001C4 的 mask/value 均为 1。三份初始化均未写 I2C_RST_CTRL 0xF8000224，不能由此推断运行态复位值。

旧和新 XCI 都保留 PCW_ACT_I2C_PERIPHERAL_FREQMHZ=50 字段，同时请求值为 111.111115；旧 XIicPs BSP 使用 111111115 Hz。运行驱动不能仅按 ACT 字段假定 50 MHz，也不能将静态初始化等同于 Linux 当前时钟。必须读取实际时钟树和控制器状态。完整事实见 `reports/ps-i2c-platform-contract.json`。

Overlay 加载不会执行 PS boot-time SLCR 初始化，也不会取得 Linux 控制器所有权。不要在运行中的 Linux 执行完整 ps7_init。上板前需只读核对 e0004000/e0005000 的活动 DT、status/compatible/clocks/pinctrl/子设备、sysfs adapter 名称及 driver 绑定、/proc/iomem 和 interrupts、内核 clock summary 和实际门控/复位/引脚归属。控制器应在重配置 PL 前停止事务；尚未证明只换 BIT 即可工作。不要求用 i2cdetect 扫描来代替这些只读证据。

旧参考代码：g_signal_analyzer.sdk/final/src/touch_config.h 的 100 kHz 配置；touch.c 的 read_reg8/read_reg16/write_reg16 和 goodix_reset_for_address；final_bsp/ps7_cortexa9_0/libsrc/iicps_v3_8/src/xiicps.c 的 CfgInitialize/Reset 及 xiicps_master.c 的 MasterSendPolled/MasterRecvPolled。GT911 地址字节高位在前，814E 清零为一次连续 81 4E 00 发送；参考代码不是本候选的板测结果。

## 同候选物理证据

|项目|实测工具结果|
|---|---|
|Setup WNS / TNS|+0.203 ns / 0|
|Hold WHS / THS|+0.036 ns / 0|
|Pulse-width WPWS / TPWS|+2.208 ns / 0|
|水平/垂直 PWM max slack|+10.076 / +10.841 ns|
|Bus skew|16 条报告路径通过，最小 slack +9.164 ns|
|布线|40,846/40,846 条可布线网完成，0 路由错误|
|LUT / FF|19,971 (37.54%) / 22,358 (21.01%)|
|BRAM / DSP|36 tiles / 41|
|时钟资源|8 BUFGCTRL，3 MMCM|
|无时钟/未约束内部端点|0 / 0|
|外部延迟缺项|3 个输入、30 个输出；计数下降来自 AXI IIC 移除，不代表 PS I2C 引脚物理时序已测|

构建原生进程 exit 0。综合工具结尾汇总 365 warnings、0 critical warnings、0 errors；原始综合日志另有一条 `Common 17-1257 Failed to create directory 'C'.` 环境诊断，不能被末尾统计掩盖。其后综合产生完整 DCP、布线完成、写 BIT 前 DRC 为 0 errors；该环境诊断仍保留，不宣称已修复。综合 elapsed 6m13s，peak 2957 MB。未为它修改 RTL/约束或改变实现策略。

CDC 报告：CDC-3=27，CDC-10=1，CDC-11=2，CDC-15=1252。显示复位限定和独立 locked 遥测同步链的 critical 标签仍保留，无新增豁免；S1 的有限冷启动解释不能自动替代 S2 非作者复核。DRC 显示 99 项 warning/advisory；REQP-1839/1840 各有 20 项显示上限，不能从相同计数推定实例或总量不变。panel 外部 setup/hold 没有依据，未虚构输出延迟；屏幕 I/O 不属于完整时序闭合。功耗验收 NOT APPLICABLE。

原始报告在 reports/：timing-summary、check-timing、route-status、utilization、clocks、screen-clock-actual、cdc、clock-interaction、drc、methodology、bus-skew、两个 servo max/min 报告。实际输入清单为 actual-inputs.txt；源码身份为 screen-source-manifest.json。

## 移交及未验证项

实际新 XPR 已重开并通过 BD/IP/输入归属检查，报告见 reopen-result.txt。从最终 ZIP 搬迁重建的验证待根协调器另批安排。本候选未仿真、未上板、未测 SCL/SDA/RST/INT、未证实 GT911 814E 写成功、未验证 Linux 资源归属、异常复位恢复或音频/显示/触摸联调。

人类可打开已实现工程，查看 timing-summary 与 IO assignment 对应 R19/P20/M19/U19，并保存原始报告。完成 PS/Linux 所有权核对后，由协调器提供运行端，再进行 axes-off 的 ID/清 ready/坐标读取验证和原始串口日志回传；本目录不包含对运行板的自动操作。无 ILA 计划。
