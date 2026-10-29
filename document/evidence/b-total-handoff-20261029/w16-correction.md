# 垂直引脚更正与复测边界

2026-10-29 用户复测并更正：水平舵机正常，垂直舵机接到 T15 后能够转动；垂直实际连接应为 W16，用户已在外部 Vivado 工程更正，正在实现和生成位流。这是用户现场报告，尚无新 I/O、时序或 W16 动作回读。

仓库当前约定为 servo_pwm=T15，servo_vertical_pwm=W16。已更新 PS XDC、bd_ps_link 注释、六个相关 Tcl 的引脚预期/检查、打包 I/O 检查与相关说明。引脚修复脚本允许已知旧 U7/W15 迁移到 W16，保留备份及冲突检查。正常更新配方要求输入工程已使用 W16，拒绝将旧 W15 工程误当新候选；用户当前已手动更正，不需要在运行中的工程重新执行脚本。RTL 控制、PS 命令、角度映射及停止行为未变。

## 实际检查

运行 `python -B software/tests/<文件>`：

| 文件 | 结果 |
|---|---|
| test_servo_pin_update.py | 8 项通过，含 W15→W16 迁移及原文备份 |
| test_dual_axis_tcl.py | 7 项通过 |
| test_dual_axis_report_tcl.py | 7 项通过 |
| test_horizontal_tcl.py | 4 项通过 |
| test_reliaze_tcl.py | 10 项通过 |

原始测试输出见 [w16-tests.json](w16-tests.json)。这些是 Tcl 离线工程模型，非真实 Vivado 运行或 RTL 仿真。

额外直接调用 tools/package_pynq.py 的 horizontal_pins：输入 project/reports/ps_3d/original/soundsight_stm32_bd_wrapper_io_placed.rpt，旧 W15 报告被拒绝；仅在内存中将该行 W15 替换为 W16 的合成输入通过。合成输入只验证检查器，不是新实现证据；原报告文件未修改。

现行源码、脚本和测试中剩余 W15 只用于旧针脚迁移识别与迁移测试。旧原件、失败记录、历史包未改。SD ZIP 未重打，外部工程未读写，未启动综合/实现/下载/复位/舵机动作。本任务未创建 codex_out 临时内容；测试临时工程由测试自动清理。

## 待用户新产物

取得同候选 bit/HWH/XSA、实际 I/O 与实现时序后，确认垂直 W16、水平 T15，再更新 SD 包并有限时间复测。旧 W15 的正时序余量与旧软件成功提交不能代替 W16 板测。
