# STM32 S1 水平角数学部分的 Python 移植

源码：[stm32_angle_math.py](stm32_angle_math.py)。对应当前 C 实现是
`software/common/s1/doa_solver.c`；C 接口/冻结合同没有改动。这个 Python 文件用于
PC 数值分析和对照，接收按 01、02、03、12、13、23 顺序排列的六对**已解码**峰值特征。
它不读取寄存器、不解析 SPI/帧状态、不产生舵机命令。调用方必须先按冻结 ABI 排除
取消、源错误和未终结帧，再把每对的原始峰/处理阶段资格合并为 `source_qualified`。
对于 BIST 诊断帧，资格规则与真实帧不同，也由调用方判定；数学模块不能决定动作许可。

## 计算方法

1. 每对先要求 `mask_count >= 12` 和 `source_qualified=True`。三点抛物线插值：
   `delta_q12 = clamp(RNE((r_minus-r_plus)*2048 / (r_minus-2*peak+r_plus)), -2048, 2048)`；
   分母为 0 时沿用 C 约定，`delta_q12=0`。随后
   `tau_q12=lag*4096+delta_q12`。`RNE` 是整数的最近偶数舍入，负数同样对称。
   对角对 02、13 的 `|tau_q12| <= 32425`，其余四对 `<= 22928`。
2. 六对坐标 `(dx,dy)` 是 `(1,0),(1,1),(0,1),(0,1),(-1,1),(-1,0)`。
   合格对至少三对，按 C 中的整数正规方程求 `ux_q20,uy_q20`，行列式须正。
   计算每对预测时差与实测时差的残差平方和，并检查
   `residual_square_q24 <= valid_pair_count*4194304`；再检查
   `10995200164 <= ux_q20²+uy_q20² <= 1858175196201`。
3. 对合格向量运行原 24 级整数 CORDIC 和相同 Q16 反正切表。
   **`angle_q8` 是正式输出**，度数为 `angle_q8/256`，范围 `[-180°,180°)`。
   `atan2_deg` 用 Python 浮点算出，仅供对照；它不是 C `atan2f` 的逐位移植，
   也不替代整数角。无效结果的 `angle_q8` 为 `None`。

`margin_q15` 与 C 一样计算并保留在逐对结果中，但不参与角度筛选或加权。
水平/垂直舵机映射和原 C 的 `servo_cmd_valid` 均不在此模块中。

## 运行

在仓库根目录执行，无第三方 Python 依赖：

```powershell
python -B models/python/test_stm32_angle_math.py
```

预期输出是 `Ran 6 tests ... OK`，不写工程输出文件。测试对照原 C 测试记录的
±45°、±90°、偏轴和 BIST 数值向量，以及插值/时差端点与四象限 CORDIC。

一个可直接运行的调用示例：

```python
from stm32_angle_math import PairFeature, solve_from_pairs

lags = (3, 6, 3, 3, 0, -3)
pairs = [PairFeature(lag, 1000, 800, 800, 100, 79, True) for lag in lags]
result = solve_from_pairs(pairs)
print(result.valid, result.angle_q8, result.angle_deg)  # True 11520 45.0
```

从仓库根目录运行这段示例时，将 `models/python` 加入本机 `PYTHONPATH`，或把示例保存
在该目录。下一步若要接真实采集链，先将上游六对字段与 `source_qualified` 对接并核验
实测几何/通道映射；当前测试只验证数学移植和既有合成向量，不代表实机声学验收。
