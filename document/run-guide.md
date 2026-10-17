# 使用新工程

工具依赖仍是本机安装的Vivado2025.2、Python和PC测试所用GCC。工程文件不再读取旧仓库或旧F盘项目。

## 当前手工开发方式

用户先在仓库外创建并编辑Vivado工程，按[手工搭建步骤](manual-stm32-build.md)添加复制后的源码和IP。阶段验证后导出最新配置并接回仓库。空目录重建仅是这次的测试安排，不是以后每次交接的固定要求。下方BAT用于仓库配方重建，其目标仍为仓库内par；不要用它创建本次外部手工工程。无参数运行BAT会尝试prepare stm32，不会自动接管你的外部工程。

## 配置工具位置

需要 Vivado 2025.2、Python 3；PC C 测试还需要 MinGW-w64 GCC。公共脚本不绑定个人安装盘符。

1. 若工具已在 `PATH` 中，可直接运行。否则复制根目录的 `tools.local.env.example` 为 `tools.local.env`，填写本机安装位置。
2. `VIVADO_ROOT` 填包含 `bin` 的 Vivado 安装目录，`PYTHON_EXE` 填 Python 可执行文件完整路径，`GCC_ROOT` 填含 `bin/gcc.exe` 的目录；也可用 `SS_GCC` 直接指定 GCC。
3. 格式为 `KEY=value`，路径可以包含空格，不加引号、不写 shell 命令或变量表达式。只填写需要的项。优先级是环境变量、本地配置、PATH；显式配置无效会报错，不悄悄换另一套工具。
4. `tools.local.env` 已被 Git 忽略，只保存在本机；换电脑或重新克隆时重新配置。不要提交它，也不要将个人路径写回公共脚本。当前电脑已迁入原工具路径，无需再填一次。

只核对位置，不打开 Vivado、不运行仿真：

```powershell
.\project\script\run.bat --check-tools
.\simulation\script\run.bat --check-tools
```

`tools/python.bat` 用同一配置启动 Python，供下面的 PC 检查使用；不必在系统 PATH 中再装一份 Python。脚本仅调整子进程环境，不修改系统 PATH。

以下命令从SoundSight根目录执行；BAT自身也能从其他当前目录调用。

```powershell
# 首次生成独立项目：没有已有工程才执行。
.\project\script\run.bat prepare stm32
.\project\script\run.bat prepare ps

# 已存在时打开；不要重复prepare。
.\project\script\run.bat open stm32
.\project\script\run.bat open ps

# 生成官方IP/BD输出，不启动综合/实现。
.\project\script\run.bat outputs stm32
.\project\script\run.bat outputs ps
```

原生入口分别是`project/par/SoundSight.xpr`和`variants/pl_ps/project/par/SoundSight_PS.xpr`。两版共用`project/rtl`，不把一版复制到另一版后各自修改。

在已打开Vivado的Tcl Console，也可source `project/script/vivado.tcl`后调用`ss_project::prepare stm32|ps`、`ss_project::outputs`。准备前必须关闭当前工程，脚本不会接管用户已打开的其他项目。

## 用户手动配置与构建

1. 阅读BD，按真实板卡设置PS7 DDR/MIO/参考时钟和PYNQ启动配置；保留FCLK0=100MHz、RESET0与RESET1的用途。
2. Validate Design并生成输出后，由用户点击Run Synthesis，再按报告决定是否Run Implementation。
3. 完成run后source `tools/export_reports.tcl`，调用`ss_reports::save synth`或`ss_reports::save impl`。
4. 报告写入该项目par内的reports；导出命令不会启动下一阶段。

用户手工更改的BD/PS配置需要通过Vivado正式导出配方/配置，再纳入Git；本地ignored数据库不是永久版本备份。

## 仿真和软件检查

```powershell
.\simulation\script\run.bat batch samplecdc
.\simulation\script\run.bat batch cdc
.\simulation\script\run.bat batch platform
.\simulation\script\run.bat batch dual
.\simulation\script\run.bat batch pscdc
.\simulation\script\run.bat batch pdm
.\tools\python.bat software/tests/test_software.py
.\tools\python.bat software/tests/test_application.py
.\tools\python.bat tools/check_project.py
```

其他已有case：pair、preprocess、capture、clean、link、stm32、frontstop、queue、spi、actuator、clock、axi、ps。不同case覆盖范围不同，不需要每次小改都全跑。

双击仿真BAT默认打开link的XSim GUI，不自动声称通过；`batch`才执行`run all`并检查实际结束标记、Fatal/ERROR及退出状态。正式输出在simulation/work，软件输出在software/build。

PS实机程序位于software/ps，先在ARM Linux编译共享求解库，再使用实际HWH寻址。它不会加载bit或替用户下载硬件。STM32 S2与真实Keil外设工程尚未收到，见software/stm32/README.md。
