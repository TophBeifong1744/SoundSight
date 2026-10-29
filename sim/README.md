# 仿真与离线验证入口

| 内容 | 位置 |
|---|---|
| RTL testbench、输入及参考模型 | [simulation](../simulation) |
| XSim执行入口 | [simulation/script/run.bat](../simulation/script/run.bat)、[tools/run_sim.py](../tools/run_sim.py) |
| 软件PC测试 | [software/tests](../software/tests) |
| 比赛Skill测试与已有结果 | [Skills交付说明](../document/competition-skills-delivery.md) |
| 最新Vivado源包离线检查 | [test_vivado_portable.py](../software/tests/test_vivado_portable.py) |

从仓库根目录运行 `python -B -m unittest discover -s software/tests -p test_vivado_portable.py`，只检查PR #30的源包依赖与边界，不启动EDA或硬件。

XSim应按[运行说明](../document/run-guide.md)选择具体用例；`simulation/script`中的名称含`vsim.do`，实际使用XSim，不代表运行过ModelSim。历史仿真、PC回归、ARM离线、实麦采集分别保留环境和版本。没有因本次目录整理新增RTL仿真、综合或板测结果。
