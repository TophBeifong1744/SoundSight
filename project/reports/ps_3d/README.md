# 最新：W16用户实现

2026-10-29新候选见 [w16/README.md](w16/README.md)。下面10月28日W15报告保留历史范围。

# SoundSight_PS_3D 实现与补查报告

`original/`是用户2026-10-28生成位流时的原始实现报告；`supplemental/`是助手使用Vivado2025.2读取同一个routed DCP后补出的报告。原bit、HWH、DCP、BD、XPR逐字节未改，不曾重新综合/布局/布线或访问硬件。

- 原时序：WNS +0.311ns、WHS +0.036ns、WPWS +2.208ns；setup/hold失败端点0。
- 资源：LUT18006/53200，FF19753/106400，BRAM32/140，DSP41/220。
- 原配方遗漏垂直PWM最大路径预算。补查仅在内存添加垂直20ns约束，端口余量+12.608ns；水平全口余量+11.077ns。check_timing中未约束内部端点和输出均0，全局时序不变。
- PWM是异步输出，没有外部同步采样钟；`-datapath_only`的外部hold不适用。min报告仅展示数据路径，不能当成0ns hold已验。内部hold仍按全局报告检查。
- 12组bus-skew均满足；CDC为22项CDC-3 Info、1252项CDC-15 Warning，无Critical。旧厂商IP的LUTAR/BRAM异步控制等告警保留，不等于零告警或完整RDC签核。

持久修正位于`project/sdc/ps/dual_axis_output_timing.xdc`，只由双轴更新Tcl登记，供下一次重建使用。此次原路由在该预算下已满足，不需要为补报告重生成位流，也不要为此重跑整个更新Tcl。

来源、未测范围及独立复核见`document/evidence/ps-dual-axis-20261028/hardware-review.json`和`user-build-receipt.json`。实际三维ARM、麦克风CH映射、两轴机械标定和闭环仍待板测。
