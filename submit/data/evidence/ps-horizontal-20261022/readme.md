# 水平舵机接入候选的自测证据

2026-10-22。本批由AI编辑/自测；没有声称独立复核或机械闭环验收。
用户创建外部工作副本并亲自综合、实现、生成bit；本批没有修改用户F盘原工程。

## 实际结果

- PS最终交付包：12组、167项离线测试通过，其中21项水平动作接合测试。
  在临时假安装目录实际解压/安装/执行，29份payload与源码逐字节一致，
  Python3.8语法检查通过；bit/HWH、ARM库及旧日志保留。见`software-final`。
- Tcl入口4项保护测试通过：拒绝原Volume名称、拒绝在途运行、拒绝错误器件，
  允许idle的用户副本进入BD阶段。既有音量脚本7项回归通过。
- XSim三例通过：`horizontal`、`actuator`、`pslevel`，见`xsim`。
  新例实际连接`bd_ps_link → AXI寄存器 → 快照 → 动作保护 → PWM`，
  使用61.44MHz计数配置，独立检查0/90/180/270/360°对应500/1000/1500/2000/2500us；
  检查ARM独立于动作、STOP完整排尾、复位保帧撤许可、看门狗、垂直恒低。
  旧动作负例检查重放、BIST、无锁帧、范围和故障；旧音量例检查双槽与ABI。
- 实际Vivado2025.2隔离副本：模块刷新、Validate、Output Products及Wrapper生成通过。
  `bd-r11/audit.json`检查实际前后BD：34条原连线、18个其他组件、AXI接口/地址和原端口保持；
  只改ps_link动作参数并增加垂直低电平端口/连线。6份安装的动作通路RTL与仓库一致；
  两路引脚为V7/U7，生成HWH的动作、音量、时钟及量程参数匹配。
  没有运行综合/实现/bit生成/下载；没有更改PS DDR/MIO/时钟和原用户TclStore。

## 行为预期

默认不请求动作；有明确机械配置和显式开关才运行水平轴。合法完整窗口给出目标，
后续积累期仅在新鲜、真实、音量合格、单帧求解合格的锁帧上续交相同目标，再CONSUME。
3°死区不阻止合法续期；被拒单帧不刷新看门狗，已有目标仅在原750ms租期内保持。
低音量/断序/坏窗口撤许可，重新合格后再开；窗口末帧不合格不绕过当前帧资格。
机械越界拒绝，不夹取、不环绕。手动定角仍需要合格真实声帧；BIST不能动作。

连续正常模式保留固定统计，新增motion_commits和最近动作状态，不新增逐帧磁盘日志。
停止事件在本轮提交前检查；普通STOP保完整当前PWM高脉冲，冷复位立即低。

## 运行命令

```text
python -B software/tests/test_horizontal_motion.py -v
python -B software/tests/test_horizontal_tcl.py -v
python -B software/tests/test_ps_volume_tcl.py -v
python -B tools/run_sim.py horizontal
python -B tools/run_sim.py actuator
python -B tools/run_sim.py pslevel
python -B tools/check_horizontal_bd.py --project <原工程XPR只读输入> --output <新证据目录>
python -B tools/check_normal_update.py --archive release/output/soundsight_horizontal_update.zip --output <新证据目录>
```

板端操作见`document/pynq-horizontal.md`；校准值未假定，板端`servo-config`保存，默认无自动动作。

## 保留的失败事实

`preparation-failures.zip`保留本轮失败日志和测试输入入口：
隔离环境TclStore包路径/Windows临时路径、搭建夹具时.srcs初始化及BD放置目录问题，
以及真实API发现的BD pin对象前缀、生成子源重复登记和关闭工程后旧BD句柄失效。
测试辅助程序修正环境与输入布局；更新脚本使用实际对象、排除生成子源、保存纯文本BD名称后通过。
用户的原工程未用于尝试性修复，也没有靠启动综合或升级PS7绕过错误。

首轮软件回归发现旧worker测试夹具未带新增可选参数，以及旧HWH测试期望无条件禁止动作能力；
前者以默认OFF兼容，后者仍拒绝不完整的动作配置，并新增完整HWH/显式命令测试。
旧音量Tcl测试曾依赖字符串切割隐藏自动入口，现使用正式library_only入口，7项通过。
中间通过包被最终包替代；最终结果以software-final为准。

## 未测范围与收尾

没有新候选综合/布局布线STA、板端ARM动作运行、实际PWM电压/波形、机械标定或声学跟随结论。
RTL复用原保护逻辑，垂直输出仅常量；量程ROM改变仍需用户的新实现报告，不能沿用旧WNS。
原SD包/旧位流保持，不把本次模拟HWH当成可下载产物。
本轮临时工程、仿真数据库及中间ZIP在必要日志/配置归档后清理；未创建codex_out任务堆。
