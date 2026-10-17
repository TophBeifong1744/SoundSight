# 拓芙 Vivado 2025.2 环境与器件检查

记录日期：2026-09-07。证据来源：拓芙在工作执行聊天中粘贴的 Tcl Console 输出；本记录不是 Codex 本轮直接启动 Vivado 得到的日志。

```text
version -short
2025.2
get_parts xc7z020clg400-2
xc7z020clg400-2
```

结果：拓芙当前运行的 Vivado 版本为 2025.2，目标器件查询可返回 `xc7z020clg400-2`。仅此环境检查通过，WP-A4 整体及 M0 未通过；不代表 IP 兼容、综合、时序、DDR、PYNQ 或板测成功，也不证明另外两名成员环境通过。后续空工程创建证据单列如下。

## 独立空工程创建

用户回传 Project Summary 截图：工程实际名称为 `one`，实际位置为 `F:/College/verilog_digital_system/AMD/Competiton/one`，不再使用先前建议的 `soundsight_m0` 路径。器件为 `xc7z020clg400-2`，Target language 为 Verilog，Simulator language 为 Mixed；Top module 未定义，Synthesis/Implementation 均为 Not started。

该截图支持“独立空工程已建立”，不代表 PS 已配置、BD 验证或构建通过。后续在此工程中由用户添加 `design_1` 和 ZYNQ7 Processing System；不套用其他板卡 preset、不升级旧工程、不提前添加采集/声学模块。

## 关联的旧工程依据

用户提供的旧工程实际路径为 `F:/College/verilog_digital_system/Xilinx/g_signal_analyzer`。此前只读核验：

- `g_signal_analyzer.xpr` 第 2 行标记 Vivado 2018.3，第 10 行 part 为 `xc7z020clg400-2`。
- `g_signal_analyzer.srcs/sources_1/bd/design_1/design_1.bd` 的 device 与 tool_version 同样为该器件和 2018.3；PS 使用 `processing_system7:5.5`。
- PS 配置的 Bank 0/1 为 3.3 V/1.8 V，UART0 为 MIO 14..15；DDR 兼容预设 `MT41J256M16 RE-125`，32 bit，配置频率约 533.333 MHz；PS 输入 33.333333 MHz，FCLK0 100 MHz。
- 旧工程 PS XCI 中 ENET0、SD0、USB0 均未启用，不能直接作为 PYNQ 启动配置。
- 历史 routed timing report 头部标记工具 2018.3、速度等级 -2；只用于交叉核对旧工程身份，未据此宣称新项目时序通过。

结合用户确认，完整器件型号不再是未知项。旧工程持续保持只读，不能在原位置升级。2025.2 最小工程另建，初期仅配置板级基础系统；四路采集接口和下游声学 RTL 仍受原有准入约束。
