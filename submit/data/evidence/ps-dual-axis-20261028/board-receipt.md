# 2026-10-28 三维候选位流收件与完整SD包

用户已完成从Reliaze复制的SoundSight_PS_3D。`user-build-receipt.json`记录实际XPR/BD/HWH、原位流、routed DCP、41个登记项和报告。31份手写RTL与仓库`project/rtl`文本一致（少数换行/BOM字节差异无功能变化），未从旧目录倒填候选。本轮没有改RTL数值、停止或握手行为，也未修改用户F盘工程。

## 实现和约束覆盖

原始实现：WNS +0.311ns、WHS +0.036ns、WPWS +2.208ns；LUT18006（33.85%）、FF19753、BRAM32（22.86%）、DSP41（18.64%）。37050条需布线网络全部完成，T15/W15实际Bank34/LVCMOS33。

收件发现唯一未约束输出为垂直PWM。原更新配方漏带该预算，这不是已证明的时序失败。新增`project/sdc/ps/dual_axis_output_timing.xdc`，只随双轴Tcl复制登记；当前用户候选仅以原routed DCP读入Vivado2025.2，内存补20ns最大延迟预算后出报告。未执行opt/place/route/synth、write_checkpoint或write_bitstream。

补查结果：垂直余量+12.608ns，水平全合法来源最差+11.077ns、新双轴水平来源+11.188ns；全局.311/.036不变，check_timing十二类全0，12组bus-skew全部满足。PWM没有外部同步采样时钟，datapath-only导致外部hold不适用；min报告只是数据延迟，不声称0ns hold通过。内部hold仍为+0.036ns。

原始与补充18份报告分别在`project/reports/ps_3d/original`、`supplemental`。独立只读`dual_axis_physical_review`从原报告、脚本和真实补查确认限定范围通过，见`hardware-review.json`。CDC有22项CDC-3 Info、1252项CDC-15 Warning（1154特征FIFO、98 PCM FIFO），0 Critical；既有IP异步复位告警、DRC显示上限及8条无现存路径例外保留。不能据此宣称全RDC或整机验收。

原bit、HWH、DCP、BD、XPR在补查前后逐字节未变。原生运行日志为`native-routed-audit.log`。首两次沙箱运行因无权使用用户TclStore分别失败在appinit/xsim初始化，原件保留`report-startup-environment-failure*.log`；受控普通账户执行同一只读DCP报告脚本成功。没有重装或重置用户TclStore。

## 软件与完整包

`release/output/soundsight_pynq_3d.zip`解压为独立`SoundSight_PYNQ_3D`，含匹配bit/HWH、三维程序和真实必要依赖，不含个人配置/录音/声纹模板。默认axes=off，运动仍需显式选轴和用户标定。B的原声纹目录未触及，共享设备锁仍防止两个采集所有者。

首次完整目录检查发现启动/排旧槽仍依赖旧求解库，因此`board_3d.offline`现在同时编译并装载两份本机库；不再借用旧程序目录的.so。旧build脚本仅把成功提示改成英文，求解算法与编译选项未改。软件增量包也补齐该C源码和构建脚本。

`tools/package_three_d_board.py`按明确文件列表打包，检查Python3.8语法、shell LF、硬件原件和ZIP字节；`board-package-test-*.txt`、`board-package-tests.json`记录从实际ZIP解压到干净临时接收目录后的本机检查、启动依赖自测、C数值检查及CLI帮助。数值原结果在`board-package-numeric.json`。这些是PC验证，不是ARM或板测。临时接收目录自动删除，未建立codex_out。

本次真实结果：完整ZIP 70项、880497字节；21项三维在线策略测试，及17/15/3/15/13/8/19项启动依赖回归，合计111项全部通过。C参考数值154例、PS能力位兼容155例以及几何/非法输入检查通过。两份动态库从空接收目录实际编译并加载；未借用旧程序目录。最终ZIP的bit/HWH与收件原件一致，所有打包源码与仓库逐字节相同。软件增量包同步更新为33项payload，不含bit/HWH。

复现：`python -B tools/package_three_d_board.py`，解压后执行`python -B software/tetra3d/linux/board_3d.py check`；另以实际可用编译器运行`python -B software/tetra3d/tests/test_solver_3d_migration.py --cc <gcc> --output <JSON>`。板端不需要输入这些长命令，使用SD说明里的短入口即可。测试过程命令、日志、原始数值与失败环境原件均保留，输出目录的临时TclStore/工具缓存已清理，仅保留复现驱动与日志。

## 下一步与限制

安装与短命令见`document/pynq-three-d-sd.md`。先确认40mm四面体实际CH0～CH3，ARM运行100帧、保持舵机关闭，再按实物标定水平/垂直零位、方向和限位；最后显式启用单轴/双轴跟随。声纹身份与三维实时融合、机械到位反馈、实板长期稳定均未被本次验证替代。

用户不必为本次补查重跑Vivado或生成位流。仓库已维护持久约束，下一次需要重建时由新版双轴更新配方带入；本次外部工程文件保持原状。
