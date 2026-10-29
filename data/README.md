# 测试数据与参考结果入口

| 数据类别 | 位置 | 使用边界 |
|---|---|---|
| 仿真夹具 | [fixtures](fixtures)、[simulation](../simulation) | 合成输入与参考结果，不作为真实声学精度 |
| 实验原件 | [document/evidence](../document/evidence) | 按日期、候选、环境查阅，保留首错和失败 |
| B可绘图指标 | [metrics.csv](../document/evidence/speaker-report-materials/metrics.csv) | 同条件比较；PC、ARM离线和实测不混合 |
| B来源与候选 | [source-map.json](../document/evidence/speaker-report-materials/source-map.json) | 历史来源身份保持，不把候选自动当成当前采用 |
| 当前W16实现和板端回报 | [project/reports/ps_3d/w16](../project/reports/ps_3d/w16) | 时序、手动观察与长稳失败各自限定范围 |

录音、个人模板、特征向量和模型权重不因资料整理公开。缺失数据保持缺失，不补造参考结果。此次没有新增实验、E编号或指标行。
