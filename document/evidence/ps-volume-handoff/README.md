# PS Volume 最新导出接回

输入：用户2026-10-21提供的`F:/AMD/work/SoundSight_PS_Volume/handoff/latest`。原始23项文件完整保存在original-export.zip，含工程/BD Tcl、源清单、两份独立FFT XCI和BD内部IP XCI。原始路径仅作历史证据，正式复现不依赖它们。

处理：从实际BD提取完整建图过程，统一工程BD名为soundsight_ps_bd；PS7参数拆到project/ip/ps7_ps.tcl，其他单元/连线原样接回project/bd/ps.tcl。按实际导出接回77项综合/实现选项和Global输出模式。实际登记的两份XDC接回原project/sdc/ps。禁用的旧ILA XDC不纳入正式依赖。没有复制第二套RTL或IP输出数据库。

核查命令：

```text
python -B -X utf8 tools/check_ps_handoff.py --hardware-project F:/AMD/work/SoundSight_PS_Volume
python -B -X utf8 tools/check_project.py
python -B -X utf8 tools/package_ps_handoff.py
```

结果：80项Tcl配置/连线事件与原导出完全一致；54项显式FFT参数与XCI一致；77项运行设置与原工程一致；26项RTL/初始化数据及2份XDC忽略换行/尾空白后与实际工程相同；41项依赖均存在且无发送方工作路径。结果原文为static-result.json、project-check.json。Tcl比较使用真实解释器和命令记录，不是Vivado执行；本次未重建原生工程或重复综合。

用户本次已实现产物、bit/HWH/XSA匹配及音量仿真/软件测试原文沿用相邻ps-volume-gate证据。真正的实现报告放project/reports/ps，方便在工程旁查看。包内41项依赖使用项目相对路径；SD包和电脑复现包均进入release/output的固定入口并发布。

原始默认参数、部件号和时序报告只能支持同候选范围，不证明新音量实板或机械闭环。尚未合并的C PR #18未纳入本批。
