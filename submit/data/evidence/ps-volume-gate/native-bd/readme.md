# Vivado真实准备检查

2026-10-21，Vivado 2025.2，xc7z020clg400-2。仅运行隔离工程的源码复制、模块刷新、BD Validate、Global模式输出生成；未综合、实现、下载或操作硬件。用户F盘工程未由AI写入。

- `result.json`：前后对照结果与未测边界。
- `vivado-preparation.log`：完整原始stdout，Windows GB18030编码，末尾真实退出流程成功；不是无警告日志。
- `before.bd`、`after.bd`：隔离输入和输出，供核对旧连线、边界、地址、其他组件与新增音量线。
- `ps7-effective-parameters-*.json`：实际XCI中的878项参数值。仅8项未启用的交叉触发选择被工具规范化，其余一致。
- `board_pins.xdc`、`interface_timing.xdc`：此次核验的真实约束副本，仅证据用途；更新脚本读取用户当前工程登记的约束，不从这里安装。
- `sim-*`、`synth-*`：工具生成的两处模块包装器文本，确认新端口及LEVEL_ENABLE=1；文件夹名synth不代表执行过综合。
- `native-check.tcl.txt`、`native-launcher.py.txt`、`prepare-isolated-copy.py.txt`、`audit-result.py.txt`：本次测试/对照原件，含测试时的本机路径，不是用户操作入口或公共默认配置。
- `failures.zip`：保留本轮隔离验证中有用途的失败原始日志。包含长路径、工具包初始化、约束属性、BD引用失效、新端口缺失、临时PS7锁定；末次测试附件曾使用不存在的report_bd_address命令也保留，已改为get_bd_addr_segs。最终干净验证不用这些失败作为通过证据。

原测试过程位于`simulation/work/volume_bd_fullcheck`、`vbc`、`vbt`；归档后清理这些本任务创建的临时工程、缓存和辅助脚本。其他仿真成果保留。用户使用的正式入口仍是仓库`project/bd/update_ps_volume.tcl`，不要source这里的历史测试脚本。
