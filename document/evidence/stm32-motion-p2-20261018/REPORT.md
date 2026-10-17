# P2 水平动作管理验证结果

日期：2026-10-18。任务分支 `codex/stm32-motion-p2`，父提交 `139a8dab548edfcf05f29f01d23f17ac40b8b453`。本记录与实现一起提交；作者软件验证，不是独立审阅、RTL仿真或板测。

## 修改与结果

新增 `ss_motion.h/.c`，在同一 LOCKED 帧内读取、S1 解算映射、核查、影子写入、COMMIT、检查和CONSUME。S2增加私有同一deadline组合入口及受编译门禁保护的水平写入；原公共API未变。许可和watchdog显式配置，失败进入隔离，恢复保留已尝试提交的帧号，避免不确定写入被重复执行。

冻结ABI/S1、P1源文件、RTL、Keil和板级物理门禁未改。动作编译门禁默认0，只有PC模型的独立开启构建传入`SS_ENABLE_MOTION_WRITES=1`；现有固件没有启用动作。

|输入／场景|预期|实测|
|---|---|---|
|真实模式合成0°特征，90°偏置|水平90°，同锁提交后消费|目标90°，模型接受1次，消费1次；58事务，第55次COMMIT，第58次CONSUME|
|合成+90°／−90°|水平180°／0°，每新帧一次|angle_q8=23040／−23040，目标180／0；仅新接受动作更新模型watchdog|
|默认编译关闭／运行配置不允许|不写shadow/permit/commit或非零watchdog|默认配置43项检查、0失败；STOP仍可用|
|58事务每位置 × 生效前后 × IO/timeout|隔离、无输出、不重发不确定提交|232组通过；保留尝试帧号，显式恢复后同帧仍不能重新提交|
|arm/disarm/STOP逐事务同类故障|失败传播、无动作接受|68组通过|
|不确定提交后的recover逐事务同类故障|隔离保留、无COMMIT/CONSUME重放|40组通过，合计340组通信故障组合|
|残差拒绝、BIST诊断帧、取消、映射域外|不COMMIT；撤销许可后消费诊断，转DISARMED|预期符合|
|持锁超时、整操作预算、影子回读错误、锁帧号变化|提交前拒绝，无动作接受|预期符合|
|COMMIT同拍许可丢失／源故障；接受后watchdog过期|模型硬件拒绝或撤销；软件报告不确定并隔离|预期符合|
|模型静默忽略COMMIT且不报错|不能声称动作接受|只报告SUBMITTED_UNCONFIRMED；模型accepted=0，软件未生成伪ACK|
|无帧、连续有效帧、重复arm、STOP、错ID恢复、卡住的锁槽|空轮询不续期、重复arm无写、STOP不重发、恢复失败保留隔离|预期符合|

最终开启模型：[motion-1.log](motion-1.log)，**74240项、0失败**。默认关闭：[motion-0.log](motion-0.log)，**43项、0失败**。断言数量包含每次总线的时限与读包检查，不等同于独立场景数。

编译：[GCC默认](compile-motion-0.log)、[GCC开启模型](compile-motion-1.log)；严格C99、O2、全部所启用警告视为错误。AC5严格C99/microlib/Cortex-M4.fp.sp/O2：S2/P2的默认与开启配置均对象编译通过，日志 `armcc-fpga_link-0/1.log`、`armcc-ss_motion-0/1.log`。没有链接新固件、测量板端运行时间或操作执行器。

原路径回归：S1 **4705项**、S2 **15980项**、P1 **26561项**均0失败；五种统一自检主机模型分类符合预期。见 [S1](regression-s1.log)、[S2](regression-s2.log)、[P1](p1-runtime.log)、`regression-host-*.log`。no_peer/dead_tick/bad_config仍被正确分类为预期失败，不计成硬件通过。

## 首错与修复

首轮默认配置PC检查通过；AC5把`if (SS_ENABLE_MOTION_WRITES == 0) return`后的动作验证分支诊断为不可达语句，warning-as-error使编译退出1。原件：[armcc-fpga_link-0-first-failure.log](armcc-fpga_link-0-first-failure.log)。改为编译期`#if/#else`门禁，高层通过构建查询函数判断；没有关闭警告或放松默认门禁。修正后双配置编译通过。首轮开启模型66222项行为检查已通过；补充恢复矩阵和竞争边界后最终74240项通过。

## 复现与公开边界

仓库根目录执行：

```text
python software/stm32/tests/run_motion_tests.py --armcc <armcc.exe绝对路径>
python software/stm32/tests/run_runtime_tests.py --armcc <armcc.exe绝对路径>
python software/stm32/tests/run_host_tests.py
```

每条展开命令位于对应日志首行。P2 runner保存退出码和首错，任何编译或用例失败均以非零退出。GCC使用项目现有tools.local.env/环境变量/PATH约定，未写入新的个人路径默认值。没有创建codex_out临时副本或封包；源码归入software，说明/必要记录归入document，忽略的可再生成程序及对象位于software/stm32/build/motion-p2。

冻结协议没有动作接受回执或采集时间戳。因此提交完成只报告UNCONFIRMED，持锁期限只约束本次MCU操作，READY队列内的真实帧年龄仍未知。机械参数与watchdog示例也不是实物配置接受。详情见 [P2使用说明](../../../software/stm32/MOTION-P2.md)。

## 下一步P3

将P1/P2接成一个取帧所有者，接合参数、串口状态、重复／不确定帧的显式诊断处置，完成AC5固件构建，保留物理写门禁。随后由用户下载取得新本板结果。

本轮只读父提交中的`ss_control_regs.sv`发现：STOP置`stop_latched`，未直接清`sys_ctrl[0]`，但P1现有停止确认及旧模型期待STOP后enable=0。**P3需对齐A当时的准确RTL，修正停止确认步骤和模型**；现有PC回归不覆盖这个真实接合差异。P2只报告STOP传输完成，没有作“生产者/PWM已停止”的判断。本批不修改A的RTL或单方扩展ABI。
