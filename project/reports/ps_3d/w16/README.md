# W16用户实现收件

用户2026-10-29完成实现、位流、XSA和handoff导出。本次登记产品输入相对原10月28日仅 horizontal_reserved.xdc 的 PACKAGE_PIN W15→W16；其余登记RTL、BD、HWH一致。用户文件中的旧U7/Bank13注释不参与配置，仓库已纠正注释。真实placed I/O为T15/W16，均Bank34/LVCMOS33/DRIVE4/SLOW。

- `original/`：用户这次实现原报告。WNS +0.047ns、WHS +0.036ns、WPWS +2.208ns；setup/hold失败端点0。
- `supplemental/`：只打开同一次routed DCP、内存加入垂直20ns预算后的报告。垂直余量+11.935ns，水平+10.182ns，覆盖检查各项0；不保存DCP、不重综合/实现、不改位流、不访问硬件。原工程未登记此预算，后续重建应登记仓库 `project/sdc/ps/dual_axis_output_timing.xdc`，此次不需要为补查再次生成bit。
- 路由资源LUT18001/53200、FF19753、BRAM32/140、DSP41/220；CDC无Critical、1252条CDC-15 Warning，既有厂商IP DRC Warning保留。不能宣称完整CDC/RDC签核或W16板测已通过。
- `user-build-receipt.json`：原文件及XSA内bit/HWH对应关系；这些历史本机路径只用于来源记录。
- `original-export.zip`：用户通用脚本生成的原始project/BD Tcl与XCI、source_files.txt，保留历史绝对路径；不是解压即用工程，不作为仓库运行依赖。
- `project/bd/ps_3d_export.tcl`：从最新原件提取的完整BD/PS/IP配置函数，与原件Tcl调用事件对照；定义函数、不自动创建工程。现有增量入口仍是 `project/bd/update_ps_dual_axis.tcl`。未做新工程重建验证。
- `report-sandbox-failure.log`：首次沙箱TclStore/appinit初始化失败；受控普通账户同一只读脚本成功，见 `report-native.log`。没有重置或修改用户TclStore。

新SD包及板端复测见 `document/pynq-w16-update.md`。完整声纹包含私人模板，仅本地交付，GitHub同步公开源码/约束/说明/报告。包和源码维护不代表动作已经成功。
