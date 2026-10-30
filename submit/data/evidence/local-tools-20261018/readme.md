# 本机工具配置迁移验证（2026-10-18）

公共入口改用环境变量 > tools.local.env > PATH；本机配置被Git忽略，仓库只维护空模板。Vivado、XSim、PC GCC共用工具发现模块；Python BAT入口共用引导脚本。不修改RTL、协议或工具安装。

## 实际运行

- `project/script/run.bat --check-tools`：成功定位本机Python和Vivado；eda_started=false。
- `simulation/script/run.bat --check-tools`：成功定位本机Python和四个XSim工具；eda_started=false。两入口从仓库外目录调用也成功。
- `tools/python.bat software/tests/test_tool_config.py`：7项通过，包含环境覆盖、GCC别名优先级、PATH回退、带空格路径、缺件/无效显式路径，以及没有本地文件的隔离BAT入口。测试使用假Vivado文件，不启动EDA。
- `tools/python.bat software/tests/test_software.py`：实际本机GCC编译运行，S1 4705项、桥接/客户9项通过。AXI输入复用既有真实仿真输出，本次没有重跑RTL仿真。结果保留为software-result.json、s1.log。
- `tools/python.bat software/tests/test_application.py`：8项通过，结果保留为application-result.json。
- `tools/python.bat tools/check_project.py` 与 `git diff --check`：通过。
- `git check-ignore tools.local.env`：命中；提交清单没有该文件。
- 当前脚本和使用说明已移除个人工具默认路径；历史证据原路径保留。Word重新渲染41页：前40页与上一轮已逐页检查的基线像素一致，修改的第41页单独视觉检查通过。

## 测试过程中修正的误报

初版测试将Windows临时目录短名与工具返回的长名直接比较，3项误报；统一resolve后通过。新增BAT测试复制环境为普通字典后错误地按SystemRoot混合大小写取值，发生KeyError；统一环境键大写后7项全部通过。均为测试自身问题，没有更改工具发现优先级。

Word继续使用指定Windows渲染器；沿用任务内输出解码适配，避免Poppler本地化信息被错误按UTF-8解码。未改全局渲染工具。可再生成的预览和本任务助手已清理。

未启动Vivado、RTL仿真、综合、实现或板上操作；工具可发现和PC测试通过不代表新硬件构建通过。
