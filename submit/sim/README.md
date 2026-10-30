# 仿真与离线验证

本目录包含实际`rtl/tb`、`rtl/script`、`software`测试及`models`参考模型。在按[根README](../README.md)生成的工作目录运行原测试路径。

```text
python -B -m unittest discover -s software/tests -p test_vivado_portable.py
python -B -m unittest discover -s software/tests -p test_volume_gate.py
```

RTL仿真使用Vivado 2025.2 XSim，原入口为`simulation/script/run.bat batch <case>`。用例及实际历史结果见[运行说明](../report/run-guide.md)和[data/evidence](../data/evidence)。本批只验证提交包的脱离仓库复现，不重跑RTL/板测；软件测试不等于ARM实测。
