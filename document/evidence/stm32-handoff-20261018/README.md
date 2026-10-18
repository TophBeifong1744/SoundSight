# 用户实际 STM32 工程配方接回记录

输入：`F:/AMD/work/SoundSight_STM32/handoff/20261018_153509`，为本次读取时 handoff 下唯一导出批。用户手工工程是 `SoundSight_STM32.xpr`，器件 `xc7z020clg400-2`，Vivado 2025.2。

- `original/`：四份原始导出，原样保存。里面的路径属于历史原文，不是活动工程依赖，不应直接 source 原始 project.tcl。
- [实现报告与布局布线图](../../../project/reports/stm32/README.md)：按用户要求集中放在工程目录 `project/reports/stm32`，本目录不再重复存放。用户外部工程已有布线后报告。时序报告时间 2026-10-18 14:53:59，资源报告时间 14:54:45；不是本次运行的新结果。
- `source-comparison.json`：当前磁盘 26 份源文件、两份 STM32 XDC 的逐项比较，以及从实际生成 IP 的 XCI 读取的关键默认参数。RTL 仅一处行尾空白不同。比较范围不包含 PS 目标构建，也不证明 DCP 当时输入未发生漂移。
- `check_export.py`、`static-result.json`：以普通 Tcl 解释器记录原始和整理后配方的创建/属性/连接命令，比对 13 单元、30 普通网络、两接口网络和布局；核两个 FFT 显式配置、运行属性与交接文件清单。工具调用被记录函数替代，不调用 Vivado。
- `project-check.json`：仓库既有静态结构检查结果。

在仓库根目录使用带 tkinter/Tcl 的 Python 3 执行：

```powershell
.\tools\python.bat document/evidence/stm32-handoff-20261018/check_export.py
.\tools\python.bat tools/check_project.py
```

本批范围：配置接回及静态比较。原导出不设置的 IP 默认值依赖 Vivado 2025.2；例如 io_release 的低有效参数已从实际 XCI 读到，而非根据导出省略项猜测。两个 FFT 的组件名称由 create_ip 指定；禁用的 blocking_run_time_configuration 字段原件均为 false，公共配方未另作覆盖。

未执行：Vivado 重建/Validate/IP输出生成、RTL 仿真、综合、实现、CDC/RDC 专项复核和板测；本次也未审定用户先前 RTL/XDC 修改的全部功能语义。已有实现成功不等于 PS 启动、SPI 或声学机械闭环已通过。

接回版本见 `project/bd/stm32.tcl`、`project/ip/ps7_stm32.tcl`、`project/script/stm32_settings.tcl`。这次保留了工程实际配置，没有修改公用 ABI、数值或停止行为。临时工作未使用 codex_out；无待清理临时工程副本。
