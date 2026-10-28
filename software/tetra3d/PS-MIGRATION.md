# 三维算法的 ARM Linux 接口

2026-10-28新增独立在线和双轴候选，日常入口为`soundsight-3d.sh`；测角、无声手动和H/V跟随使用方法见[完整操作说明](../../document/pynq-three-d-dual-axis.md)。本页保留底层库/数值复现方法，ARM与实际声源尚未验证；软件包不含未生成的新bit/HWH。

三维专用源码、入口和测试集中在 `software/tetra3d/`，现有二维发布包不自动包含它。

实施顺序以[当前接合方案](../../document/tetra3d-integration-plan.md)为准：2026-10-28用户改为A推进三维、B继续声纹，并行开发，不再等待声纹完成。下文接口与编译步骤继续适用；原交付中C承担的三维接入由当前A侧接续，不能据旧人员称谓重新派工。本次进度核查没有执行板端动作或修改Vivado工程。

2026-10-25 新增独立[三维 DAS 定向拾音](das/README.md)：几何延时、Solver3D 结果接合、连续 PCM 分块及离线 WAV 导出，16 个 PC 测试通过。需要连续四路 PCM；本页六对定位特征不能直接用作音频输入。尚未接入 PYNQ 在线应用或完成 ARM/实物声学验证。

二维主线保持原库 `libss_solver.so`、`Solver` 与原运行脚本。新增三维库 `libss_solver_3d.so`、`Solver3D`；**不能只替换二维库文件名就运行三维**。六对输入线格式可复用，结果新增Z、俯仰及独立有效位，C须显式接入这些字段。当前 `run_capture.py/run_smp.py` 仍走二维，未在本批改成三维。

## 1. 在目标 PYNQ 编译和离线验收

从仓库根目录执行，Python≥3.8、GCC C99、libm。不依赖STM32、PYNQ导入或PL就绪，不触碰MMIO/复位/动作：

```sh
sh software/tetra3d/linux/build_solver_3d.sh
python3 software/tetra3d/tests/test_solver_3d_migration.py \
  --library software/tetra3d/linux/libss_solver_3d.so \
  --golden document/evidence/ps-tetra3d-migration-20261021/PC-RESULT.json \
  --output software/build/tetra3d-migration/ARM-RESULT.json
```

测试返回原二维选择2110项、三维选择2378项、双轴软件映射92270项通过，以及 `MIGRATION_3D_PASS equivalence=154 bridge_negative=28 geometry=15 motion=DISABLED` 和 `PS_CAPABILITY_PASS equivalence=155 reserved_bits_checked=6,21,22,23`。不要加 `-ffast-math`；使用本机GCC即可，不需要AC5授权。Windows生成的DLL不能复制成ARM .so。

2026-10-25本地修复：PS专用C桥接受STATUS bit18（`0x00040000`）所表示的手动接口能力。这不是动作许可，不进入算法帧标志；冻结STM32/SPI头不变。其余保留位、LOCKED、配对次序与数值检查继续生效。新增测试用同一帧对比能力位有无，覆盖成功、算法拒绝、取消及旧BIST；另覆盖实际PS状态位组合`0xf7f31`。本机测试已通过，但尚未执行本次ARM/实板组合。详见[本地修复记录](../../document/evidence/tetra3d-review-20261025/local-fix/README.md)。

PC基准和目标结果逐对RNE整数、margin64、资格/原因/有效性必须一致；浮点容差为abs 1e-5或rel 2e-6，Q8角允许1 LSB。它验证数值可移植性，不是声学误差标准。结果含平台、编译器、输入、输出、原生测试日志、200次调用耗时；耗时包括Python/ctypes/几何预检/求解，非采集端到端延时，不是Linux最坏调度保证。请回传ARM-RESULT.json以及 `uname -m`、`getconf LONG_BIT` 和Python版本。

## 2. Python纯计算调用

```python
import sys
from pathlib import Path
sys.path.insert(0, 'software/tetra3d/linux')
from solver_3d import Solver3D, read_json

geometry = read_json(Path('software/tetra3d/core/tetra40-nominal.json').read_text())
solver = Solver3D('software/tetra3d/linux/libss_solver_3d.so', geometry)
# frame来自C已验证的单一所有者acquire，或离线快照JSONL。
# frame = {'sequence': 非零uint32, 'status': LOCKED快照状态, 'words': 30个uint32}
result = solver.solve(frame)
```

输入六对各五字为FEATURE_0/peak/r_minus/r_plus/second_peak。负幅值字以uint32保存，C按冻结头解释S32/S25；不能把Python负整数直接塞入word。输入序号、状态和每个字必须是uint32，禁止静默取模。

先检查 `bridge_status`：负值为线格式/参数/几何错；正值为求解API输入错；0之后才检查 `direction_valid`。方向有效还需分别检查 `azimuth_valid/elevation_valid`。极点方向有效但方位无效是预期行为。所有输出来自同一次调用，不保持旧角度。

输出含ux/uy/uz、norm、residual_rms_samples、normal_condition、azimuth/elevation的deg与q8、每对delta/tau/margin64/qualified/reason、几何版本与来源。`servo_cmd_valid`固定0。库不消费快照、不提交动作、不自动清错；由C继续负责记录成功后的消费、故障停止与所有权。现有二维应用使用不同的result字段，C需适配日志/显示和拒绝判断后才能接入。

原生平坦数组API详见 `software/tetra3d/linux/ss_solver_3d_bridge.h`，版本0x00010000，仅为进程内ctypes协议，不改PL寄存器ABI。源结构体未直接作为Python布局；32位ARM/64位PC均使用明确的uint32/int32/int64/float类型。输出缓冲由调用者提供，必须满足头文件尺寸，不重叠。

## 3. 离线回放

```sh
python3 software/tetra3d/linux/solver_3d.py \
  --library software/tetra3d/linux/libss_solver_3d.so \
  --geometry software/tetra3d/core/tetra40-nominal.json \
  --input document/evidence/ps-tetra3d-migration-20261021/EXAMPLE-FRAMES.jsonl \
  --output software/build/tetra3d-migration/replay.jsonl
```

示例是合成六对特征，不是PCM/实录。每行输入为完整frame字典，输出保存原输入、全部几何配置、解算结果和本次调用时间。API/输入错误保存后停止；正常算法拒绝记录原因并继续。输出文件必须尚不存在；空输入不能算通过。离线回放不证明在线帧新鲜度，真实流仍需C检查锁槽与序号。

## 4. 原交付分工与剩余技术工作

下表保留原交付责任说明。当前三维实现/验证由A侧推进，B继续声纹，具体以2026-10-28的[并行分工](../../document/tetra3d-integration-plan.md)为准；技术待办不因分工变化而视为完成。

| 人员 | 下一步 | 交付 |
|---|---|---|
| B | 根据目标ARM结果处理数值/调用问题；实测几何与独立方向到齐后分析 | 对比结果、算法参数和误差说明 |
| C | 运行上述ARM离线测试；显式新增三维结果的显示/记录路径，保持二维BIST入口 | ARM结果及三维无动作采集日志 |
| A | 确认真实PL六对、lag符号、48kHz、频带及窗口/邻点；三维阵列通道一致 | 匹配映像/配置与通道记录 |
| 人类现场成员 | 制作40mm标称阵列并测量声孔坐标/误差，测独立参考角度 | 实测几何和同步实录 |

`doa_target_3d.c/h` 已随共享库编译并完成原软件回归，C调用者可单独使用其API；Python三维入口本批仅输出方向，不提供双轴动作配置或提交。双轴映射采用已对齐正交yaw/pitch、1:1角度模型，默认关闭，不能代替实际机构标定、限位/看门狗/新鲜度保护。现有硬件动作合同仅水平轴，A/C需对齐双轴接口后另行接合。

板测与实录前，已完成的是远场方向数学及源码适配；没有声明目标ARM、声学准确率或双轴设备验收完成。无目标板连接时B不能生成并验证与目标ABI匹配的最终ARM二进制，本批交源码及目标构建命令。
