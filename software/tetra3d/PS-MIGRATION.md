# B → C：三维算法的 ARM Linux 接口

三维专用源码、入口和测试集中在 `software/tetra3d/`，现有二维发布包不自动包含它。

2026-10-25 新增独立[三维 DAS 定向拾音](das/README.md)：几何延时、Solver3D 结果接合、连续 PCM 分块及离线 WAV 导出，16 个 PC 测试通过。需要连续四路 PCM；本页六对定位特征不能直接用作音频输入。尚未接入 PYNQ 在线应用或完成 ARM/实物声学验证。

同日基于用户确认的3347989完成[六项兼容软件优化](OPTIMIZATION.md)：默认调用和结果保留，新增缓存、可选加权/校准/参数、DAS性能优化及独立方向滤波/双轴软件策略。原测试仍适用；新选项、上下文生命周期和新增模块接入按该说明执行。

已补齐可导入的 `TetraPipeline` 模块接合层和统一配置，见 [兼容替换说明](INTEGRATION.md)。它不新增在线运行入口；原程序可继续使用原接口，或在具备源采样时标/连续PCM时调用整个三维链。

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

测试返回原二维选择2110项、三维选择2378项、双轴软件映射92270项通过，以及 `MIGRATION_3D_PASS equivalence=154 bridge_negative=17 geometry=15 motion=DISABLED`。不要加 `-ffast-math`；使用本机GCC即可，不需要AC5授权。Windows生成的DLL不能复制成ARM .so。

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

## 4. 接合与剩余分工

| 人员 | 下一步 | 交付 |
|---|---|---|
| B | 根据目标ARM结果处理数值/调用问题；实测几何与独立方向到齐后分析 | 对比结果、算法参数和误差说明 |
| C | 运行上述ARM离线测试；显式新增三维结果的显示/记录路径，保持二维BIST入口 | ARM结果及三维无动作采集日志 |
| A | 确认真实PL六对、lag符号、48kHz、频带及窗口/邻点；三维阵列通道一致 | 匹配映像/配置与通道记录 |
| 人类现场成员 | 制作40mm标称阵列并测量声孔坐标/误差，测独立参考角度 | 实测几何和同步实录 |

`doa_target_3d.c/h` 已随共享库编译并完成原软件回归，C调用者可单独使用其API；原 `Solver3D` 仅输出方向。可选 `TetraPipeline` 现可产生经过旋转/极点/限速处理的双轴软件设定值，默认关闭，均不提交硬件动作。双轴映射采用正交yaw/pitch角度模型，不能代替实际机构标定、限位/看门狗/新鲜度保护。现有硬件动作合同仅水平轴，A/C需对齐双轴接口后另行接合。

板测与实录前，已完成的是远场方向数学及源码适配；没有声明目标ARM、声学准确率或双轴设备验收完成。无目标板连接时B不能生成并验证与目标ABI匹配的最终ARM二进制，本批交源码及目标构建命令。
