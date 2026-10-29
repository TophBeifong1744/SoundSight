# B交回总工程：AF1与垂直不动

收件日2026-10-29。原ZIP完整性通过，7个外层文件完整读取并保存在received；内层AF1 ZIP完整性及3项payload校验通过。没有执行附件安装器或任何硬件命令。原文件字节保持不变；串口原件中离线测试打印的模拟DEVICE_STATE不能当作实际设备状态。

用户本轮明确：A全面接手；保留显式选择的纯声源follow-sound。根据这一授权接回AF1三项文件。board_3d替换前与AF1要求的基线一致；收件manifest对比是在接入后记录，所以该文件matches_B_base=false属于预期。run_capture.py与B旧基线不同，因为昨日已增加旧二维自动入口拒绝双轴的保护；该修复保留，没有用旧包覆盖。

本次实际运行：follow-sound7、online3d21、normal17、manual8、horizontal28、board15，共96项PC离线测试全部通过，日志及命令见tests.json。无RTL/BD/STA/实板动作；不将B板端离线测试说成现场机械验收。

关键板端事实：manual垂直110和115各30次提交被控制器接受、正常撤销，用户观察均不动；无W15/舵机端波形。source-as-delivered/motion_3d.py与本地逐字节一致。垂直试探限位不作为实测标定。P02导入/CP1VF1校验成功不能替代身份识别效果测试。

后续负责人、各模式及排查入口见[接管说明](../../total-handoff-20261029.md)。本轮仅原件和必要代码归档，没有创建临时工程；不自动公开附件或私人资产。
