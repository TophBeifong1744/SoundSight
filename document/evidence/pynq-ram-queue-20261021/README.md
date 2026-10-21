# RAM队列修复自测

批目标：解除SD逐帧同步与PL槽释放的直接耦合；用户接受断电丢未落盘RAM记录，要求队列接近满时停止新增并保已有记录。限无动作路径，不改变RTL、冻结ABI、C数值、采集周期、STOP/硬件握手语义。

## 实现与预期

- `software/ps/ram_queue.py`：有界RAM文件队列；完整写入才确认接收；SD fsync成功才删RAM项；在写项仍计容量。实际运行要求`/dev/shm`为tmpfs，打印swap平台状态，不自动更改系统配置。
- `software/ps/run_buffered.py`：CPU1独占MMIO和C求解；CPU0接收/控制及独立写盘线程。ACK采用queued语义，旧saved ACK不能混用。默认容量64、高水位48；保留在途/双槽排尾/结束信息容量。输出独占新建。
- `software/ps/recover_ram.py`：失败退出后把完整RAM项复制到新SD日志，原件保留，不访问硬件。
- 旧`run_smp.py`、`run_capture.py`、`ps_client.py`及所有C/RTL/IP/XDC/bit/HWH均未修改，旧动作路径仍要求durable-before-consume。数值算法复用已有验证，本批不重复冒充新的ARM数值结果。

## 实际执行

在Windows开发机执行，均为假MMIO，不导入PYNQ、不加载位流、不访问硬件：

```text
python -E -s -B -X utf8 software/tests/test_buffered.py -v
python -E -s -B -X utf8 software/tests/test_smp.py -v
python -E -s -B -X utf8 software/tests/test_application.py
```

结果：新增16项unittest通过，既有双进程17项通过，应用8项检查通过。命令及真实结果见`RESULT.json`及三个同名log。Python3.8语法解析通过；这不是在Python3.8或ARM上执行的替代证据。

新测试使用真实spawn/Pipe和写盘线程，独立假MMIO在CONSUME时检查完整记录确实存在于RAM或SD文件，不仅检查函数调用次数。35ms延迟的写盘仍可完成请求帧并保存双槽尾帧；容量7、高水位3的测试提前STOP，记录保持有序且峰值不超容量。覆盖在写项占用容量、SD失败/RAM失败、超限记录拒绝、FIFO、超时、错误确认、Ctrl+C排尾、求解失败不消费、运动入口拒绝、RAM恢复不删原件/不覆盖输出。

测试中的帧数、写盘延迟和小容量是注入条件，不能作为实板吞吐或Linux最坏延迟证明。新程序可接受队列后释放槽，但Linux失调度、RAM压力、驱动/C库挂死依然可能超过硬件服务余量；持续过慢会高水位停止，不宣称无限连续或零丢帧。

## 包与交付核对

生成命令：`python tools/package_pynq_ram_update.py`。增量只有三个新运行文件、一个自测文件和操作说明，ZIP根目录为`SoundSight_PYNQ`，不覆盖旧入口、C共享库、bit/HWH或用户日志。生成器拒绝覆盖已有同名ZIP。

交接自测将现有`soundsight_pynq.zip`解压到仓库内临时测试目录，再叠加本次增量，从解压位置运行新增自测；结果见`package-check.log`及`PACKAGE-RESULT.json`。临时解压目录检查路径范围后清理，不保留第二套产品源。

软件交付时，板上新增入口、100帧复验、高水位实板行为均为**NOT_RUN**；本目录RESULT.json保留该次自测原始状态，不倒改为板测结果。该次没有启动XSim/综合/实现/下载/复位或执行器。现有板测失败保存在相邻`pynq-board-20261021`，不因本机自测通过而删除。此处是作者自测，不自称独立复核或整机验收。

后续用户已在板端运行16项自测、通过BIST及100帧无动作实采：程序报告100帧落盘、DROPS=0，无高水位提前停止。真实回传及边界见[板测接续](../pynq-board-20261021/README.md#ram队列实板接续)。高水位实板行为、长期稳定性与整机闭环仍未完成。

## 启动等待修复接续

002轮未ready即超时且输出文件为空。板端CPU1独立测得PYNQ导入4.589秒、C库加载0.005秒，初版5秒总启动上界余量不足。只在`run_buffered.py`独立采用20秒启动等待，增加导入前/身份读取前阶段提示及未ready超时说明；不修改旧run_smp入口、ready后750ms消息等待、250ms取帧/ACK/STOP、数值、硬件或运动行为。

新增3项定向自测：模拟6秒启动在旧5秒预算下失败、新预算下通过；永不ready仍在20秒终止等待；ready后继续使用750ms失联检测。原16项继续通过，总计19项，见`startup-fix-tests.log`。原上传包用`python -c`单次覆盖START_TIMEOUT=20的路径也已验证：真实spawn的假worker延迟5.2秒，正常结束；见`startup-wrapper-test.log`。均为PC假硬件结果，不代表已复验实际ARM启动。

正式增量入口仍为`release/output/soundsight_ram_queue_update.zip`，已更新为含19项测试的版本，原包与更新包叠加解压后自测通过，见`startup-package-test.log`与`STARTUP-RESULT.json`。先前的`PACKAGE-RESULT.json`和16项日志保持原文，对应的初版小型ZIP保存在`before-startup-fix.zip`（约16KiB），用于复现本次启动边界失败和已有板测软件；不是另一套维护源码。未留下临时解压目录或`.next.zip`。

板上当前仍可使用初版文件，通过操作说明中的单次命令先验证20秒启动等待；该命令不永久改板端源码，也不会带来新增WORKER_STAGE提示。当前完整修复文件和后续正式上传包一致，不能把临时启动覆盖说成已更新了板端全部文件。
