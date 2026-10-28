# 板端统一准备与门限工具验证

2026-10-22。目标是把用户已经验证的手动长命令封装为`prepare`，并提供保存门限/单次覆盖、normal/debug、状态检查和旧帧排空，不改算法或位流。

源码：`soundsight.sh`、`software/ps/board_tools.py`；安装器增加显式`--prepare`，不带参数时仍只安装、不碰硬件。现有采集核心和中文转英文结果保留。

## 真正运行过的检查

- `python -B -X utf8 tools/package_normal_update.py`
- `python -B -X utf8 tools/check_normal_update.py`
- Git Bash对`soundsight.sh`执行语法检查及`--help`；临时指定本机Python，只读帮助，不导入PYNQ、不运行下载。
- 从既有`soundsight_pynq_volume.zip`读取实际配套bit/HWH到临时目录，运行新HWH检查，确认compute/ps_link音量能力、ACTUATOR_BOUND=0、AXI地址0x40000000/4096字节。结果见`actual-hwh-check.json`。原bit/HWH未修改。

实际ZIP解压、安装到隔离假目录后共121项通过：启动工具15、英文3、原SMP17、正常模式17、安装5、批量写盘6、RAM24、角度19、音量15。每组原始输出及退出码保存在本目录。非法参数的error为预期负例；模型打印LOADED=True不代表对实际板子的访问。

必须保留的波动：补充寄存器读取转Python int后的一轮包验证，旧`test_online_filter_in_real_spawn_queue_with_slow_writer`出现`kind=error`，断言未带具体result。原输出为`test_buffered-failure-001.log`、`checks-failure-001.json`。只增强该测试断言显示result，没有修改RAM/SD产品代码或放宽超时；随后完整24项重跑通过。旧收件时也曾有同类无详细信息的间歇失败，根因仍未确定，不能因后续通过就关闭。这不属于新增prepare/门限功能的通过证据，需和板端debug积压事实分别保留。

启动模型重点覆盖：首次下载顺序、4×4分频、已经加载时不重载、旧帧不清除、非STOP故障不清除、ID/ABI/能力失配、时钟/复位不对时不读PL、未知其它overlay不覆盖、离线自测失败不发READY、门限持久化与边界、单轮覆盖不修改保存值、normal/debug/BIST默认帧数及无动作参数。

安装检查覆盖根目录shell入口、本地设置保留、文件备份、路径越界、`--prepare`可选且仅在安装锁关闭后执行。实际更新payload24份逐字节一致，Python3.8语法检查通过，ZIP CRC通过；bit/HWH、C库和日志未被替换。临时目录自动清理，无codex_out遗留。

## 未执行的部分

新封装尚未在ARM板端执行。主机使用假寄存器/overlay验证流程，不声称PYNQ驱动、硬件下载、声学精度、长稳或舵机通过；本次无Vivado构建/下载/复位/物理动作。

准备函数来自已在本板成功的手动加载命令，并核对[PYNQ 2.7官方Overlay源码](https://github.com/Xilinx/PYNQ/blob/v2.7.0/pynq/overlay.py)中download=False、clock_dict和is_loaded语义。is_loaded依赖PYNQ元数据，不是独立的位流内容证明；同一位流登记后不再自动下载，另读ID/ABI及状态。不修改系统启动脚本，不建立开机无人值守下载服务。

以前的英文提示证据、正常模式及B板测失败/原始日志均保持原目录。新入口不能替代尚未完成的正常模式板端统计回传，也不能把debug高水位失败改写为成功。
