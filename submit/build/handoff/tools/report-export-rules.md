# 通用 BD / 实现报告导出

脚本：`project/script/export_bd_impl_reports.tcl`。可以单独复制到其他项目使用，没有工程名、器件或本机路径依赖。

在 Vivado GUI 打开目标工程，保存 BD 修改，确认目标实现已完成布线。在 Tcl Console 执行（把示例换成脚本实际位置；路径有空格也保留花括号）：

```tcl
source {脚本所在目录/export_bd_impl_reports.tcl}
```

默认使用当前 Implementation Run，不要求名字为 impl_1。需要选择其他 run 时，在 source 前执行：

```tcl
set ::bd_impl_export_run impl_2
```

结果自动放在当前工程目录的 `reports/export_年月日_时分秒/`，重名自动加编号，不覆盖上次结果。可选指定报告父目录（相对路径以 Vivado 当前工作目录为基准）：

```tcl
set ::bd_impl_export_dir {./my_reports}
```

以上覆盖项在本次 Vivado 会话中持续有效，恢复默认可执行：

```tcl
unset -nocomplain ::bd_impl_export_run ::bd_impl_export_dir
```

## 输出

- `bd_01_设计名.pdf`：每个已登记 BD 各一份横向 PDF，采用当前布局，不自动重排。显示当前层级的图，不自动展开每个层级。
- `utilization_report_imp.txt`：实现资源利用率。
- `utilization_hierarchy_imp.txt`：按模块层级统计的实现资源利用率。
- `timing_report_imp.txt`：实现 setup/hold 时序汇总、详细路径、未约束路径及 check_timing 信息；每组最多 50 条路径，不代表穷举所有违例。
- `export_info.txt`：工程名、实现 run、Vivado 版本、导出错误。

没有 BD 的纯 RTL 工程会跳过 PDF，仍导出实现报告。PDF 或单项报告失败时会保留已成功的文件，并报出具体错误，不显示完整成功。

只读取已有实现，不启动综合、实现或下载，不修改 RTL、约束和 BD 连线。会打开 BD 和一个单独命名的实现设计视图。未完成布线或已过期的 run 会停止导出；时序负裕量仍会正常导出，便于分析。BD PDF 是当前设计图，实现报告来自保存的 run；两者一致性仍取决于工程是否正确保存并重新实现。

命令依据 AMD UG835：[write_bd_layout](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/write_bd_layout)、[report_timing_summary](https://docs.amd.com/r/2021.2-English/ug835-vivado-tcl-commands/report_timing_summary)。

本脚本完成 Tcl 模拟环境的流程检查；尚未在实际 Vivado GUI 中导出 PDF，不把模拟检查当作真实 EDA 验证。
