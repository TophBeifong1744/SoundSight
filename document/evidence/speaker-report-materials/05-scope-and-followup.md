# 结论边界与后续记录

## 2026-10-29 仓库对齐后的当前状态

本节按仓库固定提交 `2f8bddc0e1da58ac52b077fbd36e01a15083fec9` 整理，替代下文历史段落中“当前/下一步”的时态，不改写原实验或失败。

- **唯一主方案为Zynq-7020 PL+PS/PYNQ，STM32路线已弃用。** STM32 S1/S2成绩和跨板失败保留为历史；不再作为当前待办或验收阻断。同一双核Linux运行Python/C业务，见[当前架构](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/document/main-architecture.md)。
- **A已全面接手总工程，包括声纹。** B的历史算法贡献保留；后续不默认交回B。当前正式源码已有SD包73份程序逐项对齐及缺失源码/依赖补入，91项验证属于Linux主机离线，非新增ARM实测，见[源码同步](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/document/evidence/sd-program-source-sync-20261029/README.md)。
- **垂直现行引脚为W16，水平T15；两轴手动可转已有用户观察回报。** 原W15的110°/115°无运动保留为历史失败。新的手动记录没有PWM波形或角度测量，不能当作全行程/标定/闭环验收，见[手动回报](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/project/reports/ps_3d/w16/board-manual-result.md)。
- **纯声音双轴跟随已经出现动作，但长稳发生整板重启。** 该次为`follow-sound --axes both`，未运行声纹推理；原因未确定，关轴持续对照只有准备结果、未收到持续时长/结论。不得归因于已证实的供电、看门狗或声纹负载，见[重启证据与边界](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/project/reports/ps_3d/w16/board-unexpected-reboot.md)。
- **A已收录B原资料ZIP。** 原件200文件、194份来源、189处内部链接的收件检查通过；不把原件里的194份历史引用复制到当前产品目录。见[收件说明](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/document/evidence/b-report-supplement-20261029/README.md)。

当前仍缺真实三维精度/标定、持续运行稳定性、声纹独立门限与身份方向关联、DAS实麦效果及最终比赛实物材料，见[当前验收范围](https://github.com/TophBeifong1744/SoundSight/blob/2f8bddc0e1da58ac52b077fbd36e01a15083fec9/document/requirements/acceptance.md)。PC/ARM离线/真实采集/人工动作观察继续分列；CP1/VF1历史数值通过而性能门限未达的结论保持。


## 截至v3资料可以支持的结论

已完成PCM传输分阶段验证、ARM模型执行与轻模型选择、部分INT8评估、短窗口实验、前端重复计算优化、有界进程调度和分阶段诊断。不能写成已完成多人混声识别、稳定实时本人跟随或整机验收。

原两人12段数据：本人登记3、本人开发3、另一人开发3、另一人旧测试3；本人独立留出为0。多轮复用及窗口重叠使数据成为开发对照，不能再当未见测试集计算推广准确率。分数一致只说明数值对照，不说明身份正确。

epoch26当时串口记录中“原件未取回”的说明保留为历史事实；之后input-audit和native-replay补充了原件核查与同窗复算。三窗低分在主机复现，FP32也出现相同状态，不能全部归因于量化或传输。见[E06](records/E06/native-replay.json)。

硬件估算与布线实测要分开；三条原Critical消除不等于所有Warning均关闭。网络内部profiling是CPU执行图观测，不能当PL周期或硬件加速收益。公开数据不包含私人音频、登记模板、连续高维特征或模型权重。

## 2026-10-28补记：B回传与联合软件接合

以下是更晚的独立批次，不能回填成v3已有结果，也不能与之前录音直接计算严格配对加速率。

- B回传full-profile＋P02 V1＋RX4：收件检查147项清单和75份Python语法。其epoch32报告938包、三次推理约2.951～3.044秒，仍超过当时2秒时效；全部过期。原版epoch33持续采集阶段约3.829秒，RX4约3.003秒的21.57%观察下降来自不同录音、各一轮，不能当严格基准。P02仍score-only、门限未标定；这些是B随包记录，不是本轮重新上板。见[E09回传进度摘录](records/E09/intake-excerpt.md)与[收件核查](records/E09/REVIEW.json)。
- 后续联合软件按用户新决策试验CP1/VF1异步评分和延迟许可：默认完成后3秒可调，下一轮推理可保留未过期许可；失败、静音、故障或STOP撤销，试验分数门限0.65可调、未配置不放行。它是新控制策略，不能称为旧2秒新鲜度要求已经满足，也不是已标定身份门限。
- 联合软件134项离线测试、真实模型主机数值对照和约6秒定速软件回放有记录；复核修正ARM/影子寄存器写期间许可过期仍可能COMMIT的问题。实际ARM并发、阵列通道/机械标定、本人/他人门限及联合闭环仍待板测。见[E10验证](records/E10/validation.json)、[数值对照](records/E10/native-models.json)、[独立复核](records/E10/independent-review.json)。

本报告目录仅记录这些进展和边界，不并入该批产品源码、部署包或硬件文件。B后续直接按[补充规则](CONTRIBUTING.md)追加真实证据。

## 2026-10-28 B补充后的历史结论与暂停点

本次补入E12～E19，覆盖RX4、MP1、FS1/CC1、CP1、VF1/CP2、目标开发对照及三维算法。来源与候选各自固定，既有E01～E11不改写。A的E10联合实现及其默认发布后3秒许可/0.65试验门限保持原记录；不能把B实验中的2秒源窗期限、A新许可保持和身份阈值标定视为同一验收。

当时声纹保存点：CP1+VF1已私下打包供A接入；ARM离线组合1.296293秒，比同轮原版快18.12%，比CP1再快2.01%。数值逐位一致不等于人物识别合格。用户授权开展接合不重写历史NO_ADOPTION；B侧尚无新组合真实采集并发回传。口头的“1秒采集+1.296秒≈2.3秒首结果”只是粗略估算，不进入metrics；采集/前端/推理是流水并行，不能简单累加各阶段总时长。

当时三维保存点：B的dfe9975提供独立求解/空间滤波/可选DAS/纯软件双轴接合模块，PC及合成验证完成。A现有main的三维采集、许可/动作提交和机械接口另行维护，不声称已合入B全部六项候选，也不把双方测试数相加成新的整机验收。

完整算法源码入口与贡献边界见[三维与B贡献索引](06-b-algorithms.md)。B本轮转入比赛资料，暂停新的声纹优化/板卡操作；既有私有模型、录音、模板和交接包原样保留。后续实麦需要确认实际运行提交、目标配置、时间关联、门限标定及定位并发；不从本资料自动触发动作。
