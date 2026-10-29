# 上板、运行与现场证据入口

当前为Zynq-7020 PL+PS/PYNQ，水平T15、垂直W16。操作说明与真实记录分开：

| 内容 | 入口 | 当前边界 |
|---|---|---|
| 板卡、电气、麦克风资料与既有照片 | [hardware](../hardware) | 原件保留来源；不能代替最新整机照片 |
| 三维SD安装 | [三维SD说明](../document/pynq-three-d-sd.md)、[W16更新](../document/pynq-w16-update.md) | 需要匹配候选和实际板端环境 |
| 两种跟随模式 | [声纹与纯声音模式](../document/pynq-speaker-3d.md) | `follow-sound`不要求身份；`speaker/run --axes`要求许可；默认不开轴 |
| 单段录入与本人关轴评分 | [板测回报](../document/evidence/speaker-enrollment-20261029/board-result.md) | 5秒录入成功；两个可用分数0.6103/0.5563；阈值未配置，不是识别验收 |
| 双轴手动 | [现场回报](../project/reports/ps_3d/w16/board-manual-result.md) | 用户观察可转；无角度/全行程标定结论 |
| 纯声音长稳失败 | [整板重启](../project/reports/ps_3d/w16/board-unexpected-reboot.md) | 根因未定；不是声纹推理测试 |
| B历史板测与算法证据 | [B贡献总览](../document/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md) | PC、ARM离线、真实采集及人工观察分别引用 |

最新状态以[当前状态](../document/current-status.md)和[验收范围](../document/requirements/acceptance.md)为准。本次资料整理没有加载位流、复位、运行板端程序或移动舵机。
