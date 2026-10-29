# B 比赛报告补充材料收件

2026-10-29：本包应加入比赛报告资料，**不作为 SD 卡程序更新安装**。包内是设计说明、贡献梳理、已有实验结果和历史源码引用；没有新的运行固件、模型或板端安装程序。

原件：[soundsight_B_report_for_A_20261029.zip](soundsight_B_report_for_A_20261029.zip)。完整解压后从 `SoundSight_B_Report_For_A/START-HERE.md` 开始，重点阅读 `materials/07-b-contribution-and-gaps-20261029.md`。保留原 ZIP 是为了保持历史源码与报告的相对链接，不再将其中 194 份引用材料复制到当前产品目录。

已有公开材料入口：[声纹及 B 算法报告索引](../speaker-report-materials/README.md)。新稿可用于成员分工、STM32/PYNQ 迁移、三维/DAS、声纹 CP1/VF1、失败分析及后续计划。性能数字仍按 PC、ARM 离线、实麦各自口径引用，不叠加百分比，不把有效率当定位精度。

## 阅读时应带上的最新事实

- B 原文中垂直轴 W15 无运动是历史失败事实。之后用户已将约束改成 **W16**，重新生成并加载位流，确认水平 T15 与垂直 W16 均能手动转动。见[手动结果](../../../project/reports/ps_3d/w16/board-manual-result.md)。原文不覆盖或倒改。
- 用户后来观察到双轴纯声音跟随开始时可转动，但长稳期间整板意外重启。**长稳未通过，原因未确定**；正在做 `--axes off` 对照。见[重启记录](../../../project/reports/ps_3d/w16/board-unexpected-reboot.md)。
- A 已全面接手总工程；本批另将最新 SD 包中缺失的声纹程序同步到正式源码，见[程序同步](../sd-program-source-sync-20261029/README.md)。这里的 `references/` 仍是历史引用，不能覆盖当前源码。
- 三维实际精度、身份与方向关联、DAS 实麦效果、长稳和机械闭环验收仍不能由此报告补齐。照片、视频、签署文件和 AI 原始对话选编仍需真实材料。

## 本次检查

[intake.json](intake.json) 记录原件校验：ZIP CRC 通过，194 份源清单的长度及内容校验通过，189 处内部 Markdown 链接无断链。未发现录音、模型、位流或共享库二进制。此次没有执行包内历史命令，没有新增算法或板测结果。
