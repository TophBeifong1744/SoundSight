# PR #15 / #16 接合检查与 PYNQ 首次上传包

用户授权：接合检查、必要测试通过后合并两个PR，整理软件及实际bit/HWH，再分步指导目标板运行。

## 候选与结论

- PR #15：`61e7303331641ec2353f89088b060aa81ffd6110`。
- PR #16：`0d388586af1dcd0355a2ab9d51360d4a9fb249cf`。
- 原main：`ade821b49551d33b764fc44a04e24fe36b7ee9fd`。
- 隔离工作区：仓库内 `software/build/pynq-integration`，任务分支 `codex/pynq-integration`。原工作区未提交的BD脚本/说明保留。
- 两PR无冲突接合，组合树与正式合并后的main内容一致。
- PR #15合入：`0fd831c`；PR #16合入：`6482d52913cbc6a4c806fa09e80b31b72be61ee0`。

M未参与这两个PR的实现，本次从现有ABI、取帧/停止和保存合同核对代码并重跑测试，接受其**离线软件接合范围**。没有修改B的算法/桥、C的生产运行程序或作者测试。合并没有被描述成GitHub原生Approve、ARM通过、实板通过或双轴完成。

## 核查预期与实际代码

- 同一个Linux的两核、两个进程；worker独占MMIO和文件锁，host不写硬件。
- 每个快照只有一次C求解；保存结果、收到当前记录ACK后才可继续动作/消费。
- 保存失败、ACK错配/超时、进程断连、取消和求解错误请求STOP，未消费帧保留。
- 历史故障不再无条件全部清除，恢复不重放旧动作。
- 当前目标ACTUATOR_BOUND=0；双轴ABI缺件不阻断不运动的BIST/取数验证。

代码满足上述接合预期，作者测试有实际失败场景覆盖。本次使用真实spawn/Pipe和假MMIO的测试；Linux实际affinity仅有注入OS接口检查，不能冒充目标板双核运行。C代码或驱动完全挂死时不能保证软件STOP已送达，既有代码有明确未确认报错。

## 实际测试

环境：Windows AMD64、Python 3.14、MinGW GCC 16.1.0。

在隔离工作区执行：

```text
python -E -s -B -X utf8 software/tests/test_smp.py
python -E -s -B -X utf8 software/tests/test_application.py
python -E -s -B -X utf8 software/tests/test_software.py
python -E -s -B -X utf8 software/tests/test_solver_migration.py --golden document/evidence/ps-solver-migration-20261020/PC-RESULT.json --output software/build/integration-review/PC-INTEGRATION-RESULT.json
python -E -s -B -X utf8 software/ps/run_smp.py --help
```

结果：双进程17项、应用8项、S1 4705项断言、桥接/客户端9项、数值对照157组、非法桥输入6组全部通过。对照使用B保存的完整输入和PC基准，未降低精度、改公共接口或扩大超时。

从生成的ZIP解压到独立目录后，再运行包内双进程、应用及数值对照测试，均通过，验证包的相对路径和依赖闭合。Linux共享库尚未生成，包内无DLL、EXE、SO、工具本机配置或工作区缓存。`build_solver.sh`为LF换行。

`tools/pynq_preflight.py`在PC正确识别实际HWH的0x40000000/4KiB和ACTUATOR_BOUND=0，并拒绝将Windows环境当作ARM/PYNQ；此退出1是预期负例。它没有导入MMIO或下载位流。目标板成功分支仍待真实环境执行。

日志在本目录；部分原始子进程中文stdout存在编码显示问题，保留原记录，英文PASS/断言数量与JSON结果可核。完整157组输入/输出复用PR #15，不再在Git重复一份；本次摘要见NUMERICAL-SUMMARY.json。

## 硬件接合

只读A的 `F:/AMD/work/SoundSight_PS`：

- bit：`SoundSight_PS.runs/impl_1/soundsight_stm32_bd_wrapper.bit`，4045703字节。
- HWH：`SoundSight_PS.gen/sources_1/bd/soundsight_stm32_bd/hw_handoff/soundsight_stm32_bd.hwh`，266500字节。
- 同次XSA：`pl_pynq.xsa`；内嵌bit和HWH与以上两个文件逐字节一致。
- 实际HWH由C候选的地址解析器读取成功：ps_link、0x40000000、4KiB、61.44MHz、ACTUATOR_BOUND=0。
- 用户布线后报告WNS +0.278ns、WHS +0.036ns，setup/hold失败端点0。DRC有流水线、RAM异步控制等警告及规则条数上限提示；未宣称零警告或全量CDC/RDC核查完成。

实际报告随上传包的reports目录提供。没有运行Vivado构建、访问板卡、复位或动作。

## 包与后续

正式入口 `release/output/soundsight_pynq.zip`，共28个文件，顶层 `SoundSight_PYNQ`。生产软件、冻结ABI/S1、ARM数值测试、PC基准、只读环境检查和配套bit/HWH齐备。README引导先环境检查，再ARM离线求解，之后才接PL和双BIST。第一次打包的报告通配符同时匹配DRC和methodology报告，脚本已改为按bit顶层名选准确报告，未改写原报告。

新工具/说明在正式目录，必要证据在本目录；没有创建codex_out。测试输出在software/build，发布ZIP在release/output，均不是第二套维护源码。当前工作区原有未提交BD资料未覆盖。本包不包含XSA/Vivado缓存、Windows编译产物或STM32/Vitis裸机运行文件。

未测：ARM编译/数值与耗时、Linux真实双核绑定、PYNQ寄存器访问、BIST与实采、持续服务/停止恢复、舵机与双轴闭环。用户已确认PYNQ能够启动，不等于这些项目已通过。
