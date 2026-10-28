# 旧解释器覆盖自动回退修复

2026-10-22用户现场回传：

```text
BACKUP= /home/xilinx/SoundSight_PYNQ_Volume/backup_normal_s0go_3ls
NORMAL_UPDATE_INSTALLED FILES= 25 HARDWARE_ACTIONS=0
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'pynq'
PYTHON_PROBE_FAILED=python3.8
STOP: PYNQ_PYTHON failed validation; correct or unset the override. No board helper started.
```

因此本次可确定：旧PYNQ_PYTHON覆盖指定了python3.8，探测不能导入PYNQ；不是bit加载失败。上一轮“环境覆盖失败即停止”的设计要求用户手工清理，与此次简化日常短命令的目标不符。

## 修改

- 有效PYNQ_PYTHON仍优先；无效时打印IGNORING_STALE_PYNQ_PYTHON并自动回退到板端venv、PATH中的python3。
- 每个硬件入口候选仍实际导入PYNQ；所有候选失败时不启动board_tools。只在本进程清理/更新环境，子进程继承已验证选择；不修改系统或用户登录配置。
- prepare/run/status/drain短命令、门限设置、bit/HWH、求解与STOP行为不改；帮助/门限文件操作不需要PYNQ。
- 同名SD增量包及说明更新，安装时仍备份源码、保留本地门限与历史日志，不加入硬件产物。

## 验证

真实POSIX shell与Python运行12项启动测试：用故意无法导入PYNQ的python3.8模拟现场旧环境，对prepare、run normal、run debug、status、drain逐项验证自动回退且子进程不再继承旧值；另覆盖缺失路径、默认venv失败后回退系统Python、所有候选失败拒绝、有效自定义路径、空格路径、参数传递、环境清理及LF。板端路径与PYNQ模块使用测试替身，不执行MMIO或下载。

交付包解压、安装到隔离目录后运行10组133项离线测试，结果见checks.json和test_*.log。检查25份payload与源码一致、ZIP CRC、Python3.8语法，以及安装未改bit/HWH/C库/历史日志。命令为`python -B tools/check_normal_update.py`，Windows通过SOUNDSIGHT_TEST_SH指定本机Git Bash；Linux自动查找sh。

新短入口未由本次代理在板端执行，实板待用户确认。旧缓冲测试的间歇失败原件保留在前次证据目录，本轮通过不代表历史根因闭合。没有运行Vivado、下载、复位或执行器动作；测试临时目录已由测试工具清理，无新增codex_out内容。
