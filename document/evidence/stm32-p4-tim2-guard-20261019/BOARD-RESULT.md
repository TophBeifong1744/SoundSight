# P4_TIM2_GUARD_V2 实板回测：第二组BIST取帧格式拒绝

2026-10-19。用户提供[串口全文](user-uart-retest.txt)，明确尚未加入A的FPGA修改。标记P4_TIM2_GUARD_V2正确；STM32对应9c08dce。用户未提供本次PL准确映像身份/冷复位记录，不将其补写为已确认。

|项目|本次实测|
|---|---|
|BOARD_ONLY|13通过/0失败/11跳过|
|FPGA_DIAGNOSTIC|20通过/3失败/5跳过，FAIL|
|ID/ABI|0x5A5A2026 / 0x00010000，PASS|
|两次启动|均step13，SYS_CTRL期望/实际0x0B，result0/recovery0|
|第一组拒绝BIST|40事务，frame1，ux46831/uy-171729，残差590912626，valid0/reason3，PASS|
|第一组快照/IRQ|释放后同帧重读、消费后IRQ低和EXTI边沿，PASS|
|第一组取帧+解算耗时|3084us / 394804 cycles，含主机处理；不是纯线上时间或最坏时延|
|第二组通过BIST|启动成功后ACQUIRE,status=8；取帧失败，未完成本次向量数值验证|
|后续测试|REMAINING_FPGA_TESTS跳过；超时注入/显式恢复未执行|
|安全读回|act/watchdog/fault均返回12；INVALID_READBACK，不能使用数值|
|末尾状态|last_error8/recovery1；APP fault0为缓存，不证明PL当前无故障|

## 首错的准确含义

8是STM32驱动的SS_WIRE_FORMAT枚举，不是FPGA FAULT_STATUS的bit3。`wait_frame(1)`调用`ss_acquire_frame`，进入`acquire_inner`，读回若不满足下列任一检查则返回8：

- SNAP_STATUS保留位、profile支持、锁定快照完整终态、非BIST能量能力一致性；
- 六对FEATURE_0保留位、pair回显、PHAT/IFFT终态枚举、lag范围和mask_count上限；
- 四种相关值S25范围/有效符号扩展；
- 六对raw_valid与快照valid_pairs汇总一致性。

日志没有保存触发失败的寄存器地址、pair编号、原始值或具体断言，所以不能从枚举8定位到以上哪一项。两次START_TRACE只记录ss_start，不覆盖acquire_inner，成功step13不能排除后续读回错误。算法还没拿到完整第二组输入，不能将此称为0°算法计算错误。

`fail()`保存错误并隔离；随后三项安全读回返回SS_RECOVERY_REQUIRED=12，两项安全FAIL属于连带结果，不是已测得运动保护失效。后续未有效读回FAULT_STATUS；末尾0来自较早缓存，不能证明原0x41已经清除或不再出现。

## 与上次比较及下一步

上次V1为26/3/4，第二组也通过，第三次prepare检出0x41。本次V2为20/3/5，在第二组读取时较早退出。计数降低主要反映执行范围减少；单次结果不能推导故障率变高，也不能证明延时修正无效或故障根因已闭环。已修正的TIM2最小等待漏洞仍是成立的软件问题，但尚不足以证明实际总线稳定。

把本记录和原文提供A，供其核对第二组BIST快照封存/选择与SPI返回数据。FPGA同拍fall修正尚未加载，需按A交付同步回测；该修正主要补拒错条件，不能预先声称必然修复本次SS_WIRE_FORMAT。

下一定位应补取帧首错的RAM记录：具体校验编号、地址、pair、原始32位读值及掩码/预期，在返回后打印，避免SPI事务中串口干扰；优先复用现有事务，不新增读写、放宽检查或自动重试。这是建议的下一软件小批，本次没有实施。也可并行抓CS/SCK/MOSI/MISO，区分读回传输与载荷生成问题。

本次只核对源码、分析和归档，未改固件/RTL，未构建或操作板卡。保持动作关闭，暂不运行stream。P4仍为故障待定位，已通过项目保留。
