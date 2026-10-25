# 三维模块兼容优化

基线：用户确认已经接合的 `3347989`。工作分支 `codex/tetra3d-optimizations`。
范围是六项软件优化与 PC 验证，实际通道校准、ARM 性能、真实声学与机构动作仍需要现场证据。

## 六项对应关系

| 项目 | 软件实现 | 默认行为 |
|---|---|---|
| 三维方向滤波 | `linux/spatial_runtime.py` 的 `DirectionFilter3D`：单位向量、空间夹角筛选、时间平滑、死区、有界保持及重捕获 | 独立调用，不插入旧求解器 |
| 质量加权 | C 三维求解器可按峰值 margin 做有界加权，保留全部合格对的未加权残差等拒绝检查 | 关闭；等权结果兼容 |
| DAS 效率 | 固定环缓冲、预分配输出、可关闭逐点 trace；TetraDAS 关闭本来就丢弃的 trace | 输出样本与旧版对照，调用方式不变 |
| 校准接口 | 定位与 DAS 共用四路固定延迟定义，DAS 另支持乘法增益校正 | 零延迟、单位增益；不虚构实测值 |
| 缓存和参数 | 每实例几何上下文、等权有效对组合缓存、显式阈值配置 | 旧参数与结果字段保持 |
| 双轴策略 | `DualAxisTracker`：安装旋转、近极点迟滞、速率/范围检查、目标超时 | 默认禁止输出；仅纯软件目标 |

必要文件涉及原 `core/doa_solver_3d.*`、`linux/ss_solver_3d_bridge.*`、`linux/solver_3d.py`、`das/dynamic_das.py`、`das/das_3d.py`，以及新增独立 runtime、测试和本说明。二维目录、公共ABI、PL、现有二维在线入口不改。

## 兼容替换边界

旧 `ss3d_solve_words`、bridge version、原结构体和输出字段继续保留。旧 Python 调用仍有效：

```python
solver = Solver3D(library, geometry)
result = solver.solve(frame)
beam = TetraDAS(geometry)
beam.from_solver(result, valid_through=pcm_expiry_sample)
mono = beam.push(pcm, start_sample=next_sample)
```

新增选项通过构造时传入，不在运行中原地修改；变更几何/校准后应停止并重建相关会话。上下文由 Python 托管，旧调用丢弃实例时会自动释放；仍建议使用 `Solver3D.close()` 或上下文管理确定释放时点。调用 `close()` 后不能继续求解。若调用方自行卸载动态库，必须先关闭使用它的所有 Solver3D 实例。
Python 和对应新库应一起更新；Windows PC DLL 不能部署到 ARM。目标板需用既有 `linux/build_solver_3d.sh` 重新构建本机库，并执行离线验证。

现已提供可导入的 `TetraPipeline`，统一接合求解、方向滤波、可选DAS及双轴软件策略，见 [模块接合与替换](INTEGRATION.md)。按用户要求不新增运行入口。现有主程序可调用该类；继续使用旧模块调用时保持旧行为，不会因为源码更新而自动开启新策略。新质量加权和校准默认关闭。

## 参数与校准

```python
options = {
    'schema': 1,
    'quality_weighting': False,
    'quality_weight_floor': 0.25,
    'channel_delay_samples': [0, 0, 0, 0],
    'max_normal_condition': 100,
    'max_residual_rms_samples': 0.5,
    'norm_min': 0.85,
    'norm_max': 1.15,
    'tau_slack_samples': 0.125,
    'min_pairs': 4,
}
solver = Solver3D(library, geometry, options=options)

calibration = {
    'schema': 1,
    'channel_delay_samples': options['channel_delay_samples'],
    'channel_gain': [1, 1, 1, 1],
}
beam = TetraDAS(geometry, calibration=calibration)
```

示例零值表示未校正，不是实测结论。应用应记录几何版本、校准来源、完整选项，并让定位与音频使用同一采样率/通道编号/校准值。

正 `channel_delay_samples[i]` 表示该通道的实测波形比理想波形**晚到**。定位使用
`tau_corrected(a,b) = tau_measured(a,b) - (bias[a]-bias[b])`；DAS 使用
`delay[i] = geometric_delay[i] - (bias[i]-bias[0])`。DAS 保留 CH0 时间参考，不能对同一输入重复应用前端已有的延迟校正。

`channel_gain` 是直接乘到 PCM 上的校正系数，不是测得增益。例如测得通道幅度为目标的0.8倍，应使用1.25。放大可能导致超出S24范围，模块拒绝越界块而不是悄悄截幅；调用方需确保输入余量。CH0回退也采用CH0增益校正。

质量加权不是可信概率，不自动剔除异常对，不解除残差/norm/最少4对/故障保护。改变阈值是实验参数变更，必须记录和回放比较，不因输出更多就视为更准确。

`max_normal_condition` 只控制每帧有效对组合的求解条件数；原几何预检仍采用既定标准，不能用此参数绕过过于扁平等不合格几何。当前两侧通道延迟校正均限制为每通道±1采样点，DAS另检查几何和相对偏置叠加后仍在±8点处理范围内。

## 三维方向滤波与双轴

```python
from spatial_runtime import DirectionFilter3D, DirectionFilterConfig

tracking = DirectionFilter3D(DirectionFilterConfig())
record = tracking.update(
    result, timestamp_s=source_sample / sample_rate,
    now_s=current_sample / sample_rate, sequence=frame_sequence,
    session_id=capture_session, target_id=selected_target,
)
direction = record['filtered_direction']
```

`raw_result` 保留原始求解结果，`filtered_direction` 独立发布向量、状态和有效期限。所有时间必须在同一单调时基；不能把定位帧号当 PCM 采样号，也不能以结果到达时刻替代采集时刻。采集会话/目标更换必须重建或重置对应音频与控制会话。

默认首次及大角度重捕获要求连续3帧支持；保持时间、候选间隔和过期使用秒，不依赖固定帧率。HOLD不延长原方向的有效期限。应用即使没有新定位帧，也必须定期调用 `poll(now_s=...)` 检查过期。

接收时钟倒退会打断候选确认，不推进最后合法时间。双轴的同一观测时间戳只允许重复相同归一化方向和期限，不允许用HOLD包修改目标方向或延长期限。

给DAS下发滤波结果时使用 `beam.steer(direction['vector'], valid_through=...)`，不要改写原 `result` 假装它是C求解器新输出。将有效期换算为同一音频会话的采样号，保守取到期前最后一点；已到期则 `beam.fallback()`，不得重新从当前时刻续期。
DAS仍保留8点处理延迟、默认480点渐变；过期退回单麦仍可能经过最多两段渐变（48kHz下约20ms），不是立即静音。

`DualAxisTracker` 要求显式提供安装旋转矩阵、机构范围、每轴速度上限和已知初始姿态；`enable=False` 是默认值。返回 `command_valid` 只表示软件目标可用，不是运动许可或PWM提交。原 `doa_target3d_map` 不变。
该策略适用于对齐后正交yaw/pitch机构，不能替代编码器闭环、碰撞/硬限位和实物标定。接近极点时保持已知水平轴，并用进入/退出迟滞避免抖动。

## 验证与待办

测试入口（从仓库根目录，Python+NumPy+GCC）：

```sh
python software/tetra3d/tests/test_solver_3d_options.py
python software/tetra3d/tests/test_solver_3d_migration.py --golden document/evidence/ps-tetra3d-migration-20261021/PC-RESULT.json
python software/tetra3d/das/test_das_3d.py
python software/tetra3d/das/test_das_optimized.py
python software/tetra3d/tests/test_spatial_runtime.py
python software/tetra3d/tests/test_optimized_chain.py
```

本批实测结果在集成完成后记录于下方。PC速度不能替代PYNQ性能，合成偏置不能替代实测校准；旧接口等价测试与新功能行为测试分别统计。

最终结果：73项Python测试全部通过（14求解选项、16原DAS、12优化DAS、30方向/双轴策略、1项含6方向的完整链测试），无跳过。原C三组2110/2378/92270断言以及154组迁移数值、17非法输入、15几何、4CLI检查继续通过。完整记录见[本批报告](../../document/evidence/tetra3d-optimizations-20261025/REPORT.md)。

DAS旧版逐点比较会从Git读取3347989；源代码ZIP或浅克隆没有该对象时会明确跳过，不能把跳过记为兼容验证通过。

待现场完成：连续四路PCM与定位采样区间关联；实测位置/延迟/增益；目标ARM吞吐与耗时；真实多方向/混响/双声源/移动目标音频；双轴初始姿态、安装旋转和机构限位确认。没有自动板测或执行器动作。
