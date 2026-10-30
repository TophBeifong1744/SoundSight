# 导出兼容性修正

用户实测不支持-ignore_utils，已移除。10项离线测试通过，其中真实2025.2归档project.tcl检查旧DCP依赖移除、设计与PS配置保留及Tcl完整性。测试命令：`python software/tests/test_portable_export.py -v`。

help-query-failed.txt为无工程工具帮助查询失败原件；本地Tcl Store目录损坏告警导致命令未注册，没有据此声称实际导出通过，也未修复/重置用户工具环境。日志路径只为原始证据，不是脚本运行依赖。

用户当前工程、位流、综合实现结果均未修改；待用户再次导出。

## JSON相对路径误判闭合

旧检查把BD的`ip\\模块\\模块.xci`内部转义分隔符误判为UNC；已加路径起始边界。11项测试通过，其中10组路径正负例验证相对JSON/普通Windows路径放行、真实驱动器/UNC/Unix用户目录拒绝。用户本轮.pending配方所引用的40份实际输入及recipe/独立BD Tcl全部扫描通过。只读核对，原BD/位流未修改；实际再次导出仍由用户执行。
