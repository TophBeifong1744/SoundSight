# 三维PS桥本地兼容修复

2026-10-25，用户授权“直接在我这里改”。已将刚核查的B候选接入本地`software/tetra3d/`并修复STATUS bit18兼容；没有激活三维在线应用，声纹识别仍是当前主线。

## 来源与变化

- 来源固定为B分支`codex/tetra3d-das`的`3347989eb03488a33c88c241c75eed517d3a30f0`。从上一级已保存候选快照接回23个模块/说明/测试文件；补齐作者原始迁移报告、示例和PC黄金结果，位于`document/evidence/ps-tetra3d-migration-20261021/`。
- 接回前核对公共冻结头、`doa_solver.c/h`与B候选内容一致（仅忽略文本换行）；没有覆盖公共依赖。
- `software/tetra3d/linux/ss_solver_3d_bridge.c`：只在PS桥自己的允许掩码中加入bit18，注释说明它是能力位而不是动作许可。算法帧标志仍按冻结的帧标志掩码提取。
- `software/tetra3d/tests/test_solver_3d_migration.py`：新增155组能力位等价检查；将非法STATUS位、未锁帧、错误配对/字段检查扩展到能力位有/无两种情况。总桥负例为28项。
- 更新该模块README和PS-MIGRATION说明；当前操作入口、二维/声纹代码、RTL、冻结SPI合同、位流、SD卡包均未修改。

本地修复完成时没有切换分支、暂存、提交、推送或合并。随后用户授权将本次三维修复独立提交并推送；共享工作树中的声纹等其他修改保留，不混入提交。三维仍需显式选择，实施顺序见[暂缓接合方案](../../../tetra3d-integration-plan.md)。

## 真实验证

环境：Windows AMD64、Python 3.14、NumPy 2.4.6、MinGW GCC 16.1.0。仅运行电脑离线编译/测试，不访问硬件。

| 检查 | 结果 |
|---|---|
| 原C算法/映射回归 | 原二维选择2110、三维2378、双轴软件映射92270项断言，均0失败 |
| 原154组迁移对照 | 通过，并与B原始PC-RESULT.json完成黄金结果比较 |
| 能力位等价 | 154组原特征逐组增加bit18后，完整结果保持一致；实际PS状态组合合成复现另1组，共155组通过 |
| 桥输入负例 | 28项通过；保留位6/21/22/23、未锁帧、错误配对/字段及Python整数范围仍拒绝 |
| 几何及JSONL入口 | 原15个几何检查、4个回放入口检查通过 |
| DAS回归 | 16项通过、0跳过，实际C求解器到DAS的用例也执行 |
| 旧桥检错验证 | 用未修复B桥编译库，运行新增测试，准确在`ps_manual_capability`断言失败 |

155组能力位等价包含方向有效、无效、取消和旧BIST等原始用例；bit18不会使被算法拒绝的帧变成有效方向。PS状态组合用例的特征是合成45°/30°特征，不是新实物采集。

`RESULT.json`与`migration.log`保存修复后的结果，`das.log`保存DAS输出。`old-bridge-canary.log`保存预期检出的旧故障；这是测试检错成功，不是修复版失败。原始故障探针及未改B源码仍保存在上一级，未被覆盖。

## 复现

在仓库根目录运行；`gcc`可通过`--cc`或本机环境变量`CC`指定，DAS中的实际C接合用例也需要同一编译器：

```sh
python software/tetra3d/tests/test_solver_3d_migration.py --cc gcc --golden document/evidence/ps-tetra3d-migration-20261021/PC-RESULT.json --output software/build/tetra3d-migration/RESULT.json
python software/tetra3d/das/test_das_3d.py -v
```

预期看到`equivalence=154 bridge_negative=28 geometry=15`、`PS_CAPABILITY_PASS equivalence=155`和DAS的`Ran 16 tests ... OK`，不能有跳过C接合测试。

## 未测及收尾

本次未运行ARM、PYNQ板测、实际三维阵列或双轴动作，也未接入声纹运行链。无需为此修改Vivado工程或重新生成bit。

编译器产物均由测试的临时目录管理并已释放；没有新增长期临时工程或codex_out内容。保留正式源码、作者原始基准以及必要的新旧结果。用户当前不需要操作板子。
