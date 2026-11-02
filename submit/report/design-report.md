# 当前系统与可报告结果

Zynq PL完成四麦采集、时差特征、连续PCM、双轴PWM和停止保护；PS运行CF1A四面体定位、
CP1/VF1声纹评分与score_ttl_v2许可，S3面板通过S2的RGB/VDMA和PS I2C0 EMIO显示与触摸。
纯声音跟随与声纹跟随是两个独立模式，默认关轴。当前三维不估计距离。

A及原作者提供PL/PS和许可基线，B侧后续负责算法迁移、声纹计算优化、J3/S2/S3及CF1/CF1A实现与验证；
用户及现场成员执行真实上板操作。CAM++、Silero、ONNX Runtime和厂商IP归各第三方。

| 证据 | 结果及适用范围 |
|---|---|
| S2既有实现 | WNS +0.203ns、WHS +0.036ns；CDC与外部I/O约束仍有缺项，非完整物理签核 |
| S2实板 | 两轮设置60秒的显示/触摸及正常退出；非联合长稳 |
| P02串行测试 | 本人授予许可，过期后另一人15个有效分数0.0372–0.2200未重授权；非总体识别率 |
| 声纹优化 | RX4校验CPU下降95.71%；CP1+VF1同轮离线并发下降18.12%；不同计时边界不可相加 |
| CF1A PC | 4598完整窗/3833稀疏窗分类与有效向量一致，前端wall中位下降45.5%；非ARM端到端延迟 |
| CF1A板测 | 摘要30.016秒，36组方向、22次动作、3次快照缺口、正常停止；现场另有几分钟观察，不能混成定量长稳 |

来源：[声纹原始指标](../data/evidence/speaker-report-materials/metrics.csv)、
[CF1A板测](../data/evidence/cf1a-longrun-20261102/readme.md)、
[CF1A离线验证](../data/evidence/cf1a-20261102/verification/report.md)、
[S2实板](../data/evidence/screen-s2-20261031/board-result.md)。
没有精确测角，不生成随机误差或宣称最大误差≤5°。失败与缺口保留在相应证据中。
