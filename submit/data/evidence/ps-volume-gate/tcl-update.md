# Volume工作工程一键准备脚本

**最新结论：完整入口已在Vivado 2025.2的隔离工程副本中通过模块刷新、BD Validate和输出生成。** 本文前半保留早先替身测试及现场失败事实，最终验证见末节，不能把各阶段结果混用。

2026-10-21，用户指定复制出的目标为`SoundSight_PS_Volume`。只读确认本机存在`F:/AMD/work/SoundSight_PS_Volume/SoundSight_PS_Volume.xpr`；此路径仅记录现场，不写入脚本默认值。AI没有打开或写入外部Vivado工程。

入口：`project/bd/update_ps_volume.tcl`。实际复制10份RTL进入当前工作工程，备份旧文件和BD/XPR，保留文件类型/库/综合仿真属性，重新登记促使源文件重读，再刷新模块、连线、Validate并生成输出文件。原Wrapper不变，不启动物理构建或硬件动作。工具路径和工程路径均由当前Vivado会话确定。

离线测试：`python -B -X utf8 software/tests/test_ps_volume_tcl.py -v`，5项通过。真实Tcl8.6解释器、真实带空格文件路径及复制/备份，Vivado命令使用替身。覆盖正常更新与重复执行、外部源复制后原件不变、在途运行拒绝、重复源拒绝、Validate失败后无成功标记且保留备份。测试生成的临时目录已在退出时清理。日志为`test_ps_volume_tcl.log`。

这些结果不证明实际Vivado刷新/Validate/输出生成成功；没有替用户运行Vivado，也没有新STA或bit。上轮RTL与功能自测结论保持。

命令核对依据：[AMD UG835 2025.2 update_module_reference](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/update_module_reference)、[generate_target](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/generate_target)。模块刷新与重新读取源文件分开执行，不使用会吞掉执行错误的`-quiet`调用刷新、Validate或生成命令。

## 现场失败后的修复

用户回传10份源码复制完成后，`update_module_reference {compute ps_link}`退出，未到Validate/输出生成。原文及分析保存在`REFRESH-FAILURE.md`，旧脚本保存在`failed-update_ps_volume.tcl.txt`。原5项替身测试错误地接受了BD显示名，没有覆盖真实生成IP名；不能把那次通过当成Vivado调用验证。

修复按当前BD名称前缀和`IPDEF`获取唯一的`get_ips -all`对象，逐个`update_module_reference -verbose`，并打印错误信息。新增`resume_ps_volume.tcl`仅继续刷新/连线/输出生成，校验已复制的10份源码，不再次复制。7项离线测试通过，新增刷新失败接续不改源码/不新增备份和未复制拒绝两项。实际Vivado结果仍待用户运行。

## 第二次现场失败与完整入口验证（当前结论）

用户随后回传`ss_ps_level::apply`检查`compute`时找不到`CONFIG.LEVEL_ENABLE`。磁盘源确有新参数，但旧会话中的模块信息未完整更新；前面的替身测试不能证明Vivado模块状态刷新成功。本次改成完整顺序：复制并重新登记源 → 保存BD并关闭/重新打开当前工程 → 按实际IP对象显式刷新两个模块 → 核验新参数/端口并连接 → Validate → Global模式输出生成。

另发现复制出来的Volume工程仍使用原PS工程的两份有效XDC。现在把它们原样复制到当前工程`ps_constraints`，仅改变登记路径，保留实际内容和适用的文件属性。没有用仓库默认约束替换现场约束。

真实测试使用用户工作工程的只读副本，并恢复首次备份的10份旧RTL作为起点；测试工作目录为`simulation/work/vbt`，不是用户F盘工程。开始时`INITIAL_COMPUTE_LEVEL_PRESENT=0`，最终两个模块均为`LEVEL_ENABLE=1`，两条音量线连通，生成的两个模块包装器也实际传入`.LEVEL_ENABLE(1)`。Vivado进程返回0，原文包含`PS_VOLUME_READY_FOR_GENERATE_BITSTREAM`和`REAL_VIVADO_VOLUME_PREP_PASS_NO_SYNTH_IMPL`。原始日志、前后BD及配置对照在[native-bd](native-bd/readme.md)。

前后对照结果：旧普通连线、AXI接口连线、外部端口和地址映射一致；PS寄存器仍为`0x40000000/4K`；时钟、复位、AXI基础设施等其他组件一致。10份实际RTL与交付源码逐字节相同，2份实际XDC与原件逐字节相同。PS7的878项XCI参数中，只有8项未启用的交叉触发选择由`DISABLED`被工具规范化为`<Select>`；交叉触发和CoreSight使能仍为0，其余参数一致，DDR/MIO及时钟配置未变。BD保存时也将一些原先省略的默认参数显式写出，不声称BD文件逐字节不变。

日志并非零警告：有本机TclStore目录警告，以及新增模块端口导致的升级警告；最终连接检查和Validate通过。没有迁移工具IP、升级PS7、重建PS板级配置。实际综合、实现、时序、bit/HWH及音量板测仍未执行，由用户继续。

本轮还捕获并修正了XDC不支持`USED_IN_SIMULATION`、关闭工程后旧BD对象引用失效、仅重新打开工程而未刷新端口三处问题。隔离测试搭建曾遇到Windows长路径和TclStore初始化问题，缩短隔离路径并为测试进程显式提供安装目录的Tcl包路径后继续，未重置用户TclStore。一个反复修改的测试副本曾出现PS7临时锁定；重新读取时IP状态为Up-to-date，干净旧源副本完整运行通过，没有靠自动升级PS7绕过。失败原件保留于`native-bd/failures.zip`。

测试入口：`python -B -X utf8 software/tests/test_ps_volume_tcl.py -v`，当前7项通过；原生日志对应命令为隔离目录中的`vivado.bat -mode batch -source full.tcl -log full-isolated.log -journal full-isolated.jou`。完整构建、下载和复位命令不在此次脚本中。用户现在统一执行`update_ps_volume.tcl`，无需再组合旧的两个接续入口。
