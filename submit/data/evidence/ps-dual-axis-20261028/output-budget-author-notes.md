# 双轴PWM输出补查入口：作者记录

本批为 `BUILD_FLOW`，准备现有 routed 设计的报告入口和未来重建的垂直输出预算。未运行 Vivado，未改用户 F 盘工程；本文件不构成 STA 或独立验收。

- **Scope/Assumptions**：Vivado 2025.2、xc7z020clg400-2、原 `soundsight_stm32_bd_wrapper`，水平 T15、垂直 W15、LVCMOS33，两路 guard 同为 61.44MHz。已只读核对原报告：垂直 max/min 数据路径为 7.392ns/4.337ns，原 slack=inf；它表示覆盖缺口，不能直接当作时序失败。
- **Changed Files**：新增 `project/sdc/ps/dual_axis_output_timing.xdc`；双轴更新 Tcl 仅增加该 XDC 的复制/登记，保留旧约束原文；新增 `project/bd/report_ps_dual_axis.tcl`；更新/新增两份离线 Tcl 测试。
- **Behavior/Latency/Throughput**：无 RTL、采样、流水、吞吐、停止或错误语义改变，Cycle Contract Delta 不适用。
- **Clock/Reset/CDC/RDC**：不改时钟/复位/CDC 结构。新 XDC 只加垂直寄存器到端口的 20ns 最大数据路径预算，和既有水平预算一致。`set_max_delay -datapath_only` 自动忽略 hold；异步舵机 PWM 没有外部采样时钟，因此 min 路径仅报告，状态明确标 `HOLD_N_A`，不声称 0ns hold 通过。
- **Register/IRQ/DMA**：不变。
- **Vendor/Target Impact**：无 IP/工具升级。报告入口只在内存加载新 XDC；不登记文件、不写 XPR/DCP/bit、不启动构建和硬件。持久 XDC 仅由双轴更新 Tcl 在用户以后选择复建时登记。
- **Evidence**：`output-budget-tcl-tests.txt`，14 项作者离线模型测试通过，Python 3.14，命令 `python -B -m unittest discover -s software/tests -p "test_dual_axis*tcl.py" -v`。检查带空格路径、重复登记、用户文件保护、缺失/活动/过期运行、错误器件/引脚、空路径、负 max/global hold slack、无穷 max slack、错误预算、旧水平驱动最差路径及 min=inf 可接受。模型 XPR/DCP/bit/原报告前后 SHA256 一致；所有临时模型目录自动清理。
- **Unverified Items/Risks**：未运行原生 Tcl/STA、Validate、综合、实现、位流或板测；报告命令的真实返回与设计对象仍需原生运行确认。CDC/DRC/异常覆盖报告必须由非作者结合实际结构判断；`REPORTS_COMPLETE` 只表示报告齐备及脚本所列最大路径检查完成。当前 DRC 默认每 rule 上限会截断 REQP-1839/1840，协调者在原生诊断中确认实际可用属性后补全，不凭猜测设置未知参数。功耗不在本批范围。
- **Handoff to Review**：先读取 `output-budget-snapshot.json` 的同一文件快照；协调者可在隔离会话打开原 routed DCP，设置 `ss_dual_axis_report::library_only=1` 后 source，再调用 `ss_dual_axis_report::audit <out>`。该过程保留内存视图，调用者结束时丢弃，不保存。用户普通 source 入口核对外部 3D/DualAxis 工程与 impl_1，要求先关闭已有设计视图，结束时关闭它自己打开的视图。原报告和工程文件不清理。

## 非作者发现与修正

复核对象为初版报告 Tcl SHA256 `EBDBF1DA7C5A93009645532E10436462F3C5FC4D88CC7ACAE31ACF5697871232`。

- **DAOUT-001**：水平输出仍合并声音、手动和双轴路径，原最差路径来自 `manual/guard/pwm_o_reg/C`，不能强制全口 worst 必须来自双轴 h_guard。修正为全口 max 检查 20ns 和有限非负 slack，另加每轴双轴 guard 的定向 max 报告/非空检查。
- **DAOUT-002**：最初误把 `set_min_delay 0` 当作覆盖 `datapath_only` 的隐含 hold false path。按官方 UG835 `set_max_delay` 语义及原水平报告中的 `Timing Exception: False Path` 修正；删除新 XDC 无效 min，min 用 `-user_ignored` 保留原始路径且标 N/A，不改原 XDC。修复影响仅报告判据和新垂直预算，电路无变化。

命令依据为安装版 Vivado 2025.2 的官方 `doc/eng/man/{set_max_delay,open_run,close_design,report_timing,get_timing_paths,report_cdc,report_bus_skew,report_exceptions,report_drc}`，并核对 [UG835 open_run 2025.2](https://docs.amd.com/r/en-US/Vivado-Design-Suite-Tcl-Command-Reference-Guide-UG835/open_run)。

## 作者测试失败事实

首次 14 项模型执行有 1 项失败：Python/Tk 默认对象转换把单元素 Tcl list 变成 Python tuple，调用记录断言得到 `('open_run', "('impl_1',)")`。脚本已成功走完该路径；这是测试记录序列化问题。仅将报告测试解释器设为 `wantobjects(False)` 后重跑通过。非作者指出的两项产品判据随后合批修正并重新执行全部 14 项通过，最终证据文件为该修正版运行。

本批未创建 codex_out；临时模型树只在 simulation/work，测试结束已删除。没有清理其他任务文件。
