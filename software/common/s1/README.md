# S1：冻结接口与PC交接验收结果

日期：2026-10-17。结果：**PASS，4705项断言，0失败；编译退出0、运行退出0。** GCC 8.1.0，严格C99、O2、全部警告作为错误。输入均为PC合成特征；S1完成后暂停，S2尚未启动。

## 改了什么

- 完成冻结跨板文档和共同常量头，再将已开始的S1代码适配为冻结的`doa_frame_input_t`/`doa_solve_output_t`交接。
- 三个C99源文件实现S25/S6范围检查、RNE插值/margin、mask/阶段/tau资格、LS/残差/范数、原24级整数CORDIC、atan2f对照、原规则水平舵机映射。
- 整数CORDIC产生正式angle_q8；浮点结果用于对照。所有输出每次清零，拒绝后旧角度/旧动作不会残留。
- 垂直valid始终0；BIST的servo_cmd_valid始终0。FPGA RTL没有修改。

## 交付入口

1. [FROZEN_SSOT_ABI.md](F:/NUEC/stm32/FROZEN_SSOT_ABI.md)：唯一跨板开发依据，STATUS:FROZEN。
2. [fpga_stm32_abi_frozen.h](F:/NUEC/stm32/fpga_stm32_abi_frozen.h)：寄存器/位域/故障/阶段码、双BIST、明确定义的有符号解码。
3. [doa_solver.h](F:/NUEC/stm32/s1/doa_solver.h)及[doa_solver.c](F:/NUEC/stm32/s1/doa_solver.c)：冻结S1/S2 API与实现。
4. [test_doa_solver.c](F:/NUEC/stm32/s1/test_doa_solver.c)：PC交接测试。

实际记录：[编译日志](F:/NUEC/stm32/s1/build/compile-frozen.log)、[完整运行输出](F:/NUEC/stm32/s1/build/run-frozen.log)。此前compile-o2/run-o2是补充冻结要求前的首次数值测试；最终结果以带frozen文件名的记录为准。

## 冻结接口摘要

- 40bit、5byte、Mode0、MSB first；地址0x00～0x7C；完整读取40事务、1MHz纯线上1.60ms。
- SYS_CTRL仅bit0/1/3；消费为SNAP_CMD bit2。双BIST选择独立放在0x2C（0拒绝，1通过）；0x6C返回ABI版本。
- FEATURE_0保留原因/阶段，S2将flags掩码后传给S1；SNAP_STATUS的帧取消与first_error随锁槽冻结。S1/S2不复制定义，不直接传输C结构体内存。
- 动作需独立ACT_CTRL许可与非零看门狗；BIST禁止实物PWM。S1返回servo_cmd_valid，S2仍检查硬件许可和当前帧新鲜度。
- 本测试显式使用offset=90°、domain=±90°、机械0～180°的示例配置。实物映射在S2接合时配置。

## 核心实现片段

```c
denominator = (int64_t)p->r_minus - INT64_C(2) * p->peak + p->r_plus;
numerator = ((int64_t)p->r_minus - p->r_plus) * INT64_C(2048);
if (denominator < 0) { denominator = -denominator; numerator = -numerator; }
delta = rne_div(numerator, denominator);
```

负数不左移；CORDIC负数算术右移用带余数的向下整除实现；同一轮cx/cy均使用更新前值，保持原RTL非阻塞赋值语义。

## 双BIST：预期与实测逐项相等

|pair|拒绝tau预期|拒绝tau实测|通过tau预期|通过tau实测|
|---:|---:|---:|---:|---:|
|0|19797|19797|16384|16384|
|1|−12971|−12971|16384|16384|
|2|−683|−683|0|0|
|3|3413|3413|0|0|
|4|−4779|−4779|−16384|−16384|
|5|7509|7509|−16384|−16384|

拒绝向量六对delta预期/实测均−683；通过向量均0；两组全部margin预期/实测均29491。

|字段|拒绝预期|拒绝实测|通过预期|通过实测|
|---|---:|---:|---:|---:|
|ux_q20|46831|46831|749295|749295|
|uy_q20|−171729|−171729|0|0|
|残差平方和|590912626|590912626|0|0|
|残差门限|25165824|25165824|25165824|25165824|
|范数平方|31683992002|31683992002|561442997025|561442997025|
|direction_valid|0|0|1|1|
|direction_reason|3|3|0|0|
|angle_q8|无效|0且valid=0|0|0|
|servo_cmd_valid|0|0|0（BIST）|0|

## 非零角与边界实测

以下real-mode测试帧同样由PC构造，用于覆盖真实帧资格分支。

|输入/场景|预期|实测|
|---|---|---|
|lag={3,6,3,3,0,−3}|+45°，angle_q8=11520，水平135°|11520，atan2f=45.000000°，水平135°|
|lag={3,0,−3,−3,−6,−3}|−45°，angle_q8=−11520，水平45°|−11520，atan2f=−45.000000°，水平45°|
|lag={0,4,4,4,4,0}|+90°，angle_q8=23040，水平180°|23040，atan2f=90.000000°，水平180°|
|lag={0,−4,−4,−4,−4,0}|−90°，angle_q8=−23040，水平0°|−23040，atan2f=−90.000000°，水平0°|
|±135°、−180°|方向有效，示例舵机域拒绝|方向有效，map_valid=0，servo_cmd_valid=0|
|lag={4,5,1,1,−3,−4}|Q8=3593，水平104°|3593，atan2f=14.036261°，水平104°|
|lag={2,5,3,3,1,−2}|Q8=14415，水平146°|14415，atan2f=56.309952°，水平146°|
|全部mask=11|0有效pair，reason1|0有效pair，valid0/reason1|
|仅2对raw_valid|reason1|2有效pair，valid0/reason1|
|S25越界|API输入范围错误，reason7|DOA_INPUT_RANGE，valid0/reason7|
|全零tau|范数拒绝reason4|valid0/reason4|
|高范数五有效pair|范数拒绝reason4|norm=2122957877922，valid0/reason4|

额外断言覆盖：S6/S25上下界、未知/未终结阶段、flags保留位、取消优先、缺失IFFT资格、缺失终态、无次峰、零分母、正负RNE半距、delta限幅、64bit大margin、tau门限等号/超1、舵机半距/映射前范围、反向映射、空参数和旧输出清除。

1440个四象限角度样本（包含非整Q8点）：整数CORDIC与double atan2的最大环形角差**0.001634337°**，与atan2f的最大环形角差**0.001647949°**。这些是本次样本的实测最大值。

跨模块测试另外把两组BIST编码为32bit大端字，再按冻结宏解码至doa_frame_input_t，调用doa_solve并逐项断言。literal负lag字0x664F19FD、S25负数扩展、MAGIC字节序和CONSUME命令均通过。

## 运行命令（PowerShell）

```powershell
Set-Location 'F:/NUEC/stm32/s1'
& 'F:/STUDY/IT/C/develop/mingw64/bin/gcc.exe' -std=c99 -Wall -Wextra -Wconversion -Wshadow -Werror -pedantic -O2 -D__USE_MINGW_ANSI_STDIO=1 -I.. doa_solver.c test_doa_solver.c -lm -o build/test_doa_solver.exe
if ($LASTEXITCODE -ne 0) { throw 'C99 compile failed' }
& './build/test_doa_solver.exe'
```

最终控制台：`RESULT,PASS,checks=4705,failures=0`。

## 下一步

S1交付后暂停。进入S2时直接使用上述两个冻结头文件；需绑定STM32准确型号、开发环境、SPI/EXTI/串口实例及实际引脚，补齐显式运动看门狗/舵机映射配置。FPGA组接收冻结文档与ABI头，按同一双BIST表对照。
