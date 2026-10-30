# LAT1新位流收件与SD包

2026-10-30，用户完成综合、实现、位流及XSA导出，并用修正后的可搬移脚本导出handoff。

- 40份登记输入与实际源逐项一致；31 RTL及Hann数据与仓库产品逻辑一致。bd_ps_link安装版仅保留旧W15注释，实际约束/IO为W16，仓库正确注释未覆盖。
- ss_snapshot_queue与ss_ps_control_regs字节匹配本批测试源码，包含LAT1寄存器和READY淘汰规则。输入时间早于本轮实现报告。
- XSA内bit/HWH与工程输出字节相同；部署产物存于release/output/ps_3d_latest_result，receipt使用仓库相对路径。
- 实现WNS +0.176ns、WHS +0.029ns、WPWS +2.208ns；LUT18226、FF19753、BRAM32、DSP41。用户配置的约束内无失败端点。
- 仍有no_output_delay=1，4份已登记XDC未含仓库独立垂直输出预算文件；原候选补查不当作本候选证据。DRC/方法学警告保留，新CDC报告未导出。本次有限接收用于关轴联合复测，不是独立设计签核或全IO验收。

original保留用户真实报告；handoff.zip为实际导出的完整相对路径资料。user-build-receipt.json记录输入与产物，hardware-review.json限定核查范围。SD包测试完成后记录在sd-package-check.json及sd-package-tests.log。

本次没有运行Vivado构建、下载、复位或执行器操作，没有读取或清理板端私有资料。新候选板测待用户进行。
