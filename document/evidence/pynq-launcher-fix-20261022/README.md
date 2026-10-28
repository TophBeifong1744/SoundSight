# PYNQ短入口解释器修正 — 2026-10-22

本页保留首版修正的真实记录。后续现场定位了旧PYNQ_PYTHON覆盖，最新自动回退修复见[stale-override](stale-override/README.md)，下述“显式覆盖错误则停止”已被新行为替代。

## 现场事实与边界

用户回传安装加准备的末段输出：

```text
Ran 15 tests in 0.163s
OK
ARM_LIBRARY_LOADED=1
STOP: No module named 'pynq'
HELP: see document/pynq-board-helper.md; preserve logs on unexpected faults.
```

随后用户直接指定`/usr/local/share/pynq-venv/bin/python3`执行同一`board_tools.py prepare`，回报“这次成功了”。原短入口没有打印实际解释器与环境，无法确定是覆盖变量、自动回退还是其他现场环境问题；不能把某一种推测当作已证实根因。导入失败发生在load_api的PYNQ导入处，尚未构造Overlay或进行下载。

本次修复的是可确认的入口缺陷：原来只按路径是否可执行选Python，没有验证PYNQ。现在硬件入口实际导入Overlay/MMIO/Clocks后才执行helper，成功打印Python路径与导入标记；清理当前进程PYTHONHOME/PYTHONPATH，默认先PYNQ venv再PATH候选，显式覆盖错误则停止。帮助/门限文件操作仍不需要PYNQ。无可用环境时不会启动helper。不改采集/求解/门限/STOP/运行超时/位流。

## 已执行验证

真实POSIX shell（本机Git Bash）运行启动脚本，真实Python导入临时PYNQ测试替身。仅把本机不存在的板端默认路径替换为临时路径，helper替身只记录参数/环境，模拟PYNQ类禁止实例化；不加载板子。9项覆盖：默认环境优先、缺失回退、可执行但PYNQ导入失败、所有环境失败、含空格的显式路径、错误覆盖拒绝、Python环境污染清理/XRT默认、无PYNQ时帮助与门限、LF行尾。

首次夹具执行中，Windows路径直接加入POSIX PATH导致回退项找不到，以及Git Bash把`/usr`转换为Windows路径，3项失败。只调整测试夹具的cygpath处理和MSYS环境转换设置后9项通过；没有按这些Windows特性改板端产品逻辑。

交付ZIP解压到临时目录，执行安装器核心，验证25份payload逐字节一致、bit/HWH/C库/历史日志保留、Python3.8语法、ZIP CRC，再执行10组共130项测试，全部通过。真实输出见同目录`checks.json`及`test_*.log`。旧缓冲测试的间歇失败仍保留在`../pynq-board-helper-20261022`，本轮通过不表示该历史问题已定位。

复现命令（Windows先把SOUNDSIGHT_TEST_SH设为本机POSIX shell路径；Linux测试自动找sh）：

```text
python -B software/tests/test_launcher.py -v
python -B tools/check_normal_update.py
```

SD包：`release/output/soundsight_normal_update.zip`。CRC和复制验证使用的是最终包；软件说明随包更新。没有执行Vivado、板端下载、复位或舵机动作。新短入口板测待用户执行；已知长命令的成功不能替代短入口板测。临时测试目录自动删除，没有新增codex_out内容。
