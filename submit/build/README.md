# 构建配方与报告

`vivado/`内为实际BD、PS/IP Tcl、XDC和工程脚本，`tools/`为Python/Tcl助手，`reports/`内为已有实现报告。完整PR #30配方和31个RTL在本包中，不需回到原仓库取文件。

先在submit根运行`python -B build/prepare_workspace.py --output ../soundsight_work`，然后按[根README](../README.md)在生成目录启动工程配方。`prepare_workspace.py`只复制本包文件，不执行EDA/硬件。原配方的详细说明见[复现说明](../report/vivado-ps-3d-rebuild.md)。

提交目录用小写路径；准备脚本按`file-map.json`恢复工具所需的原名。报告的结果只适用于其记录的候选，不能代替新工程STA。
