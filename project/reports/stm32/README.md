# STM32 主方案实现结果

这三份是用户外部工程的**实现阶段资料**，集中放在工程目录内；不是综合报告。

| 文件 | 内容 |
|---|---|
| [timing_report_imp.txt](timing_report_imp.txt) | 布线后时序报告：WNS +0.248 ns，WHS +0.036 ns |
| [utilization_report_imp.txt](utilization_report_imp.txt) | 实现资源报告：LUT 13894、FF 14458、BRAM 25、DSP 41 |
| [布局布线图.png](布局布线图.png) | 用户导出的布局布线视图 |

来源：用户工作工程 `F:/AMD/work/SoundSight_STM32` 的 `report` 目录。时序报告时间为 2026-10-18 14:53:59，资源报告时间为 14:54:45；器件 xc7z020clg400-2，Vivado 2025.2，顶层 soundsight_stm32_bd_wrapper。

本次仅原样归档已有报告与图片，没有启动 Vivado。截图用于查看布局，不代替时序、约束覆盖或板测证据。完整配置和交接范围见 [工程交接说明](../../../document/stm32-handoff.md)。这两份 TXT 从 document/evidence/stm32-handoff-20261018 移入本目录，旧位置不保留重复副本。

![布局布线图](布局布线图.png)
