# S2 工程复现与报告导出

与 [2026-11-02 S2 报告](../report/screen_s2_20261102/README.md) 配套。目录可单独复制到短 ASCII 路径，不依赖发送方 F 盘或 Vivado 安装位置。Vivado 版本为 2025.2，器件 xc7z020clg400-2。

## 内容与来源

- `screen_s2/`：49 项完整 S2 工程配方及 RTL、XDC、BD/IP、初始化数据，加可搬移 `build.bat`。由仓库 `tools/prepare_screen_s2.py` 生成；49 项内容与 `source-map.json` 逐字节校验一致。
- `source-map.json`：原仓库源码到交接相对路径的映射。开发仍维护 `project/` 等正式目录；本目录是可交接快照。
- `tools/export_bd_impl_reports.tcl`：用户提供的报告导出脚本原件，本次已在真实 GUI 导出成功。
- `tools/rebuild_tool.tcl`：用户提供的通用源码交接导出器原件，本次未执行。
- `tools/report-export-rules.md`：用户原说明原文，其“尚未在实际 GUI 导出”的描述是提供脚本时的历史状态；本次实际结果见 report。

整理基线为 main `77a85ed6072fa99e1138f5d8b96e123a68093437`。本次没有重跑 EDA、修改产品逻辑或操作硬件；未包含私人录音、声纹模板和板端标定。S3 面板和 CF1A 软件仍见仓库 `software/`，本目录仅复现 S2 PL 工程。

## 复现工程

将本目录复制到新的短 ASCII 路径，设置本机 `XILINX_VIVADO` 指向 Vivado 2025.2 根目录，或让 `vivado.bat` 可从 PATH 找到。进入 `screen_s2`：

```bat
build.bat
```

无参数只创建工程、BD 和 IP，不启动综合/实现。生成工程位于 `screen_s2/project/par/SoundSight_PS_3D.xpr`，随后可在 GUI 手动运行综合和实现。

如需命令行完整重建，在另一份尚无 `project/par` 的全新副本中运行：

```bat
build.bat route
```

此命令会运行综合、布线、审计并生成 bit/HWH/XSA，不下载到板卡。不能在已经执行无参数 `build.bat` 的同一副本上再次运行；旧输出受保护。仅综合使用 `build.bat synth`，同样要求新副本。重新实现后的数值应以新报告为准，不能沿用本次已保存实现的结果。

## 导出已有实现报告

在 Vivado GUI 打开准确工程，保存 BD，并确认目标实现已经布线且未过期。在 Tcl Console 执行（将占位路径换成你的本地路径）：

```tcl
source {交接目录/tools/export_bd_impl_reports.tcl}
```

默认使用当前 Implementation Run，输出到工程目录 `reports/export_年月日_时分秒/`，不覆盖旧结果。需要指定 run 或报告父目录，可在 source 前设置：

```tcl
set ::bd_impl_export_run impl_1
set ::bd_impl_export_dir {本机报告父目录}
```

脚本只读取已有实现，不自动综合、实现、下载或重排 BD。必须在 GUI 导出 PDF；batch 文本报告成功但缺 PDF 仍属于部分失败。五份文件齐全且 `export_info.txt` 中 `Export errors: 0` 才是完整导出，不等于设计签核通过。

## 从以后修改的工程重新交接源码

打开接收方实际修改后的工程，在 GUI Tcl Console 执行：

```tcl
source {交接目录/tools/rebuild_tool.tcl}
```

该工具会保存 BD，导出工程配方、BD Tcl、已登记源码/约束及清单到其计算的 `handoff/latest`，保留旧 latest 的备份；它不是只读报告工具。外部依赖需先复制进工程并登记，脚本会拒绝未解决的外部路径、自定义 IP 仓库等不完整交接。仅导出脚本成功不代表已完成重建或板测。本轮未调用它，也未把本目录说成该工具的实测输出。
