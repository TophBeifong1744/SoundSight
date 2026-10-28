# 英文窗口诊断与可调帧数

2026-10-22，用户要求：显示已积累帧数/窗口大小、上一组结果和最近清空原因；保持默认筛选规则，增加可调整窗口总帧数和最低有效角度数的短命令；更新SD包，不驱动舵机。

## 交付

- `software/ps/angle_filter.py`：实例窗口参数及有效数验证，新增reset_reason诊断。默认20/12；±10°、至少三分之二有效角度一致、圆周平均、3°死区、低音量/断序/错误清窗及停止规则不改。有效数门限仍同时用于原始有效数和筛选后保留数。
- `run_normal.py`：当前WINDOW/VALID/MIN、LAST_GROUP、LAST_CLEAR及对应帧号/年龄。上一组与最近清空各只保留一条快照，不增加逐帧写盘；低音量清除当前目标，但上一组可保留为HISTORY诊断，不能冒充新方向。
- `board_tools.py`、`soundsight.sh`：`filter`查看，`filter N M`保存，run可用--window-frames/--min-valid临时覆盖。普通设置操作不需PYNQ；修改时仍取原所有者锁，正在采集则拒绝改设置。设置和音量互不覆盖，旧只有min_level的文件默认补20/12。参数仅下轮生效。
- `volume_gate.py`、`run_buffered.py`：正常和调试入口都将参数传到实际筛选实例；详细日志记实际参数。合法范围1<=M<=N<=100，限制内存及圆周中心搜索规模；不同参数在本板的延迟/声学效果尚待实测。
- `release/output/soundsight_normal_update.zip`：同一入口26份payload，不含新bit/HWH/C库；安装仍备份被替换源码，保留设置及日志。使用说明在document/pynq-board-helper.md和pynq-normal-mode.md。

## 实际验证

最终包解压安装到隔离目录后，11组共146项离线测试全部通过，原始输出为本目录test_*.log与checks.json。新增13项覆盖：默认窗口输出时机/死区、可调窗口与最低数、跨±180°、一致性仍不变、无效参数拒绝、清窗/断序/STOP、错过窗口完成后仍显示拒绝原因、低音量恢复后最近清空保留、历史目标不冒充当前有效角、旧设置兼容/相互保留、两模式CLI与worker真正传入参数、所有者锁、非法CLI在硬件前拒绝。既有串口ASCII、非阻塞显示、常量规模内存、慢盘/错误/停止测试继续执行。

附加默认等价对照：旧实现取Git提交7c8f48a的angle_filter.py，与新默认实例逐帧比较4000个模拟输入。随机种子20261022；角度每200帧交替基准-12/179度并加均匀±2度扰动，每23帧离群90度、每11帧求解拒绝、每113帧低音量、每97帧人为断序。忽略新增reset_reason字段后整条返回记录完全一致，153个接受窗口、116次清空事件，结果见default-equivalence.json。这是软件等价验证，不是新采集实测。

复现定向测试：

```text
python -B software/tests/test_filter_controls.py -v
python -B tools/check_normal_update.py
```

第二条在Windows需通过SOUNDSIGHT_TEST_SH指定本机POSIX shell，用于既有启动器测试；Linux自动查找sh。包同时通过CRC、26份payload逐字节一致、Python3.8语法、安装保留bit/HWH/C库/历史日志检查。旧缓冲测试的历史间歇失败证据仍保留，本次通过不等于旧根因闭合。

未执行Vivado、FPGA加载/复位、实板采集或舵机动作。新提示和自定义窗口待用户在板端确认。临时测试目录自动清理，没有新增codex_out内容。
