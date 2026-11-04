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

## 工程复现与报告生成

### 环境要求

- Windows、Python 3、Vivado 2025.2，安装 `xc7z020clg400-2` 器件支持。
- 将 Python 和 `vivado.bat` 加入 PATH，或设置 `XILINX_VIVADO` 为本机 Vivado 安装根目录。
- 工程输出目录使用新的空目录，完整路径为 ASCII 字符且不超过 78 字节。

### 从提交包创建工程

完整解压 `submit`，在其根目录打开终端，依次执行：

```bat
python -B build/prepare_workspace.py --output ../soundsight_work
cd ../soundsight_work
python -B tools/prepare_screen_s2.py --output ../s2_work
cd ../s2_work
build.bat
```

第一步从提交包恢复源码及脚本的目录结构；第二步准备 S2 工程的 49 项输入，并创建 `reports`、`output` 输出目录；最后一步生成工程、BD、IP 和 wrapper。工程文件为 `s2_work/project/par/SoundSight_PS_3D.xpr`。打开该工程后，可在 Vivado GUI 中执行综合、实现和位流生成。

从仓库源码开始时，在仓库根目录执行 [S2 工程准备脚本](../../tools/prepare_screen_s2.py)，随后进入输出目录运行 `build.bat`；无需执行提交包的源码恢复步骤。

若直接复制 [handoff 中的 S2 配方](../../handoff/screen_s2/README.md)，进入复制后的 `screen_s2` 目录，先准备输出目录，再创建工程：

```bat
if not exist reports mkdir reports
if not exist output mkdir output
build.bat
```

### 综合、实现与位流

命令行运行综合、实现及 bit/HWH/XSA 导出时，在另一份新准备的 S2 输出目录中执行：

```bat
build.bat route
```

仅执行综合使用 `build.bat synth`。每次调用均使用尚无 `project/par` 的新副本；已有工程的后续运行在 Vivado GUI 中进行。完整步骤与产物说明见 [工程交接说明](../../handoff/README.md)。

### 导出 BD、资源和时序报告

在 Vivado GUI 中打开目标工程，确认实现已完成布线且未过期。在 Tcl Console 执行以下命令，将路径替换为本机恢复工作目录中的脚本路径：

```tcl
source {<soundsight_work的绝对路径>/handoff/tools/export_bd_impl_reports.tcl}
```

[报告导出脚本](../../handoff/tools/export_bd_impl_reports.tcl)读取已有实现，默认输出到工程目录下 `reports/export_年月日_时分秒/`。本项目输出包括 BD 图 PDF、实现资源、分层资源、实现时序及 `export_info.txt` 五份文件；`Export errors: 0` 表示导出完成。BD PDF 需在 GUI 会话中生成。

本目录保存 2026-11-03 的 S2 实现报告，供设计分析与结果对照。重新构建后生成的资源和时序结果以新报告为准。`reports` 为工具输出目录，提交包中的 `report` 为设计文档目录。
