# D1 三维应用接合与诊断

2026-10-18。状态：PC整帧接合完成，AC5源文件编译通过；三维完整固件链接被本机链接器容量限制阻断。没有三维AXF/HEX可下载。二维Template完整构建通过，原二维默认行为保留。

## 现在提供了什么

- 新 `include/ss_spatial.h` / `src/ss_spatial.c`：同一S2锁帧内读取六对→三维解算→CONSUME。读、计算、消费共用原始整帧时限，成功一次消费；通信/解算API错误隔离，结果清零，不盲目重试消费。
- P1/P3按 `SS_DOA_PROFILE` 选择二维或三维诊断路径，仍只有一个取帧所有者。三维结果独立存入 `spatial_result`，不把俯仰或三维原因码塞入冻结二维结构；三维时旧planar结果保持零。
- 三维配置暂为40mm标称正四面体、48kHz、coordinates_measured=0，不提供本轮坐标编辑入口，交D2完成。
- 原双BIST仍调用原二维S1，用于二维数值/传输核对，标记 `legacy_BIST=PLANAR_TRANSPORT`。三维流中收到旧BIST，返回 `DOA3D_LEGACY_BIST` 拒绝且只消费一次。
- 独立三维目标的board检查增加45°/+30°、-45°/-30°、正上方三组合成特征；输出方位/俯仰Q8、各自valid、原因、DWT/TIM2耗时和标称几何来源。它们不访问SPI，不等于麦克风或真实声学验证。
- 附带修复P3共有问题：统计读取在同一HAL毫秒内失败时，runtime必须先处理恢复隔离，再执行轮询节流；否则recover之后可能仍停在RUNNING。二维/三维定向负例均已通过。

没有修改冻结ABI、原二维/三维求解器、FPGA RTL、128MHz时钟或板级门禁。

## Keil两种目标

同一工程 `keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx`：

|目标|用途|输出和本机状态|
|---|---|---|
|Template|原二维主线；SS_DOA_PROFILE默认0|build/keil/atk_f407.axf及hex，0错误0警告；仍待用户新板端记录|
|Tetra3D_Diagnostic|SS_DOA_PROFILE=1，所有相关编译单元一致；动作编译门禁0；O2尺寸优化|build/keil-3d/，源编译通过，但33936字节映像触发本机链接器L6047U限额；未生成AXF/HEX|

两种目标使用同一份源码，独立输出目录，不复制第二套工程。下载二维固件前明确选Template，避免GUI记住上一次目标。只读检查确认本次armcc/armlink报告MDK-ARM Lite 5.36；这不判断用户是否另有授权。三维目标需要能够链接该大小映像的合法AC5授权，或另行确定并验证其他工具链；本批没有改许可证或安装环境。

初始无优化三维代码38258字节，O2映像33936字节，O3仍33976字节且同样受限。最终保留较小O2。不能把F407容量与工具许可上限混为一谈，也没有为满足限额删掉检查或替换数值算法。

## 三维入口的边界

三维完整构建成功之后，启动或`board`预期16 PASS/0 FAIL/11 SKIP（二维仍13/0/11）。这两个新数值目前都仅有主机模型预期；用户旧本板记录仍11/0/11。

三维固件`stream`当前明确输出：

```text
STREAM,SKIP,THREE_DIMENSIONAL_PROFILE_NOT_ALIGNED_WITH_A
```

这是D5待办：尚无实物及A确认的三维通道、lag符号、窗口/频带配置，不能直接将当前方形阵列输入按四面体解释。PC寄存器模型已独立执行真实S2/P1/P3三维路径，门禁不掩盖软件接合测试。`fpga`仍仅为原冻结传输/二维BIST诊断，不能认定三维硬件合格。

三维APP禁止arm，编译开启 `SS_ENABLE_MOTION_WRITES=1` 会被ss_spatial.c拒绝；既有板级动作拦截保持。没有水平或垂直动作提交。`discard`仍是显式诊断消费，不能拿其结果补交动作。

## 输出与预算

- 只在帧事件且fresh为真时读取frame/spatial_result。无帧/错误时不能使用历史方向。
- 成功裸三维读解消费40事务，P1含提前fault检查41事务，P3再读DROP_COUNT共42事务，与二维诊断预算一致；求解时间仍属于整帧时限，不能重置deadline。
- `direction_valid=1`不保证方位角有效：正上/正下方 `azimuth_valid=0`，俯仰有效。三维原因码使用DOA3D枚举，不能按二维reason解释。
- 三维使用double运算，F407无硬件双精度。PC时间/主机HAL模拟值不能当板端耗时；未测板端性能、实际栈高水位或声学精度。
- ABI没有采集时间戳和动作ACK的限制保持。几何标称不等于实测。

## 验证命令及后续

仓库根目录：

```text
python software/stm32/tests/run_spatial_app_tests.py
python software/stm32/tests/run_app_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_runtime_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_host_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <二维构建日志>
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Tetra3D_Diagnostic -o <三维构建日志>
```

结果：[D1记录](../../document/evidence/stm32-spatial-d1-20261018/REPORT.md)。后续可独立推进D2几何配置；三维完整链接需解决本机工具限额。D3回放、D4双轴软件映射、D5跨板合同与D6实物验证均在[原进度表](../../document/STM32-MODULE-PROGRESS.md)，本轮不同时执行。

D2后续增量已完成配置软件与PC验证，见[几何配置](GEOMETRY-D2.md)。本文33936字节属于D1旧候选，不是加入D2后的映像大小；三维完整链接仍待条件。
