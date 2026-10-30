# 在线音量门限、角度筛选和死区（不驱动舵机）

2026-10-21：已接到 `software/ps/run_buffered.py`，使用 `--angle-filter --min-level 1000` 启用。纯Python软件变更，现有音量版bit/HWH、RTL、ABI、C求解器均不变。1000是试调值；窗口参数也只是此前离线回放采用的实验值，不代表声学标定或机械响应已经通过。

## 每一层做什么

1. C求解器的原始结果保留在 `result`；它不是最终的应用输出。
2. 音量低于门限、音量无效、故障、取消、BIST时，不能输出新方向；清空积累窗口和旧目标。音量等于门限可参与筛选。测量模式 `--measure-level` 只测音量，不启用角度筛选。
3. 正常发声期间，每20个连续帧完成一个窗口，不重叠、不提前输出。求解器普通拒绝帧计入20帧，但不参与平均；至少需要12个有效角。
4. 找到当前窗口中与其他有效角的圆周距离总和最小的一个角（圆周中位中心），保留离它不超过10°的角。保留数必须至少12个，而且至少占本窗有效角的2/3；否则整窗不输出。中心由当前窗口决定，不能因旧方向而挡住真正转向。
5. 对保留的角算圆周平均：179°与−179°应平均到±180°附近，不能变成0°。
6. 第一个合格窗口建立目标。以后候选与上次输出目标的最短圆周距离达到3°才更新；小于3°时保留目标。累计变化仍相对上次实际更新目标比较，不会被每窗的小变化抵消。

低音量立即清窗，恢复后需要重新积累20帧。断序、重复、倒序也重建窗口并清除旧目标；新会话不继承旧状态。STOP、高水位或异常后的排尾仍完整保存原始记录，但禁止产生新目标。不满20帧的末尾不强凑结果。

普通求解拒绝不会直接清窗，例如12个合格角加8个拒绝帧仍可能产生窗口估计；估计代表这个窗口，不代表最后一帧。C接口错误则清窗。筛选拒绝的窗口不输出旧角；内部死区参考保留到下一合格窗口，低音量、故障、断序或STOP会清掉它。

## 怎么运行

先按包内README完成解压、ARM C库编译和软件自测。新音量bit首次加载仍按已验证的PYNQ时钟流程操作，确认ID=0x5a5a2026、ABI=0x00010001、FCLK0约100MHz、复位已释放、无未处理旧槽或故障。旧ABI不能运行本功能。以下只由用户在板端执行，不会自动加载bit或驱动舵机。

已经加载音量bit且只剩已知STOP故障0x40时，运行100帧：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_buffered.py --hwh soundsight.hwh --output volume-filter-100-001.jsonl --mode real --frames 100 --min-level 1000 --angle-filter --clear-faults 0x40
```

`--clear-faults 0x40`只用于已经确认的STOP标记；有其他故障或旧槽应先按原恢复流程处理。输出文件独占新建，重复试验更换文件名。音量门限可改，先分别固定安静和持续发声条件，再比较记录的 `volume.level_counts`。不要用BIST合成音量标定。

查看窗口及音量拒绝统计（在同一工作目录）：

```sh
python3 -c "import json; from collections import Counter; f=[json.loads(s) for s in open('volume-filter-100-001.jsonl') if s.strip()]; f=[r for r in f if 'angle_filter' in r]; print('REASONS=',dict(Counter(r['direction_output']['reason'] for r in f))); [print('SEQ=',r['frame']['sequence'],'OUT=',r['direction_output'],'WINDOW=',r['angle_filter']) for r in f if r['angle_filter']['complete']]"
```

## 日志字段

|字段|用途|
|---|---|
|`result`|原始C求解输出，未经音量或时间筛选|
|`volume`|本帧实际音量、设置门限、单位和测量有效性|
|`frame_direction`|单帧音量门限后的结果，仅启用多帧时出现|
|`angle_filter`|窗口帧数、有效数、入选数、参数、起止序号、候选圆周平均及决策|
|`direction_output`|最终应用结果；只在合格窗口末尾 `valid=true`，其他帧角度为null|
|`direction_output.updated`|目标是否在本窗口更新；死区内为false，仍可显示当前合格窗口确认的目标|
|`motion_requested`|始终false，本入口不提交任何舵机动作|

最终角度同时给出浮点 `angle_deg` 和按256倍四舍五入的 `angle_q8`。显示程序必须检查 `valid`；不要把null当0°，也不要把过去的有效目标当作当前仍在发声。不设置 `--angle-filter` 时保留原单帧门限行为。

本实现按帧数统计，没有增加采样时间戳或固定输出周期保证。低音量频繁打断可能长时间不出角；这是重新积累策略的结果。板端性能、真实音量门限、移动声源响应仍需现场验证。当前不连接执行器，也不声称3°死区等于机械角度精度。

## 源码和自测

- `software/ps/angle_filter.py`：共享数学函数和在线状态；离线回放工具调用同一数学函数。
- `software/ps/volume_gate.py`：单帧门限后执行一次状态更新，再交RAM保存确认，成功后才释放PL槽。
- `software/ps/run_buffered.py`：显式参数、会话状态和STOP尾帧抑制；原队列和单MMIO所有者机制保留。
- `software/tests/test_online_angle_filter.py`：数值、边界、假MMIO会话及保存失败测试。

```sh
python3 -B software/tests/test_online_angle_filter.py -v
python3 -B software/tests/test_volume_gate.py -v
python3 -B software/tests/test_buffered.py -v
```

主机定向测试和旧1000帧等价回放证据见 `document/evidence/pynq-online-angle-filter/README.md`。旧1000帧不含真实音量，等价回放仅验证角度部分，不能冒充新的联合实板结果。
