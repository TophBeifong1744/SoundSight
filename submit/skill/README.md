# 比赛技能包

本目录已放入两个技能包的实际脚本、示例、测试与许可证：`fpga-module-verification/`和`pynq-overlay-dma-validation/`，不是外部链接占位。各自的`skill.md`是小写提交入口；需安装到要求`SKILL.md`的助手时在使用者副本恢复该名称，或用本包准备脚本恢复原目录。

在生成工作目录中可运行：

```text
python -B release/check_competition_skills.py --skills-root research/competition-skills --output ../skill_check
```

省略`--vivado-bin`仅做离线测试；XSim标NOT_RUN。真实PYNQ Skill验收仍未完成。许可、历史失败与实际AI纠错见[交付说明](../report/competition-skills-delivery.md)、[AI协作记录](../report/competition-skills-ai-corrections.md)。
