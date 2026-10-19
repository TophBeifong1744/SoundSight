# V3再次实测：读回一致性/BIST数值失败，有效读回0x41

2026-10-19；[本次用户串口原文](user-uart-retest-2.txt)。用户称再次测试，沿用P4_ACQUIRE_V3，上一轮已说明加载A修改；本轮未额外提供映像变更或复位记录。STM32产品没有新增修改。

## 与上轮的区别

|项目|上轮|本轮|
|---|---|---|
|BOARD_ONLY|13/0/11|13/0/11|
|FPGA_DIAGNOSTIC|14/3/5|18/4/5|
|第一组取帧|check6：请求pair5读回pair4，status8|初次取帧及释放后取帧均返回成功；没有ACQUIRE_FORMAT|
|释放后同帧检查|未执行到|FPGA_RELEASE_SAME_FRAME FAIL|
|标准BIST数值|未完成|FPGA_SPI_BIST_REJECT FAIL|
|消费后IRQ检查|未执行到|FPGA_IRQ_AFTER_CONSUME FAIL|
|最终安全读回|返回12，被隔离，fault0仅旧缓存|三读返回0，act0/watchdog0，实际读回fault0x41|

本轮拒绝向量计算：

|字段|冻结预期|实测|差值|
|---|---:|---:|---:|
|ux_q20|46831|47037|+206|
|uy_q20|-171729|-171934|-205|
|残差平方和|590912626|590892309|-20317|

valid0/reason3仍一致，不能抵消其他精确数值不符。S1本板同向量数值通过，而跨板输入的解算不符合标准；应先查实际输入/读取链，不能凭本日志归责于S1数学实现。

## 可以确认与不能确认的事项

1. 不是上次完全相同的首错。本次没有观察到pair校验拒绝，不能说pair5读回pair4已再次被证实，也不能因此宣布已修复。
2. `FPGA_RELEASE_SAME_FRAME`比较的是frame_id相等且完整输入结构体相等；FAIL说明这一组合不成立。日志未打印两份全部字段，所以不能指出哪个pair/相关值变化，也不能仅凭此认定FPGA存储槽发生写覆盖。
3. 本次40事务/status0表示主机回调和输入格式检查通过；不是逐写ACK，不证明FPGA接受了每次SELECT/CONSUME，也不证明线上没有错位或内容错误。范围合法的错误数值仍可通过格式校验，由同帧/BIST标准检查发现。
4. `SAFETY_READ_STATUS`中act/watchdog/fault三个0是API成功状态；下一行`DATA,SAFETY,...fault=0x00000041`才是本次读取的故障值。末尾APP fault0是另一时刻缓存，不覆盖该有效读回证据。
5. 0x41包含SPI_FORMAT和STOP。测试在BIST失败后主动调用ss_stop，再做safety_readback，所以STOP记录可以来自测试收尾；日志不能精确定位SPI_FORMAT首次出现在哪个事务。不能把它自动归因于最后一次CONSUME，也不能断言它一定早于IRQ检查。
6. 消费后IRQ检查同时要求状态与引脚一致且引脚为低；未清故障本就可保持IRQ高，因此此FAIL不单独证明CONSUME没生效或IRQ硬件损坏。真实波形/状态需继续定位。
7. link.last_error0/recovery0只是未发生驱动级错误。本轮失败由自检的同帧/标准值/IRQ/故障断言发现，并执行STOP；并不代表整轮正常，也不代表动作启用。实测动作许可与看门狗均0。第二组BIST和超时注入/恢复均未执行。

## 对ILA建议的判断

两次表现可能来自同一条SPI选择/提交/读回链路，但尚不能证明同根因。STM32日志能确认收到的结果，不足以区分内部提交被拒、选择未更新、读mux/快照错误和输出采样异常。

ILA不是逻辑上唯一方法（受控仿真、外部SPI分析或内部调试寄存器也可提供证据），但针对当前间歇实板现象，A加ILA观察PL内部路径是合理、优先的下一步。重点由A安排：

- 触发format_error，保留事前的CS/SCK同步状态、位计数、malformed、edge_age；
- 同时看commit、write_access、address、write_data、pair_select及read_pending/read_data/tx；
- 覆盖SELECT→读FEATURE/相关值→RELEASE/重读→CONSUME的关系。深度不够时分段抓，避免只看错误脉冲而缺少触发前的写入；
- 对照用户STM32日志与准确的bit/LTX/source版本。ILA采样不等于模拟电气质量检查，必要时配外部仪器。

当前应保留V3，不再盲目改算法、加延时或清混合故障。下一由A准备ILA候选/触发方式，现场人员加载并配合运行原fpga流程，B分析对应串口及波形。本次只分析归档、无产品/RTL/构建/板卡操作；原用户Keil修改保留，不创建额外工程副本、不删除文件。
