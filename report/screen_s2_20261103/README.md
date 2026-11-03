# S2 硬件报告与 P1 软件交付 — 2026-11-03

本轮使用用户提供的原样 `export_bd_impl_reports.tcl`，在独立 Vivado 2025.2 GUI 会话只读打开现有 S2 工程。
器件 xc7z020clg400-2，impl_1 为 `route_design Complete!`，脚本的实现过期检查通过，`Export errors: 0`。
没有启动综合、实现、位流生成或板卡操作；XPR 导出前后内容一致。

## 同一次会话的五份原生输出

- [BD 图 PDF](bd_01_soundsight_stm32_bd.pdf)：一页，当前保存布局，已解析并渲染核对。
- [实现资源](utilization_report_imp.txt)。
- [分层资源](utilization_hierarchy_imp.txt)。
- [实现时序](timing_report_imp.txt)：约 9 MB，包含未约束路径及 check_timing；每组详细路径最多 50 条。
- [导出信息](export_info.txt)。

会话为 `export_20261103_163331`；原始 [日志](vivado-export.log)、[journal](vivado-export.jou) 和 [核对记录](verification.json) 一并保留。
本轮重新运行导出脚本，未将 11 月 2 日旧报告改日期冒充新导出。

| 项目 | 本轮报告值 |
|---|---:|
| WNS / WHS / WPWS | +0.203 / +0.036 / +2.208 ns |
| TNS / THS / TPWS | 0 / 0 / 0 ns |
| LUT / 寄存器 | 19971 / 22358 |
| 无 input_delay / 无 output_delay | 3 / 30 |

这些数值与此前同一已保存实现一致。已约束路径裕量为正，不代表完整 I/O/CDC 签核。
报告中的 Methodology 是缓存结果：LUTAR-1 3 项、XDCB-1 6 项；本轮没有新增 CDC、DRC 或 bus-skew 检查。
导出日志保留要求执行 report_bus_skew 的提示，不把报告生成成功等同所有检查通过。

## 软件更新和验收边界

最新 P1 软件基线为 `eb05bd5bfa2e5f8d3d01d494965497bd70e3209e`（PR #43）。
在 S3 面板上增加开机自动准备、触屏声纹录入、模式保存、异常停止与确认关机；保留 S2 硬件、CF1A、CP1/VF1 和 score_ttl_v2。
安装包：[soundsight_screen_product_p1.zip](../../release/output/soundsight_screen_product_p1.zip)。
操作与两轮冷启动步骤：[产品化说明](../../document/screen-product.md)。

已有 [P1 软件证据](../../document/evidence/screen-product-p1-20261103/README.md) 记录 141 项离线测试通过，其中新增 43 项。
用户回报 C 的此前声纹、三维转向及屏幕功能测试通过；板子当前不在线，新 P1 自启、录入、屏幕关机及冷启动仍待本板测试。
硬件报告不能用于证明软件启动时间、整机响应、三维精度或识别率。

## 复现

原样脚本、使用规则和 49 项 S2 依赖见 [handoff](../../handoff/README.md)。
软件、安装包、报告和复现脚本同时由统一导出器放入 submit 的七类实体目录。
原工程 `F:/NUEC/ss-screen-ps-i2c-s2/project/par/SoundSight_PS_3D.xpr` 仅用于本次溯源，不是接收方运行依赖。
旧报告仍在开发仓库历史目录；submit 本轮只保留当前导出。
