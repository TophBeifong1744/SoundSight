# 三维模块接合与兼容替换

基线为用户确认的 `3347989`。本批在独立三维目录完成模块接合；按用户要求不新增运行入口，不改现有二维程序、PL协议或硬件动作路径。

## 替换已有模块

原调用仍有效，默认原始求解字段和音频结果保持兼容：

```python
solver = Solver3D(library, geometry)
result = solver.solve(frame)
beam = TetraDAS(geometry)
beam.from_solver(result, valid_through=pcm_expiry_sample)
mono = beam.push(pcm, start_sample=next_sample)
```

请作为同一版本更新 `software/tetra3d/` 内的源码。尤其 `das_3d.py` 和 `dynamic_das.py` 必须配套；Python/C桥/C求解器也应一起更新，然后在目标 ARM 上使用现有脚本构建：

```sh
sh software/tetra3d/linux/build_solver_3d.sh
```

库名仍是 `libss_solver_3d.so`，公开 C ABI 和原 `Solver3D.solve(frame)` 不变。Windows 测试 DLL 不用于 ARM。已有实例先结束、调用 `close()`，再切换新库；不要在运行中的进程里覆盖已加载的动态库。旧程序继续直接调用这两个模块时，缓存和 DAS 内部优化生效；新的筛选/平滑以及双轴策略需调用下面的接合层，可选加权与校准按配置启用。

## 一处调用接合整个三维链

`linux/pipeline_3d.py` 是供现有程序导入的类，没有主程序、采集循环或 PYNQ/MMIO 操作。

```text
六对快照 + 明确的源采样时标
                ↓
      Solver3D（缓存、可选质量加权、延迟校准）
                ↓
      DirectionFilter3D（空间筛选、平滑、死区、有效期）
                ├── TetraDAS + 连续四路 PCM → 单声道
                └── 可选双轴软件设定值（无硬件提交）
```

从项目根目录导入（Python 3.8+）：

```python
import json
from pathlib import Path
from software.tetra3d.linux.pipeline_3d import TetraPipeline

geometry = json.loads(Path('software/tetra3d/core/tetra40-nominal.json').read_text())
config = json.loads(Path('software/tetra3d/linux/pipeline-default.json').read_text())
config['das']['enabled'] = True  # 仅在确实提供连续四路PCM时启用

with TetraPipeline('software/tetra3d/linux/libss_solver_3d.so', geometry, config,
                   session_id='capture-session-1', target_id='selected-source') as chain:
    metadata = chain.metadata()  # 与原始记录一起保存完整配置
    # 以下是现有采集所有者的调用顺序，不是新的采集入口：
    # mono0 = chain.push_pcm(pcm[:, :k], start_sample=0)
    # record = chain.process_frame(frame, capture_sample=source_sample,
    #                              now_sample=k)
    # mono1 = chain.push_pcm(pcm[:, k:m], start_sample=k)
    # end = chain.push_pcm(pcm[:, m:], start_sample=m, final=True)
```

`process_frame()` 返回原始 `frame` / `result`，以及独立的 `filtered_direction`、`axis_setpoint`、时间信息和固定为假的 `motion_requested`。不要把滤波后角度覆写回原始求解结果。`metadata()` 提供几何、校准来源、完整有效参数和会话标识，返回副本。

无 PCM 时保持 `das.enabled=false`，可以单独调用 `process_frame()` 和 `poll(now_sample=...)` 使用定位/滤波。两者仍要求真实的源采样时标，不会自动推断。未提供轴配置时 `axis_setpoint.command_valid=false`。

## 采样时间与失效规则

`capture_sample` 是产生该帧定位特征的源采样参考点，`now_sample` 是结果可应用的当前源采样位置；两者使用同一会话中从零开始的四路 PCM 时基。参考点定义必须由采集端一致提供，不能用特征帧号或收到结果的主机时刻代替。

- 特征序号与 `capture_sample` 必须严格递增，`now_sample` 不得倒退。采样数均为普通非负整数。
- DAS 启用后，先推入早于 `now_sample` 的 PCM，再提交该时刻可用的特征；此时 `now_sample` 必须等于 `chain.next_sample`。新方向不能作用于已经过去的 PCM。
- PCM 为 `(4,N)` 的有符号 24 位整数，顺序 CH0～CH3；`start_sample` 必须连续。输入超范围或增益后溢出会拒绝整块，不截幅。
- 空间滤波默认需三个一致候选。HOLD 不延长最后一次接受观测的有效期；DAS 在块内部也执行样点有效期检查。回退是淡变到校准后的 CH0，既不是静音，也不是物理急停。
- BIST、故障、停止/排尾及错误桥接结果不能携带之前的有效方向。时间逆序、重复特征、PCM 空洞或非法块使该实例失效，须重新建会话。
- `final=True` 输出包含固定八点延迟的尾部，随后实例关闭；整体音频长度为输入长度加八。可以用 `(4,0)` 空块单独结束。
- 新采集、换目标、换几何或校准均新建实例。`target_id` 只是上游选择标识，不实现声纹/身份识别。

现有 PS 六对寄存器快照没有连续 PCM 和采样时间关联。这个接合层不补造数据，也不改变其协议；没有这些输入时，应继续使用原始 `Solver3D` 接口。模块软件接合不等于已在板上启用在线 DAS。

## 配置的一致性

示例 `linux/pipeline-default.json` 使用标称几何、零延迟、单位增益，并明确 `calibration_source=UNCALIBRATED`。延迟校准只填在 `calibration.channel_delay_samples`，接合层同时送给定位与 DAS；在 `solver_options` 再填同名字段会报错，避免两侧不一致或重复校准。

`quality_weighting` 默认关闭。`direction_filter` 的配置沿用 [OPTIMIZATION.md](OPTIMIZATION.md)。`axes=null` 默认不计算轴目标；需要纯软件验证时显式提供：

```python
config['axes'] = {
    'config': {
        'rotation': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        'yaw_limits_deg': [-180, 180], 'pitch_limits_deg': [-90, 90],
        'max_yaw_rate_deg_s': 60, 'max_pitch_rate_deg_s': 60,
    },
    'initial_yaw_deg': 0, 'initial_pitch_deg': 0, 'initial_time_s': 0,
}
```

这是模拟配置，实际安装旋转、范围、速率与初始姿态需要真实依据。生成的 `axis_setpoint` 仅为软件值，不能当作已经执行或机械反馈。原 `servo_cmd_valid` 始终为零。

## 验证与待办

```sh
python3 -B software/tetra3d/tests/test_pipeline_3d.py
```

该测试在当前机器临时构建 C 库，检查实际求解器到滤波/DAS/软件轴的模块连接以及异常边界。旧接口回归与本批测试结果见 [报告](../../document/evidence/tetra3d-optimizations-20261025/REPORT.md)。板端库重建、ARM速度、实测坐标/延迟/增益、连续PCM及采样时间关联、真实声学效果仍需实板验证；本批没有新增或执行在线运行入口。
