# 用户导出的实现报告

本目录保留用户2026-10-30 17:03:06导出的六个原文件，不是本次AI重新运行Vivado。原件中的工作路径仅是历史来源，不是工程重建依赖。

- `timing_report_imp.txt`：已布局布线候选，setup WNS **+0.176ns**、TNS0、失败0/68646；hold WHS **+0.029ns**、THS0、失败0/68507；WPWS **+2.208ns**、脉宽失败0。
- `utilization_report_imp.txt`：LUT18226/53200（34.26%）、FF19753/106400（18.56%）、BRAM32/140、DSP41/220。
- `utilization_hierarchy_imp.txt`：逐层资源；`export_info.txt`：impl_1 write_bitstream Complete，导出错误0。
- `imp_schematic.png`实际是器件布局布线视图，并不是逻辑原理图；`bd_01_soundsight_stm32_bd.pdf`是当前BD导出视图，文件名保留历史名称。

**物理结论边界：** 报告明确列出 `servo_vertical_pwm` 缺少输出延迟。该输出路径Slack=inf，数据延迟7.917ns，不能当成垂直输出时序已经闭合。其余受约束路径通过；不能宣称所有I/O约束齐全。旧W16候选的补查证据不能继承给本候选。没有导出新的CDC报告；缓存Methodology提示仍有LUTAR-1两项、XDCB-1四项，需要完整物理签核时结合当前设计核查。

最新可搬移配方含第五份垂直输出预算约束，但实际产物登记为四份约束；本次未重建，所以不能将已导出的时序结果绑定到重新运行第五份约束后的工程。本次只收件、检查和归档，不修改用户工程，也不安排重复综合实现。
