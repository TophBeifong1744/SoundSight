# Hardware

2026-09-17覆盖：旧机械路线停止采用，现按C舵机与摄像头路线落实，见[路线决定](servo-camera-decision.md)、[C操作单](../document/member-c-operation-sheet.md)。C负责方案、全部相关驱动及最终效果测试；下文旧“不追加任务”不适用于本项新授权，PWM模块PASS不等于实物或摄像头通过。

2026-09-23：按 [fpga-team-workflow 协作约定](../document/team-workflow.md)执行，V1 总验收改为 **2026-10-07**；任务及状态以 GitHub Issue/PR 为准，见[日历](../document/project-plan.md)与[任务入口](../document/work-packages.md)。A/B/C 均可承担工程开发和独立复核；旧聊天已删除。本文技术合同保留，历史证据不自动批准后续版本。

本目录保存真实硬件证据：板卡型号与原理图引用、麦克风/ADC 数据手册、阵列机械尺寸、时钟树、电源与 IO 电平、连接图、BOM、XDC 引脚映射和标定记录。

硬件结论必须能追溯到实际板卡版本或测量结果。不得仅凭通用 Zynq-7020 能力假设某个引脚、电压、音频 Codec 或扩展口可用。

当前入口：

- [当前项目状态](../document/current-status.md)、[项目计划](../document/project-plan.md)、[任务包](../document/work-packages.md)
- [四路同步麦克风采集方案与接口核验](microphone-interface-selection.md)
- [麦克风评审及用户模块照片文字证据](microphone-recommendation-review.md)
- [C 提交的麦克风实物资料与 A 复核记录](evidence/microphone-c-2026-09-09/README.md)（资料归档通过，接线未验收）
- [已选 C 转接板：接口基线与工程适配](microphone-adapter-decision.md)（2026-09-11用户决定采用；非阻塞风险集中在[暂缓清单](../document/deferred-acquisition-risks.md#c-adapter-risks)，不沿用旧单CLOCK绘板草案）
- [现行V1硬件采购指标](procurement-specifications.md)
- [M0板卡与接口审计](m0-board-interface-audit.md)、[竞赛验收台账](../document/competition-acceptance.md)
- [六麦阵列与夹具指南](three-dimensional-array-guide.md)
- [六麦声学软件报告](../document/six-mic-acoustic-software-review.md)、[独立评审材料包](../deliverables/six-mic-acoustic-review-v1/README.md)
- [Zynq 与领航者板级参考资料索引](reference/README.md)

## 当前路线和证据状态

沿用用户已选的IM73D122V01／PDM，不重新比较或更换麦克风、接口；INMP441只作历史备用讨论。选定路线不等于模块身份、供电电平、尺寸声孔、接线或板测已通过。

V1仍为四麦二维、目标2026-10-07；其采集合同、采购指标和验收要求是现行文档，不因V2六麦预研而废弃。V2当前只做六麦软件预研，不新增四麦模拟、四/六麦对照或六路抽四路任务。V1的4用1备不是5通道，V2未准入不加购。

六麦报告已有2700帧、21项自检通过及独立复跑一致；真正带内0 dB场景有效率47%、等强竞争声源26%，完整3D-G0未通过，更不是硬件通过。尚须人工评审失败场景与资源预算，并取得实际模块、遮挡、PDM同步/抽取、标定、长录音及实板证据。软件结果的A/B/C是同组六路数据的单麦参考/手动真实指向/自动指向，不是四麦方案测试。

## 现行文件与归档边界

整理前文档的逐字节备份由主流程集中保存在`archive/2026-09-07-before-materials-cleanup/`，本目录入口只指向现行文件；备份不是新的有效状态，也不重复备份。日期命名的原始照片证据仍保留其真实日期，不因链接迁移改写为当前硬件通过。主计划、审计迁移、材料包及归档由主流程维护，本轮硬件任务不改它们。
