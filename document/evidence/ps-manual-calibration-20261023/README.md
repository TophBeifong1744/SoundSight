# 无声音手动标定验证（2026-10-23）

## 本批结论与范围

手动角度改为独立PS命令，不依赖音量、有效方向或声帧；声音跟随继续经过原声音资格/滤波。T15水平、W15垂直保持，垂直LOW。750ms硬件看门狗、硬件和软件限位、停止排尾、故障/复位撤许可、互斥和旧位流拒绝已在下列范围验证。没有执行用户综合、实现、下载或机械动作，不宣称新候选资源/时序或机构到位。

代码：project/rtl/ss_manual_servo.sv、ss_ps_control_regs.sv；software/ps/manual_servo.py、board_tools.py、run_normal.py。新增PS 0x70～0x7c扩展，不改变冻结SPI/数值合同。PS源码清单、仿真清单、模块接口目录和现有完整更新配方已同步。

## 真实执行结果

| 检查 | 输入和预期 | 结果 |
|---|---|---|
| XSim manual | 真实AXI/寄存器/PWM，声音输入始终无有效帧；1MHz参数时基加速检查750ms保护、限位、模式互斥、STOP/故障/复位 | MANUAL_PASS，84694次检查；sources.zip保留实际输入 |
| XSim horizontal | 原声音路径，真实61.44MHz参数、500/1000/1500/2000/2500us脉宽、声帧资格及STOP | HORIZONTAL_PASS，1300368次检查 |
| XSim pslevel | 双槽、音量、复位保留、BIST | PSLEVEL_PASS ABI=00010001 slots=2 reset_retains=1 BIST=100000 |
| 软件包 | 从独立解压包运行13组182项PC离线测试，假寄存器/独立看门狗和多进程测试 | 12组首次通过；buffered组首次Windows文件访问失败，原代码24项限定复测通过，见下述失败事实 |
| Vivado配方 | 只读外部Volume工程输入复制到隔离fixture，执行完整horizontal更新，再执行manual更新 | Validate与Output Products通过；34条既有网、18个既有组件、AXI地址接口保留，7份RTL一致，T15/W15核对通过 |
| 收尾检查 | CLI帮助修正、旧音量更新入口补新依赖；6组定向复测、项目静态结构、包CRC/Python3.8语法 | final-checks中均返回0；最终包相对已测包只改两处CLI帮助字符串及两份文档 |

软件测试的182项是13组唯一用例总数，不把复测再累计为新增功能验证。模型测试不代表板端ARM运行或机械验证。BD审计从Volume输入到Servo会新增垂直LOW端口；本次manual增量本身不新增BD端口或改连线。

## 保留的失败与警告

- xsim/manual_20261023_222519：初次TB整数字面量延时溢出，0时刻timeout；把延时改为实数字面量后完成运行。原失败日志、TB和全部编译源码保留，没有把失败当作产品通过。
- software/test_buffered.py.log：原缓冲回归的spawn/slow-writer用例发生Windows AppData文件访问WinError5；没有改缓冲产品或测试，从同包改用仓库内临时目录复测24项通过，见test_buffered-r02.log/recheck.json。原checks.json仍保留失败返回码。
- bd/vivado.log/stdout.log保留工具告警：沙箱TclStore目录问题按安装目录回退；逐文件add_files性能告警；完整Volume->Servo更新时旧模块缺少新垂直端口告警，随后连接并最终Validate/audit通过。未重置用户全局TclStore，未修改实际用户工程。

## 复现命令

在仓库根目录、配置好的本机Python/Vivado环境中：

```text
python -B software/tests/test_manual_servo.py -v
python -B tools/run_sim.py manual
python -B tools/run_sim.py horizontal
python -B tools/run_sim.py pslevel
python -B tools/check_normal_update.py --archive release/output/soundsight_manual_update.zip --output <独立检查输出目录>
python -B tools/check_horizontal_bd.py --project <用户外部Volume工程.xpr> --output <独立检查输出目录>
python -B tools/check_project.py
```

实际原命令/本机路径见各日志和result.json。隔离BD检查会创建自己的测试工程，不打开用户工作工程。最终配方仅收尾补充volume入口依赖；manual增量主体与真实Vivado执行版本相同，原执行Tcl保留在bd/executed-recipes.zip。

## 交付与清理

操作文档：document/ps-manual-calibration.md。当前工程执行project/bd/update_ps_manual.tcl；输出MANUAL_PREPARED后用户自行综合、实现、导出新bit/HWH。软件增量release/output/soundsight_manual_update.zip不含bit/HWH；工程增量soundsight_horizontal_project_update.zip不含构建缓存。旧完整Servo SD包不冒充本次RTL。

保留xsim日志、结果和源码快照，bd前后设计/注册/约束/审计/脚本/日志，软件测试原始日志。清理本任务4个XSim运行目录及hz5supiji隔离Vivado工程，不清理他人工作或未归档成果；不新建codex_out目录。历史日志中的路径不篡改，原运行目录清理后的必要原件位于本证据目录。
