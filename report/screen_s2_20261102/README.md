# S2 已保存实现的报告导出

2026-11-02 使用用户提供的原样 `export_bd_impl_reports.tcl`，在 Vivado 2025.2 GUI 对 S2 工程执行只读导出。器件 xc7z020clg400-2，impl_1 状态 `route_design Complete!`，脚本的实现未过期检查通过，`Export errors: 0`。

本目录完整五份报告来自同一次成功会话 `export_20261102_205236`：

- [BD 原生 PDF](bd_01_soundsight_stm32_bd.pdf)：1 页，保留当前布局与层级，已渲染核对模块及连线。
- [实现资源](utilization_report_imp.txt)。
- [分层资源](utilization_hierarchy_imp.txt)。
- [实现时序](timing_report_imp.txt)：约 9 MB；GitHub 无法预览时下载原文件。
- [导出信息](export_info.txt)。

| 项目 | 实测报告值 |
|---|---:|
| WNS / WHS / WPWS | +0.203 / +0.036 / +2.208 ns |
| TNS / THS / TPWS | 0 / 0 / 0 ns |
| LUT / 寄存器 | 19971 / 22358 |
| 无 input_delay / 无 output_delay | 3 / 30 |

已约束路径裕量为正，不代表完整 I/O 时序签核。Methodology 区是缓存结果；此次没有新增 CDC、DRC 或 bus-skew 检查。详细路径每组最多 50 条，不是所有违例的穷举。

原工程：`F:/NUEC/ss-screen-ps-i2c-s2/project/par/SoundSight_PS_3D.xpr`。该路径仅用于溯源，不是接收方运行依赖。S2 包含 J3 舵机引脚、RGB/VDMA/GPIO、PS I2C0/EMIO。S3/CF1A 属软件更新；本报告不能代表 A 后续硬件改版。

本次没有综合、实现、生成位流、保存 BD 或操作板卡；XPR 内容未变。`verification.json`、`input-identity.json` 及 `vivado-gui-retry.log/.jou` 保留成功会话的核对和原始记录。首次受限 GUI 启动失败、随后 batch 缺 PDF 的部分输出未混入此目录；失败原件保留在本地导出工作目录。

脚本及重新导出步骤见 [handoff](../../handoff/README.md)。复现源码来自已归档 S2 的 49 项配方/依赖；本次仅检查打包一致性，没有重新构建来声称另一份实现具有相同裕量。
