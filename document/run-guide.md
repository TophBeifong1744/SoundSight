# 使用新工程

工具依赖仍是本机安装的Vivado2025.2、Python和PC测试所用GCC。工程文件不再读取旧仓库或旧F盘项目。

## 配置工具位置

- Vivado工程入口：`project/script/setting.bat`。
- XSim/PC测试配置：`simulation/script/setting.txt`。
- 默认使用本机现有`F:/AMD/2025.2/Vivado`、`C:/Python314/python.exe`、`F:/Program/env/mingw64`。
- 只改变子进程PATH，不修改系统PATH；可用环境变量覆盖。其他机器安装目录不同就改这两处配置。

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
& C:/Python314/python.exe -E -s -B -X utf8 software/tests/test_software.py
& C:/Python314/python.exe -E -s -B -X utf8 software/tests/test_application.py
& C:/Python314/python.exe -E -s -B -X utf8 tools/check_project.py
```

其他已有case：pair、preprocess、capture、clean、link、stm32、frontstop、queue、spi、actuator、clock、axi、ps。不同case覆盖范围不同，不需要每次小改都全跑。

双击仿真BAT默认打开link的XSim GUI，不自动声称通过；`batch`才执行`run all`并检查实际结束标记、Fatal/ERROR及退出状态。正式输出在simulation/work，软件输出在software/build。

PS实机程序位于software/ps，先在ARM Linux编译共享求解库，再使用实际HWH寻址。它不会加载bit或替用户下载硬件。STM32 S2与真实Keil外设工程尚未收到，见software/stm32/README.md。
