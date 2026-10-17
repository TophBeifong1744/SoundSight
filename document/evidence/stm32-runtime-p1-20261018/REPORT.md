# P1 独立运行状态机验证结果

日期：2026-10-18。任务分支：`codex/stm32-runtime-p1`，父提交 `9967958276e174934ab4c12ce5b14bdce41c6010`。本记录随实现同一提交保存；不是独立复核或硬件验收记录。

## 改了什么

新增 `ss_runtime.h/.c`，复用原 S1/S2，实现启动、周期等待/取帧、停止与排尾回读、故障隔离、显式恢复和原会话继续。结果仅供诊断，已经单次消费；动作不提交。冻结 ABI、S1/S2、FPGA RTL 和原 Keil 固件未修改。

核心行为：通信错误进入 FAULT 后不自动访问总线，恢复只读回真实槽状态并在必要时 RELEASE，不重发 CONSUME；成功恢复先停在 IDLE，必须显式 start/resume。resume 只能继续设备仍启用的原模式。STOP 发送完成和生产者已停止分别记录，不能从传输成功推断 PWM 实物状态。

## 输入／预期／实测

|输入／场景|预期|实测|
|---|---|---|
|原拒绝 BIST|ux=46831，uy=-171729，残差590912626，valid=0/reason=3|全部一致，消费1次；总41事务（fault检查1＋原单帧40）|
|0° 通过 BIST|ux=749295，uy=0，残差0，valid=1/reason=0|全部一致，消费1次；总41事务；不输出动作|
|有效/残差拒绝/取消/来源错误连续四帧|分别报告原方向原因，每帧消费一次|4次消费，拒绝计数3；重复帧及恢复后的重复帧不再消费|
|每个取帧事务，生效前/后，IO/timeout|隔离，清结果，无自动重试；恢复不消费|164/164组合通过，包括CONSUME已生效但返回失败|
|probe/start/stop/drain/recover/resume的每个事务同样注入|错误传播，无自动重试、无动作写入|140/140组合通过|
|两帧连续READY，IRQ保持高|无须新边沿即可逐帧读取|帧1、2各消费一次|
|无帧、忙队列、排尾、超时、回绕、错误身份、保留位|有界等待、正确拒绝；未识别设备无写入；sticky fault不清除|预定检查通过|
|动作安全|不写ACTUATOR_CMD，不发PERMIT/COMMIT，WATCHDOG只写0|所有覆盖场景符合|

最终输出：[runtime.log](runtime.log)：**P1_RESULT,PASS,checks=26561,failures=0**。其中包含模型对每次总线调用的时限及写入检查，断言数量不是独立测试场景数量。

- GCC 严格 C99 编译通过：[compile-runtime.log](compile-runtime.log)。
- ARM Compiler 5.06 update 7，Cortex-M4.fp.sp / C99 / microlib / O2 / strict / warning-as-error，**仅P1对象编译通过**：[compile-armcc.log](compile-armcc.log)。未链接/生成新固件，未测P1板端耗时和栈水位。
- 既有 S1：4705项、0失败：[s1.log](s1.log)。
- 既有 S2：15980项、0失败：[s2.log](s2.log)。
- 统一自检主机模型五种分类符合预期：[board](host-board.log)、[live](host-live.log)、[no_peer](host-no_peer.log)、[dead_tick](host-dead_tick.log)、[bad_config](host-bad_config.log)。后三种是预期故障分类，不是被测设备正常通过；live也只是软件模型。
- 本轮首次P1运行即通过（20921项）；补充生命周期/边界覆盖及可见残差后最终26561项通过。没有本轮编译／测试失败原件需补存。

## 运行命令

仓库根目录，配置本机 GCC 后：

```text
python software/stm32/tests/run_runtime_tests.py --armcc <ARM Compiler 5 armcc.exe的绝对路径>
python software/stm32/tests/run_host_tests.py
```

每个编译及运行的实际展开命令在对应日志首行。P1 runner 保存退出码，编译／运行失败会抛错并以非零退出；若发生失败，首份失败日志另行保留。工具路径未写入公共默认配置。

## 下一步与保留项

P1范围为独立控制软件；不冒充非作者审阅、RTL仿真、真实SPI/IRQ或新的STM32本板测试。原本板11通过/0失败/11跳过的事实不变。P2为水平动作命令管理，P3统一固件接合，P4/P5再做真实跨板和闭环。三维继续保留暂停。

必要记录已归入本目录；本任务未新建codex_out副本、压缩包或外部工程，没有需要删除的临时工作副本。可再生成的测试程序和P1对象留在约定的Git忽略目录 `software/stm32/build/`，不公开提交。main未合并。
