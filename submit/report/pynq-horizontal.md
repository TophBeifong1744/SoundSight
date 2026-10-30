# PL+PS水平舵机：更新工程副本与PYNQ操作

> 2026-10-29 引脚更正：当前双轴方案为水平 T15、垂直 W16。本文旧 W15 位流及板测描述仅对应历史版本，不能作为新接线依据；现行操作见 [三维双轴说明](../board/instructions/pynq-three-d-dual-axis.md)。仓库现行脚本按 W16 检查，旧工程需先更正约束并重新实现。

日常按步骤操作请看[三种模式完整命令：调参、手动标定和声音跟随](../board/instructions/ps-manual-calibration.md)。

本批接入水平轴，垂直仅预留低电平输出。默认仍只测角度，不自动转动。
2026-10-23按用户明确接线更正：水平360°舵机信号T15，垂直220°舵机信号W15。
2026-10-23用户已重新生成位流，实际I/O报告确认T15/W15，最新同名SD完整包已更新。此前2026-10-22的V7/U7旧包不能混用。
用户已实测开发板给舵机供电可用，沿用该方式；开发板输入适配器为12V/1A，不能把12V当成舵机供电电压。

## 1. 当前已准备好的Servo工程：只更正引脚

直接打开你现有的`SoundSight_PS_Servo`副本，在所有运行结束后执行：

```tcl
source {你的SoundSight仓库/project/bd/update_ps_servo_pins.tcl}
```

脚本核对当前项目、两份本地XDC和引脚占用，备份到工程`handoff/before_servo_pins_*`，
只把`servo_pwm`改为T15、`servo_vertical_pwm`改为W15；不改RTL、BD、时钟、采样或软件。
看到`SERVO_PINS_UPDATED: horizontal=T15 vertical=W15`后，由你在GUI重新运行实现并生成bit；
若Vivado提示需要更新综合，按提示由你运行。检查新实现时序、DRC并导出同批bit/HWH/XSA再打包。
旧实现结果与旧位流不会因编辑XDC自动变成新引脚，不应直接拿旧SD包按T15/W15接线。

## 2. 若从Volume工程新建副本：完整接入入口

保留当前通过板测的Volume原工程。由你复制或另存为新工程，建议命名
`SoundSight_PS_Servo`（更新脚本要求工程名以`_Servo`结尾，防止误更新原工程）。
放在你自己选的仓库外工作目录。确认BD文件本身也在副本里，不能仍登记原工程的BD。

然后在**该副本**的Vivado Tcl Console中执行：

```tcl
source {你的SoundSight仓库/project/bd/update_ps_horizontal.tcl}
```

这是更新脚本，不会创建副本。自动备份副本当前XPR、BD、待改源码与约束；
复制RTL/初始化数据到副本的`horizontal_sources`，本次覆盖6份动作通路源码，
其余已登记RTL/数据保留实际内容。约束复制到`horizontal_constraints`，只改舵机引脚。
重新打开副本以刷新模块信息，Validate BD、生成Output Products并更新Wrapper。
DDR、MIO、FFT、采集时钟、计算时钟和AXI地址均沿用你的原配置。

看到`HORIZONTAL_PREPARED`和`NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED`
后，由你点击综合、实现；检查实现时序与DRC后再生成bit。脚本不会启动这些操作。
如果中途出错，保留`handoff/before_horizontal_*`备份和报错，不改回原工程重新试。

本批BD设置：`ps_link.ACTUATOR_BOUND=1`、`SERVO_MAX=360`、硬件范围0～360°。
硬件范围是电气编码能力，不代表云台允许走满360°；实际机械范围由PYNQ配置缩小。

| 信号 | 副本更新后位置 | 本批行为 |
|---|---|---|
| `servo_pwm` | FPGA T15，LVCMOS33 | 水平PWM，20ms周期，500～2500us对应0～360° |
| `servo_vertical_pwm` | FPGA W15，LVCMOS33 | 垂直220°舵机预留，固定低电平，不驱动 |

原Volume位流水平端口在T15；此前已交付的Servo位流却为V7/U7。本次明确更正为T15/W15，需新bit。
两路信号不能并接。垂直不发PWM并不保证机构保持姿态；本批不实现双轴联动。
按实际连接器位置和针脚方向接线，电源与PWM信号分开、两者共地；接线和上电由你执行。

## 3. 配套bit/HWH和软件

从同一次通过检查的工程导出bit/HWH，板端命名仍为`soundsight.bit`和`soundsight.hwh`。
本次软件增量包不包含未生成的新bit/HWH，不能用旧音量位流测试动作。
建议先在SD保留原有包，然后用新的bit/HWH与软件组成独立板端目录，保留原Volume目录。
软件安装器不会替换bit/HWH、C库、校准文件或历史日志。

`soundsight_horizontal_update.zip`沿用现有安装器，解压根目录仍为`soundsight_normal_update`。
例如你已将配套bit/HWH与原ARM库放入`/home/xilinx/SoundSight_PYNQ_Servo`后：

```sh
python3 -m zipfile -e /boot/soundsight_horizontal_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_normal_update/install.py --destination /home/xilinx/SoundSight_PYNQ_Servo
cd /home/xilinx/SoundSight_PYNQ_Servo
sudo sh soundsight.sh prepare
```

切换为另一套bit时，先保存结果并停止旧程序；准备入口不会强行覆盖已经登记的另一overlay。
重启后进入新目录执行`prepare`可加载新bit；随后默认运行仍不驱动舵机。

## 4. PYNQ上标定，不需要重做Vivado

配置顺序是：前方对应的舵机角度、转向（1或-1）、允许最小角、允许最大角。
**没有自动填写的实物标定值。** 例如仅在你确认机构允许170～190°时，才使用下面的试调示例：

```sh
sudo sh soundsight.sh servo-config 180 1 170 190
sh soundsight.sh servo-config
```

配置保存在当前目录`horizontal.local.json`，只在下次运行时生效；修改配置本身不转动。
默认映射为“前方角度 + 转向 × 声源方位”，超出允许范围就撤输出，不夹到边界、不绕回另一侧。
本项目实际安装方式已由用户确认：麦克风固定，舵机带其他部件转动。

### 麦克风与转轴相对位置（全部在PYNQ配置）

以麦克风阵列中心为原点，从上往下看水平面：X正方向是算法的0°，Y正方向是算法的+90°。
正方向须按当前阵列实际标记/测试确认，不直接猜成“板子的左边”。
填写**水平转轴中心**相对阵列中心的X、Y位置，单位厘米，允许负数和小数；不是舵机外壳边缘距离。
上下高度差不参与本次水平指向计算。

先完成上面的`servo-config`，再配置安装位置。以下仅是示例：转轴在X方向10cm、Y方向-5cm：

```sh
sudo sh soundsight.sh servo-geometry 10 -5
sh soundsight.sh servo-geometry
```

这会保存位置，并使用`DIRECTION_ONLY_NO_PARALLAX_CORRECTION`模式：只按声源方位转动。
**只有位置和方位，不能确定声源在哪个距离，因而不能精确补偿两者错开的角度。**
程序不会用音量猜距离。此模式中，填写的位置仅用于记录，暂不参与目标计算。

若当前试验已知声源距阵列中心的**水平距离**，例如200cm，才指定：

```sh
sudo sh soundsight.sh servo-geometry 10 -5 --source-range-cm 200
```

此时显示`USER_SUPPLIED_RANGE`。程序先按方位和该距离算出声源平面位置，减去转轴位置，
再算舵机应该朝向的角度。距离是你提供的固定实验参数，不是系统测距结果；声源远近改变时要重设。
不再知道距离时，重新执行不带`--source-range-cm`的命令即可关闭补偿。
示例：声源在阵列正前方100cm，转轴在Y正方向100cm，则转轴应朝-45°，不再是0°。

哪个部件需要朝向声源，就用那个部件的实际指向来标定`front_deg`：它与阵列X正方向平行时的舵机角度。
这是安装朝向的标定，不能用近处声源带来的偏角代替零位。
当前几何模型假定部件的指向轴线经过水平转轴；偏置镜头/探头若要求近距离精确对点，仍需其安装几何模型。
这里实现的是水平指向，不包含高度跟随，也没有机械位置反馈。

位置和距离与零位等参数一起保存在`horizontal.local.json`，下次运行生效。
重新设置`servo-config`会保留位置配置；旧版只有四个标定字段的文件继续使用原来的方位映射。
原始DOA、音量门限、多帧筛选和3°死区不变；几何转换只发生在最终舵机目标处，3°仍是阵列方位的死区。
声源恰好落在转轴上时方向无定义，程序撤销输出并显示`GEOMETRY_TARGET_UNDEFINED`，不会随意选0°。
手动定角`servo-angle`直接指定舵机角度，不叠加位置补偿；它不需要声帧，受机械限位、超时和停止保护。

手动标定已拆为独立模式，新位流下不需要声音：

```sh
sudo sh soundsight.sh servo-angle 180 --seconds 5
```

仍需先设置实测机械限位；180仅是确认安全后的试调示例。默认5秒后撤输出，Ctrl+C提前停止，
PL固定750ms看门狗保护程序失联。与声音采集互斥，旧帧先保存排空；实际细节和新RTL更新入口见
[手动标定说明](../board/instructions/ps-manual-calibration.md)。旧的`run normal --manual-angle`命令已停用。

## 5. 手动选择是否启动水平跟随

只测声音和角度（默认关闭转台）：

```sh
sudo sh soundsight.sh run normal
```

显式打开水平跟随：

```sh
sudo sh soundsight.sh run normal --horizontal-motion
```

**Ctrl+C停止当前运行并撤销PWM**。想保留测角、关闭转台，就停止后重新执行不带
`--horizontal-motion`的命令；本批不支持另开进程在运行中抢写控制寄存器。
每轮都须显式选择，不会保存“开机自动动作”。原`run debug`继续无动作。

音量与窗口设置沿用短命令`level N`、`filter N M`。
跟随使用音量门限、多帧筛选、圆周平均和3°死区后的目标。
好窗口建立目标后，窗口积累期间每个新鲜、音量合格、求解合格的真实帧可以续交相同目标；
这刷新750ms硬件看门狗，不改变死区内的位置。
积累期间偶发的单帧求解拒绝不提交新命令、不刷新看门狗，已有目标仅在原看门狗期限内保持。
低音量、断序或完整窗口不合格会撤销输出；跟随需下一个完整好窗口再恢复。
窗口末帧不合格时，即使该窗统计合格，也不绕过硬件当前帧资格检查。
STOP或撤销会让当前高脉冲完整结束，然后停止输出；它不是机械刹车。

## 6. 验证边界

本批离线检查入口：

```sh
python -B software/tests/test_horizontal_motion.py -v
python -B tools/run_sim.py horizontal
```

Vivado更新脚本的原生验证使用隔离临时输入，只做模块刷新、Validate和输出生成。
证据见`document/evidence/ps-horizontal-20261022`。没有替你运行实际工程的综合、实现、下载或转动；
新bit的时序、实际PWM电气/方向/机械范围和声音跟随效果仍需后续由你验证。
