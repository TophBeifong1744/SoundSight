# B 的三维模块只读评估 — 2026-10-25

后续：用户已授权在本地修复，本目录下[local-fix/README.md](local-fix/readme.md)记录修复后的源码、回归和未测范围。以下保留首次评估的原始候选及失败事实；`candidate-source.zip`仍是未修复的B候选。

结论：三维求解与DAS已具备可复现的电脑算法模块，但还不能直接替换当前板端程序；确认了一处PS状态位兼容故障。当前主线仍是尚未完成的声纹识别。本轮不接入三维、不合并、不改RTL/位流、不驱动舵机。

## 候选与工作边界

- 来源：`TophBeifong1744/SoundSight` 的 `codex/tetra3d-das`。
- 本次固定提交：`3347989eb03488a33c88c241c75eed517d3a30f0`。查询时该分支没有对应PR。
- 阅读范围：`software/tetra3d`全部源文件、说明、测试及其冻结头/S1依赖；对照当前PS状态寄存器、C桥和PCM接入代码。
- 本机当前checkout有其他工作的未提交修改，全部保留。没有切换分支、合并或覆盖产品源码。
- `candidate-source.zip`仅是此次复测所用的30个文本文件快照，不是上板包，不包含作者的大型PC-RESULT.json。提取过程中仅规范了文本换行/末尾换行。

## 发现：当前PS状态字会被三维桥拒绝

严重性：接入阻断，需在实际接板前修正。

[ss_solver_3d_bridge.c 第22行](https://github.com/TophBeifong1744/SoundSight/blob/3347989eb03488a33c88c241c75eed517d3a30f0/software/tetra3d/linux/ss_solver_3d_bridge.c#L22)仍只接受冻结头的`SNAP_STATUS_DEFINED_MASK=0xFF1BFFBF`。它没有包含PS扩展的bit18（`0x00040000`，手动舵机能力）。当前`project/rtl/ss_ps_control_regs.sv`把该位置1；二维`software/ps/ss_solver_bridge.c`已经为这件事修过一次，三维桥尚未同步。

用B的原码编译库，对同一组合成的45°方位/30°俯仰特征只改变STATUS，实际结果如下：

| 输入STATUS | bridge_status | direction_valid | 含义 |
|---|---:|---:|---|
| `0x11` | 0 | 1 | 原测试格式正常 |
| `0x40011` | -2 | 0 | 仅新增手动能力位就被拒绝 |
| `0xf7f31` | -2 | 0 | 使用此前真实PS帧的状态位组合，也被拒绝 |
| `0xb7f31` | 0 | 1 | 仅用于定位问题：去掉能力位后恢复 |
| `0x51` | -2 | 0 | 未定义bit6仍正确拒绝 |

这不是音量、反射、三维算法精度或舵机是否开启造成的。建议在PS专用三维桥中接纳已定义的PS能力位并补等价/负例回归，保留SPI冻结合同和其余非法位检查；不要在应用中任意清除STATUS作为长期绕过。本轮仅复现，未修B分支。

原始输入和输出见`ps-status-result.json`；复现脚本为`probe_ps_status.py`。表中0xf7f31案例的特征仍为合成特征，不能说成真实三维声学试验。

## 三部分分别能做什么

| 部分 | 输入/输出 | 当前能用到哪一步 |
|---|---|---|
| C三维求解器 + Python桥 | 同一帧六对特征 + 四麦xyz坐标 → 方向向量、方位角、俯仰角、有效性及原因 | 电脑合成/回放可用；ARM、实物四面体尚无验证结果 |
| 双轴目标映射 | 三维结果 + 两轴零位/方向/机械范围 → 两个软件目标角 | 数学映射已有测试；不含实际双轴PWM接合、时效/提交授权 |
| Python/NumPy DAS | 连续四路S24 PCM + 有时效的三维方向 → 单路定向叠加音频 | 离线/参考实现；ARM实时吞吐和真实声学效果未验证 |

三维求解输入仍为01/02/03/12/13/23六对，每对5个uint32。lag定义为`t_a-t_b`，配合`Xa*conj(Xb)`，方向指向声源。示例是边长40mm正四面体、48kHz、声速343m/s；xyz是名义值，不能冒充实际阵列测量值。当前平面四麦不能只换库就获得可靠上下方向。

`Solver3D`的结果字段是`azimuth_q8/elevation_q8`等，当前二维程序使用`angle_q8`及二维筛选/动作规则。需要明确的三维应用适配，不能把新.so改名覆盖旧库。旧平面BIST在三维接口中被明确标为旧BIST拒绝，不能用于宣布三维计算通过。

DAS是按照方向把四路声音对齐后叠加，不是识别人，也不等于多人语音分离。目标失效后默认渐变回mic0，而非静音或硬件急停。每个流只有有限历史样本，但Python逐样本处理和每块临时诊断对象的实际开销仍需ARM测量。

## 与现有PCM/声纹主线的关系

当前PCM CDC工程已经提供四路48kHz PCM及同一时基的定位元数据，并有板端有限录音验证。不要再把“完全没有PCM通路”作为三维或声纹的现状。当前软件入口仍是有限包数录音，不能把它说成已经完成无限时长实时流水线。

可复用的具体接口：

- DMA每包512个采样时刻，32字节包头 + 8192字节载荷，四通道按采样交错，S24符号扩展为小端int32。
- DAS要求形状`(4,N)`的有符号整数数组；适配时从载荷按`<i4`读取，再由`(N,4)`转置，保持原幅度和通道顺序。
- PCM有`epoch/block_seq/sample_start`。`TimedClient`在定位帧中提供`epoch/sample_start/source_window/sample_count/valid`。
- 以后接DAS时需按epoch和采样范围对齐方向，处理晚到/过期结果；不能把定位帧序号当成PCM采样编号，也不能把收到消息的电脑时间直接当作采样时间。DAS一会话从采样0开始，缺口或新epoch需重建状态。

当前优先事项仍是完成声纹识别：真实音频到预处理、模型、身份判断的完整PYNQ链路，以及总耗时/运行稳定性。当前CAM++核心的实板测速不等于完整声纹实时流程已完成。

B的三维模块保留为后续扩展。若以后把DAS作为声纹前处理，还要重新核对登记/识别音频链的一致性和实际识别效果；不能拿DAS的合成降噪数字替代声纹效果结论。本次不调整已决定的单通道声纹基线，也不因三维模块到货而扩展当前硬件任务。

## 本机真实复测结果

环境：Windows AMD64、Python 3.14、NumPy 2.4.6、本机MinGW GCC（完整编译器版本见`migration-result.json`）。所有测试均使用固定候选的原代码，无硬件访问。

- B的C测试重跑：原二维选择2110项、三维选择2378项、双轴软件映射92270项，均0失败。这些数字是测试内断言次数，不是独立声学样本数。
- B的迁移测试重跑：154组对照、17个桥负例、15个几何检查、4项JSONL入口检查通过。本次未使用作者PC黄金文件对比；没有ARM结果。
- B的DAS测试重跑：16项通过、0跳过，其中实际编译C求解器接DAS的测试也执行了。
- 额外PS状态位探针：5种状态均符合预期，确认上述兼容故障。探针成功只代表故障可复现，不代表候选已修好。
- 未运行Vivado、XSim、下载、板测或执行器操作。此交付是软件模块，当前问题不需要重新综合来定位。

日志：`migration-review.log`、`das-review.log`、`migration-result.json`、`ps-status-result.json`。

## 复现命令

将`candidate-source.zip`解压到独立临时目录，在解压根目录运行（编译器由本机`CC`或`--cc`指定）：

```sh
python software/tetra3d/tests/test_solver_3d_migration.py --cc gcc --output review_results/migration-result.json
python software/tetra3d/das/test_das_3d.py -v
```

在仓库根目录运行额外探针，`<snapshot>`换成上面的解压目录：

```sh
python document/evidence/tetra3d-review-20261025/probe_ps_status.py --source <snapshot> --cc gcc --output review_results/ps-status-result.json
```

本轮临时源码和编译结果在保存必要原件后清理；正式产品源码、正在进行的声纹工作和用户的外部工程均未改动。
