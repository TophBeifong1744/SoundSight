# 当前运行包验证 — 2026-11-03

- 实际完整私人ZIP166份载荷：CRC、原有私人资产绑定、真实文件安装、模拟重启回执、产品回执刷新、重复升级及个人设置/档案/日志保留通过。
- 22组主机测试共297次执行全部通过，C库由包内源新编译；不是297个实板测试，也未进行ARM模型推理。
- 首次发现录入测试的调度器替身仍返回None，新程序需要其info字段。保留初次失败日志，修正测试替身后18项录入测试及完整297次检查通过；未改生产调度逻辑掩盖错误。
- 新旧包中的C数值核心、模型及S2bit/HWH保持已有匹配关系。当前公共P1包包含33项载荷，完整包包含其全部文件并刷新同一回执。
- 诊断输出中的本机临时路径改为标签，错误、测试名和结果保留；原始运行证据在final-board-20261103等目录。
- 没有执行Vivado、下载、复位、接线或舵机动作。独立submit的最终验证由同一发布中的submit-validation.json记录。

命令：

```sh
python -B tools/check_current_runtime_package.py --package release/output/soundsight_pynq_3d_speaker.zip --output simulation/work/runtime-check --cc gcc
python -B tools/check_submit.py --submit submit --work-parent TEMP_DIRECTORY --result submit-check.json
```

第一条用于完整Git维护仓库及私有包；第二条验证公开实体提交。Windows临时目录应使S2输出路径小于78字节。

实际公共P1包从已安装快速启动版升级、重复安装、保留私有设置/档案/bit、拒绝未知源码修改均通过。首次基线清单漏收已知CRLF版本，已从准确旧包校验并补入两种换行；未放宽未知版本保护。记录见public-update-validation.json。
