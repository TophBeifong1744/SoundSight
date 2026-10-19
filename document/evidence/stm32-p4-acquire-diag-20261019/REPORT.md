# P4 取帧首错诊断 V3

2026-10-19；基于53edcbd，用户要求下一步。已完成PC验证和二维Template构建，未下载/回测。针对V2第二组BIST的ACQUIRE,status=8补定位信息，不宣称修复根因。

## 修改

三个产品文件：`software/stm32/include/fpga_link.h`新增16字节内部RAM诊断；`src/fpga_link.c`在原格式检查失败处保存具体检查/地址/pair/原始字及快照/帧号；`keil/soundsight_f407/User/soundsight_selftest.c`在取帧返回后输出。固件标记`FIRMWARE_DIAG,P4_ACQUIRE_V3`。

无额外SPI事务、读回、重试或清故障；所有原判定和错误码保持。ss_start原诊断保留，TIM2最小延时修正保留。新增RAM记录有少量CPU开销，不声称绝对不扰动时序。失败后的REVOKE、被隔离的重复调用和显式recover不覆盖记录；下一次实际取帧尝试重置。check=0仅表示未捕获格式拒绝，不能当成成功或没有传输错误。冻结SPI ABI/S1接口/RTL/动作门禁未改。

输出示例（来自PC故障注入，不是实板）：

```text
DATA,ACQUIRE_FORMAT,check=6,addr=0x0C,pair=3,word=0x664F1A00,snapshot=0x00017F39,frame=2
DATA,ACQUIRE,status=8
```

该例中期望pair=3，读回FEATURE_0的pair字段实际为2。`word`是成功传输后收到的原始32位值，不保证内容本身可信。pair=255表示整帧检查；frame=0可能表示尚未读取帧号。check12的word为计算所得六对raw_valid掩码，snapshot仍保留原始状态字，两者须按下表比较。

|check|含义/判定要求|
|---|---|
|1|SNAP_STATUS保留位必须为0|
|2|PROFILE_SUPPORTED必须为1|
|3|锁定快照ALL_TERMINAL必须为1|
|4|非BIST快照不能声明真实模式未提供的能量有效/能力|
|5|FEATURE_0保留位必须为0|
|6|FEATURE_0 pair回显必须等于请求的pair|
|7|PHAT阶段必须为1～6|
|8|IFFT阶段必须为1～6|
|9|lag必须在-32～31|
|10|mask_count不能超过79|
|11|对应相关值必须在S25范围-16777216～16777215|
|12|六对raw_valid汇总word必须等于(snapshot & 0x3F00)>>8|

## 验证结果

|项目|实测结果|
|---|---|
|取帧首错定向测试|15435项断言0失败；107组格式异常，覆盖全部12类及六pair；156组传输故障不误报格式错误|
|证据保留/流程|隔离及recover保留诊断；重新取帧清旧记录；39事务取帧/40事务取帧解算消费不变；错误输出清零|
|UART注入|第二组BIST pair3错误准确输出上例，仍20/3/5，超时注入不执行，动作写0|
|原S1/S2/启动诊断|4705/15980/1459项通过，原5自检模型和命令通过；成功模型仍32/0/4、302事务|
|P3主机模型|默认3070项、测试开启3283项通过；该脚本可选AC5对象检查未指定，不能算已执行|
|二维Keil Template完整构建|AC5退出0，0错误0警告；Code30174/RO2378/RW48/ZI10120，AXF/HEX已生成|

用户本地uvprojx构建前后相同，未提交；三维目标未构建、许可未修改。上述PC模型不模拟电气时序，不等于真实板端/物理波形通过。

复现命令：

```text
python software/stm32/tests/run_acquire_trace_tests.py
python software/stm32/tests/run_app_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <日志绝对路径>
```

## 用户下一步

1. 在原Keil工程选择二维Template，通过DAP/SWD下载`software/stm32/build/keil/atk_f407.axf`；同目录HEX可用，无新增Keil源文件。
2. 记录本次PL映像是否包含A修改，并与A确认复测初始状态。STM32下载不会清除PL旧故障/占用槽，不能带着未知残留状态宣称回归失败；也不在驱动中自动清错或重试。
3. 确认启动标记`P4_ACQUIRE_V3`，逐条发送`status`、`fpga`、`status`（CRLF），回传全文，重点保留`ACQUIRE_FORMAT`和原`START_TRACE`。
4. 如果不再失败，记录本轮通过，仍不凭一次成功认定原故障永久消失。若失败，按check/原始值对照A的快照和SPI输出；必要时抓总线波形。暂不stream或运动。

本次只修改诊断/测试/文档并构建，不操作板卡。有效源码及证据归正式目录，产物在既定build目录；未创建codex_out或额外工程副本，未删除用户文件。
