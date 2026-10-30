# 双轴 FPGA 实现与作者自测

后续用户已完成实际3D工程位流，原布线补查与完整SD包交付见[本次收件](board-receipt.md)。下文保留写代码时的自测原貌，其NOT_RUN不代表最新物理构建状态。

后续PS在线接合、99项软件回归、实际ZIP隔离安装、非作者复核与问题闭合见[软件与复核记录](software-review.md)。以下保留FPGA作者原始自测范围，不将其改写成板级通过。

用户随后明确以做声纹时的`SoundSight_PS_Reliaze`为基线。`reliaze-base.json`记录本机实际XPR/BD/HWH与登记源的只读核对：39项文件存在；三份PS层有本批功能差异，其余公共RTL文本一致（两份仅字节换行差异）；PCM、DMA→HP0和修复后的控制连接完整。旧禁用SPI ILA约束的外部路径已识别，当前Tcl复制约束且保留IS_ENABLED。只改操作说明，不改RTL或Tcl行为，因此复用上述测试，不把本轮静态核对称作真实Vivado Validate。软件增量ZIP只因内含说明更新而重打包。

2026-10-28。按主协调确认的[PS双轴扩展v1](../../../report/ps-dual-axis-interface.md)实现，用户已确认水平T15/360°、垂直W15/220°，两路20ms、500～2500μs。仅PL+PS扩展；声纹、PCM数据、原快照和STM32合同不改。

本记录是作者自测，非独立验收。综合、实现、实际BD Validate、输出生成、下载和机械动作均 **NOT RUN**。现有位流不因此获得新能力。

## 范围与源码

- 新 `project/rtl/ss_dual_axis_control.sv`：影子配置原子应用，模式/轴mask/两角原子提交，真实锁帧关联和防重放，两轴共享750ms租约；复用原PWM发生器与收尾保护。
- `ss_ps_control_regs.sv`、`ss_ps_link.sv`、`bd_ps_link.v`：接入PS专用0xA0～0xD0扩展与垂直输出；默认`DUAL_AXIS_ENABLE=0`，原二维路径保留。关闭分支不实例化新模块，因此旧更新脚本无新增源码依赖。
- `project/bd/update_ps_dual_axis.tcl`：只处理用户事先建立的仓库外3D/DualAxis副本；备份现有源和BD，复制受影响RTL及其余当前手写源、约束到该副本，保留IP与用户现有内容；检查T15/W15，刷新模块参数，启用双轴，Validate与输出生成。无创建副本、综合、实现、下载入口。
- 两份正式源清单补入新模块；新增 `tb_dualaxis.sv` 与 `test_dual_axis_tcl.py`。已有PS TB仅补新增输出空接和已发布手动能力位的旧预期。

`review-snapshot.json`冻结本次只读复核文件内容；它仅用于管理证据，不插入RTL或运行门槛。工作区原先还有其他未归档/未提交成果，本批未清理、覆盖或提交它们。

## 行为、时钟与接口

新双轴同在61.44MHz控制域，无新增CDC、异步输入、时钟IP或复位IP。普通总线复位撤许可、清配置而保留快照和最后跟随序号；冷复位立即低。新命令进入原20ms周期边界；首次开启沿用原PWM guard等待完整边界规则，可等待约两个周期，不输出旧复位角度。采集/求解数值与吞吐路径未改。

旧0x00～0x94和STATUS布局保留，能力改用独立A0；原IRQ汇总故障。无新增DMA。非法双轴命令/配置沿用FAULT bit7，寄存器错误bit1，租约到期bit8。旧SYS停采集、ACT的0/STOP/REVOKE、故障及PS总线复位同时覆盖双轴撤销。

## 真实执行

Vivado/XSim 2025.2，SW Build6299465；仅隔离仿真输出写入`simulation/work`。下面命令从仓库根执行，Python工具路径按本机配置解析。

```text
python -B tools/run_sim.py dualaxis
python -B tools/run_sim.py manual
python -B tools/run_sim.py horizontal
python -B tools/run_sim.py audiometa
python -B tools/run_sim.py pslevel
python -B tools/run_sim.py ps
python -B tools/run_sim.py pscdc
python -B software/tests/test_dual_axis_tcl.py -v
```

| 检查 | 结果及边界 |
|---|---|
| dualaxis | PASS，319254断言；实际BD包装/AXI寄存器/双槽/双PWM路径，1MHz参数加速计数但保持20ms和750ms实际时间。静默启动、无声手动、真实≥4对跟随、单轴mask、原子配置/目标、范围拒绝、重复/变更/高32位序号、普通复位保帧防重放、两轴不同高脉宽完整撤销、旧安全退出、STOP/故障与COMMIT冲突均覆盖。独立端口小实例只补同拍STOP和最高位序号边界；主要用例走实际AXI。 |
| manual | PASS，84694断言；原无声水平标定、限位、租约、采集互斥。编译刻意不含新双轴模块，证明旧关闭分支无新依赖。 |
| horizontal | PASS，1300368断言；实际61.44MHz配置，500/1000/1500/2000/2500μs脉宽、STOP完整脉冲、保帧复位、超时，垂直保持低。 |
| audiometa / pslevel | PASS；双槽保留、总线复位、原BIST/音量/PCM元数据合同。 |
| ps / pscdc | PASS，各852断言；双BIST、双槽保留、格式错误、冷复位。pscdc使用官方100→61.44MHz AXI Clock Converter仿真模型。 |
| Tcl离线 | 5项PASS；临时模型实际执行文件复制、登记、重复运行和带空格路径，拒绝原工程、错误器件、活动运行及引脚冲突。模型不证明厂商原生BD操作已完成。 |

最终七项原生仿真各阶段退出码0，归档日志未检出WARNING/CRITICAL WARNING。每项命令、运行目录、阶段退出码和PASS标记见`runs.json`；同目录下各项子目录保留原始compile/elaborate/simulate日志与RESULT。

## 保留的失败事实

1. `ps_old_expectation_failure/`：首次旧PS用例失败于`BIST status/sequence`。旧预期`0x17f39`忽略已发布手动标定STATUS bit18；按既有合同更新为`0x57f39`并加入实际值诊断后通过。没有为适配测试改产品状态位，双轴本次也没有新增STATUS位。
2. Tcl模型首次末尾检查发生Python `TypeError: cannot use '_tkinter.Tcl_Obj' as a set element`；文件操作及脚本已经执行完成，是测试集合比较没有转字符串。只修测试，最终完整重跑5项通过。与产品/厂商命令无关。

## 独立发现修正

- **DA-001**（复核旧快照：`review-snapshot-before-DA001.json`）：租约到期同拍COMMIT原来走命令拒绝分支，掩盖FAULT bit8。现到期事件独立记录，截止拍COMMIT拒绝且产生超时，显式STOP/REVOKE与环境故障仍优先。新增到期前一拍、同拍、之后及STOP同时到期的端口边界检查；重新编译/展开/运行完整dualaxis通过。此修正只作用新扩展的到期错误原因，旧二维generate关闭路径无变化，已完成旧路径回归无需因无影响变化重复。
- **DA-002**：原冷复位断言前两个输出已低，刺激不足。已在实际AXI启动两轴并确认两输出同时高后断言冷复位，检查立即拉低，通过。
- 追加四轮750ms边界用例后首次仍使用旧5秒总仿真界限而超时；保存`dualaxis_test_timeout/`，将测试总界限改为8秒后通过，产品租约750ms未改。
- `project/sdc/ps/horizontal_reserved.xdc`只修旧注释，说明DUAL_AXIS_ENABLE=0保留低、=1受保护驱动；T15/W15约束不变。

## 未验证与交接

当前自测不包含新候选STA、资源、实际61.44MHz垂直机械位置或带载动作；双轴脉宽精度、保护逻辑不等于舵机已实际到位。通道物理映射和机械零位/正反/允许范围仍须用户之后标定。没有新增ILA，因为本批先用可控仿真检查明确数字语义；后续板测据具体失败属性再决定采集点。

主协调接续PS三维在线入口，必须先测角度再显式启用动作，跟随每次写AC与BC后COMMIT；配置可以在采集运行但双轴停用且排尾完时应用。两轴能力、原始锁帧资格及软件三维筛选分层核查，不能只改软件就声称旧位流支持双轴。独立非作者只读复核同一快照后，用户在自建副本运行更新Tcl并亲自综合、实现。

本批没有创建`codex_out`，Tcl测试临时树已自动删除；原生仿真数据库留在正式`simulation/work`，必要日志已归本目录，没有把数据库整份归档。
