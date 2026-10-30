# SoundSight FPGA—STM32 跨板与 S1/S2 接口契约

STATUS: FROZEN

ABI_VERSION: 1.0 / 0x00010000

冻结日期：2026-10-17

状态：用户已确认R1及13项审阅修正。本会话负责STM32 S1/S2，FPGA F1～F3由FPGA组推进。本文件与fpga_stm32_abi_frozen.h、s1/doa_solver.h共同作为本次唯一冻结契约；替代此前INTERFACE-SPEC草案。公开字段、地址、原因码或数值规则变更须经用户同意并升级版本。当前实现S1，FPGA组以本合同开发F1/F2。代码入口：`F:/NUEC/stm32/s1/`。

## 1. 数据边界和数值Profile

FPGA保留PDM/CIC、1024/512分帧、预处理、官方FFT、六对跨谱/PHAT、官方IFFT与整数峰/邻点提取。每pair在LAG_MARGIN最后更新稳定后采入槽，六pair全部终态后发布一帧。取消/失败也有终态与原因，不能等六pair成功才终结。STM32实现插值、margin、LS和方位CORDIC及舵机坐标映射。

pair顺序：(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)；几何dx/dy为(1,0),(1,1),(0,1),(0,1),(-1,1),(-1,0)。本Profile沿原标称48kHz、40mm、343m/s常数，bin7～85共79点。实际几何标定在后续接合时绑定。

输入每pair：S6 lag、四个S25相关值peak/left/right/second、second_valid、U7 mask_count及raw_valid/IFFT资格/取消/数值错/PHAT和IFFT阶段。mask的本Profile实际范围0～79。S25范围−16777216～16777215，S6范围−32～31；越界立即报输入错误，绝不截断回绕。

纯C函数接收一份完整六pair结构；S2负责锁槽、pair回显及同帧读取。本结构不是通过memcpy直接发送的线协议。输入flags中的ALL_TERMINAL=1时，PHAT/IFFT阶段必须已终结，PENDING按输入错误拒绝。

- den=left−2*peak+right；分子=((int64_t)left−right)*2048。负分母同时反转分子/分母。den=0时delta=0，否则正负对称RNE（最近偶数），限幅±2048。tau=lag*4096+delta。
- margin=RNE(((int64_t)peak−(second_valid?second:0))*32768/max(abs((int64_t)peak),1))，输出int64_t；Q15表示缩放，不是概率范围。
- mask≥12；原raw/阶段合格；pair1/4的tau绝对值≤32425，其他≤22928。无效pair不参与LS。
- LS：累计sxx,syy,sxy,bx,by；det=sxx*syy−sxy*sxy。ux_q20=RNE((syy*bx−sxy*by)*87808/(det*1920))；uy同理。有效pair至少3，det>0；ux/uy范围−4194304～4194303。
- predicted_tau=RNE((dx*ux+dy*uy)*7864320/(343*1048576))；残差平方和≤valid_pairs*4194304。范数ux²+uy²范围10995200164～1858175196201（含边界）。
- direction_reason：0有效，1有效pair不足，2几何奇异，3残差超限，4范数超限，5保留，6取消，7输入/源/数值错误。软件输入错误另有API状态和bad_pair_index，不占用原原因码。
- 原24级整数CORDIC和原atan ROM产生权威angle_q8，范围[−180°,180°)。C以明确的向下整除实现算术右移，不依赖负数右移行为；乘法代替负数左移。atan2f给出独立浮点对照，不改变正式输出。
- 水平舵机映射按signed_angle_map.sv：mapped=offset_q8+direction*angle_q8，direction只能±1；先检查方位域/机械范围，再RNE到整数度。拒绝时valid=0，无wrap/clamp。垂直轴valid固定0。
- 配置显式提供offset、domain、mechanical_min/max、servo_max。PC示例为offset=90°、domain=±90°、mechanical=0～180°，与实物配置分开。

64bit算术上界：插值分子<2^36、margin分子<2^40；参与LS的tau≤32425，保守|bx/by|<2^18、|LS缩放分子|<2^39；检查ux/uy范围后残差预测分子<2^46、残差平方和<2^39、范数≤2^45。CORDIC归一后向量及24次迭代在原28bit有符号范围内；C用int64_t保存所有中间量。

## 2. SPI物理与事务

Mode0，MSB first，61.44MHz处理域同步过采样SCK/CS_N/MOSI。每次CS严格40bit，头字节{write,byte_offset[6:0]}，后32bit大端。地址0x00～0x7C且4字节对齐；未定义地址、RO写、未定义位非零均置协议错，未知读返回0xDEADBEEF。所有未列位读0写0。

初始SCK=1MHz；SCK高/低和CS前后保持至少8处理周期（约130.21ns）。第8下降沿呈现payload bit31，第9上升沿采样；后续下降沿移至下一位。CS释放、恰好40上升沿才提交副作用；短帧丢弃、长帧置错丢弃，计数饱和。针脚、电平与实际SPI实例在S2绑定。

## 3. 寄存器表

|地址|名称|属性/复位|定义|
|---|---|---|---|
|0x00|MAGIC_ID|RO/0x5A5A2026|链路标识|
|0x04|SYS_CTRL|RW/0x08|bit0 enable；bit1 BIST；bit3 Lite；其余位（包括bit2、bit4）保留0。首版Lite=1，Lite=0为未支持配置并报错。|
|0x08|FRAME_CNT|RO/0|锁定快照32bit序号，首帧1；尝试发布含丢包也递增；到上限停止接纳，显式重启后从1开始。|
|0x0C|FEATURE_0|RO/0|见下文|
|0x10|FEATURE_1|RO/0|peak，S25符号扩展S32|
|0x14|SIGNAL_ENG|RO/0|真实模式0且energy_valid=0；BIST合成100000且energy_valid=1|
|0x18|ACTUATOR_CMD|RW影子/0|[8:0]水平度码，[17:9]垂直度码，bit18/19轴valid；首版垂直valid=0；写入仅暂存|
|0x1C|FEATURE_SELECT|RW/0|[2:0]pair0～5，6/7拒绝|
|0x20|R_MINUS|RO/0|left S32|
|0x24|R_PLUS|RO/0|right S32|
|0x28|R_SECOND|RO/0|second S32，结合second_valid|
|0x2C|BIST_SELECT|RW/0|0拒绝向量，1通过向量；其他值拒绝。只在停用、排空、队列空时可改。|
|0x34|SNAP_STATUS|RO|bit0 locked、1 queued、2 gap、3锁定帧BIST、4六对终态、5锁定帧energy_valid、7实际运动许可、[13:8]六raw_valid、14实时IRQ、15排空中、16当前profile支持、17真实能量能力（0）、19执行器已绑定、20锁定帧已取消、[31:24]锁定帧原first_error_code；位6/18/21～23保留0|
|0x38|SNAP_CMD|W1P/0|bit0 ACQUIRE、bit1 RELEASE、bit2 CONSUME。每次最多一个脉冲。CONSUME只消费当前LOCKED槽；无锁消费报错。|
|0x58|ACT_CTRL|RW/W1P/0|bit0独立运动许可请求；bit1 STOP、bit2 REVOKE、bit3 COMMIT。读bit0为实际许可；写0撤销。STOP/REVOKE优先。|
|0x60|WATCHDOG_TICKS|RW/0|处理域周期数；0关闭运动；无运动许可时可设置。仅成功接受的新动作续期。|
|0x64|FAULT_STATUS|RO/W1C/0|粘滞错误；同拍新错置位优先；停用且原因消退后可清，清错不恢复运动|
|0x68|DROP_COUNT|RO/0|满槽丢新帧累计，U32饱和；冷复位清0|
|0x6C|ABI_VERSION|RO/0x00010000|本接口major/minor各16bit|

FEATURE_0：[7:0]S8 lag；[10:8]pair回显；11 raw_peak_valid；12 second_valid；13 IFFT合格；14取消；15数值错误；[22:16]mask_count；23保留；[27:24]PHAT阶段；[31:28]IFFT阶段。原阶段码0 PENDING、1 OK、2 REJECTED、3 NUMERIC、4 PROTOCOL、5 CANCELLED、6 SKIPPED。无效数值归零、valid清0、原因保留。

FAULT_STATUS位0事务格式、1地址/字段、2快照操作、3溢出、4源协议、5数值、6取消/STOP、7动作拒绝、8看门狗、9计数溢出、10配置未绑定、11帧不完整；其余0。内部首错继续由FPGA记录。

本次冻结细化：双BIST选择使用独立0x2C寄存器，SYS_CTRL bit4仍保留0；SNAP_STATUS新增锁定帧cancel/first_error，随槽封存并冻结，避免额外SPI读取或把实时故障误配给旧帧；0x6C给出ABI版本。此前草案的SYS_CTRL bit4选择方式已撤回。S1仅处理解码后的结构体。

## 4. F1a与两槽状态转换

F1a串行处理pair0～5：每对LAG_MARGIN末次更新后的稳定周期，将lag/四相关值/mask/阶段flags采入该pair槽；下一pair不得覆盖之前的槽。取消或未运行的pair仍封存终态且数值归零。全部六对终态后，帧号、BIST、frame_cancelled、first_error_code和六对载荷同拍封存。ready=0时保持feature_valid及整帧载荷稳定；ready=1时单次交接。物理采集持续而下游满槽时，适配器完成本次IP排空并记录丢新帧，不能反压PDM停采。

|事件|前态|后态/动作|
|---|---|---|
|整帧到达且有FREE|FREE|原子写入后READY|
|整帧到达且无FREE|两槽均被占用|丢新整帧，递增帧序号和DROP_COUNT，置gap/故障|
|ACQUIRE|无LOCKED且存在READY|最老READY→LOCKED|
|ACQUIRE|已有LOCKED|保持原锁，无副作用|
|ACQUIRE|无READY/LOCKED|空操作，locked=0|
|RELEASE|LOCKED|退回READY，仍保留原序号|
|CONSUME|LOCKED|该槽→FREE，重新计算IRQ|
|RELEASE/CONSUME|无LOCKED|拒绝并置快照故障|
|enable清0或STOP|任意|停止新事务、取消/排空；已发布槽保持|
|冷复位|任意|两槽FREE，序号0，控制/输出按复位值|

SNAP_CMD同写多个脉冲拒绝，全0为空操作。消费与新到达同拍时，先允许锁槽释放供新整帧接入，再由最终占用/故障生成IRQ；无可用槽仍丢新帧。

## 5. 读取与动作

两槽FREE/READY/LOCKED。每帧六对终态及标志原子发布。ACQUIRE锁最老READY，已锁重复ACQUIRE无动作；RELEASE退回READY；CONSUME释放已锁槽。满槽丢新整帧并置gap/DROP_COUNT，不覆盖已锁数据。READY/LOCKED或未清故障存在则IRQ保持高，消费同拍新到达优先。驱动循环查看状态，不只依赖IRQ上升沿。

标准完整读取：ACQUIRE1＋STATUS/FRAME2＋六pair各（SELECT1＋五读）36＋CONSUME1＝40事务、1MHz纯线上1.60ms。能量/故障读取、动作配置和CS/HAL开销另计。动作可在同锁读取后、CONSUME前提交。

取消725bit K跨界传输与会话cookie；FPGA内部真实load关联保持。Lite只简化传输与快照，不授予运动权限。BIST禁止实际PWM；冷复位运动许可0；enable不是运动许可；WATCHDOG0关闭运动。COMMIT须独立许可、真实合格新结果、角度范围/轴配置合法、无故障并通过当前锁帧的新鲜度检查。重复同帧自动动作不重新接纳。顶层串接i17_turntable_pwm_guard.sv；S1完整高脉冲结束后停机，冷复位立即低。MCU/FPGA重启后丢弃旧动作，重新初始化。真实运动超时与引脚参数在S2/实物接合时明确设置。

## 6. 双BIST与S1验收

BIST只在停用、排空且槽空时选向量。enable上升触发一帧，记录bist=1、raw_valid=1、second_valid=1、PHAT/IFFT=SKIPPED、IFFT合格位0。S1诊断分支允许该合成特征算数值，动作输出资格固定0。真实帧必须PHAT/IFFT为OK且IFFT合格位1。再次BIST须消费、停用再启用。

|向量|lag|peak/left/right/second/mask|预期|
|---|---|---|---|
|拒绝|5,-3,0,1,-1,2|1000/800/600/100/79|delta全部−683；tau19797,-12971,-683,3413,-4779,7509；margin全部29491；u=(46831,−171729)；残差590912626>25165824；valid0/reason3|
|0度通过|4,4,0,0,−4,−4|1000/800/800/100/79|delta0；tau16384,16384,0,0,−16384,−16384；margin29491；u=(749295,0)；残差0；范数561442997025；valid1/reason0/angle_q8=0|

S1附加非零角、mask/有效数/数值范围/舍入/映射边界检查；整数CORDIC为正式输出，atan2f给对照，环形角差按±180°折返计算。S2随后接SPI/EXTI/串口；当前停止在S1交付。

## 7. 冻结的S2→S1→S2 C99交接

`doa_solver.h`定义唯一输入`doa_frame_input_t`和输出`doa_solve_output_t`。S2不再定义私有同名结构；各模块包含该头和共同ABI头。C结构使用字段赋值，不把带padding的内存直接作为SPI载荷，不使用packed结构跨CPU传输。

输入：frame_id取REG_FRAME_CNT；frame.flags=SNAP_STATUS_GET_FRAME_FLAGS(锁定STATUS)；pair[i].lag=FEATURE_0_GET_LAG(word)，mask_count用GET_MASK_COUNT，flags用GET_FLAGS。S2先校验FEATURE_0保留位、pair回显及S8对S6的有效符号扩展。peak/left/right/second读取完整32bit大端字，用fpga_abi_word_to_s32转换；S1再次校验S25范围。六对次序固定，原始每对flags带second_valid，不另造布尔位。

S1接受的frame.flags只含BIST、ALL_TERMINAL、FRAME_CANCELLED、FIRST_ERROR；pair.flags只含raw/second/IFFT/cancel/numeric/两阶段码，其余置0。全帧取消优先输出reason6；first_error非零或pair数值/协议错输出reason7。阶段PENDING或未知码、输入越界为API错误；算法拒绝仍返回DOA_OK并用direction_valid/reason表示。

输出每pair有delta_q12/tau_q12/margin_q15/qualified/reason；全帧有u、残差、范数、direction_valid/reason、权威angle_q8及atan2f对照。水平映射输出horizontal_servo_deg、horizontal_map_valid、servo_map_status。servo_cmd_valid=direction_valid && horizontal_map_valid && !BIST，垂直valid固定0。S2仅在servo_cmd_valid=1且硬件许可/看门狗/当前锁帧新鲜度均满足时提交；BIST可展示数学映射角度，但servo_cmd_valid始终0。

调用：`doa_solve(&frame, &servo_config, &output)`。config由应用明确提供，NULL仅关闭舵机映射；示例90°偏置不是实物标定。拒绝时输出角度/动作载荷归零并valid=0，禁止把无效0°当目标。

## 8. 交接实施要求

FPGA组：按F1a数据/终态接口、寄存器及BIST实现并打印六对表；保留S1高脉冲末端保护。STM32组：S1完成纯C99 PC验收，S2再实现SPI/EXTI/串口，不在两个模块各自改一份协议。头文件中的所有位域宏与本文件一一对应。当前只有本组PC实测，FPGA侧按同一双BIST表交接。
