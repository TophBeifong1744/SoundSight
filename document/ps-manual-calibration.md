# PYNQ日常操作：只测角度、无声手动标定、声音跟随

> 2026-10-29 引脚更正：当前双轴方案为水平 T15、垂直 W16。本文旧 W15 位流及板测描述仅对应历史版本，不能作为新接线依据；现行操作见 [三维双轴说明](pynq-three-d-dual-axis.md)。仓库现行脚本按 W16 检查，旧工程需先更正约束并重新实现。

如遇`C bridge error`且`bridge_status=-2`，先按[状态位兼容修复](pynq-manual-status-fix.md)处理；最新版完整包已修复，需重编C库，位流不变。

手动标定不需要声音、不启动采集、不读求解器、不伪造或消费声帧。声音跟随保留原来的资格检查。
水平T15、垂直W15不变；垂直仍固定LOW。本轮新bit已由用户生成，22:59实现报告通过；23:03新XSA与bit/HWH一致。使用最新完整`soundsight_pynq_servo.zip`即可，下午旧位流不具备这项功能。

## 0. 本次完整包安装：只做一次

本说明适用于最新`soundsight_pynq_servo.zip`，解压目录为`/home/xilinx/SoundSight_PYNQ_Servo`。包含一键准备、参数调整、三种运行模式、C求解器源码及新bit/HWH，**不需要叠加旧更新包，也不用重装PYNQ镜像**。

### 0.1 电脑端准备SD卡

正常停止板端程序并关机、断电后取卡。将最新`soundsight_pynq_servo.zip`覆盖复制到SD可见分区根目录。Windows盘符可能是G:或H:，板端挂载路径仍为`/boot`。

- 保留`BOOT.BIN`、`boot.py`、`BOOT.SCR`、`IMAGE.UB`、`REVISION`；不要动系统启动文件。
- 旧normal_update、ps_sd_batch_v1、pynq、pynq_volume、ram_queue_update安装ZIP可删除，已经解压在Linux分区的程序不会因此消失。
- 板测日志ZIP先复制到电脑保存，再删除卡上副本；不要把唯一测试记录当安装包删除。
- 安全弹出SD，插回断电的板子后开机。此次应在刚开机、尚未prepare/加载旧工程时更新。

### 0.2 串口输入规则

在`xilinx@pynq:~$`提示符后发送命令，不要把提示符也复制进去。每次发送一整行，串口行尾选择LF。等待该条执行结束，再发下一条。

出现`[sudo] password for xilinx:`时输入密码；本板此前使用`xilinx`。密码不回显是正常的，此时不要发送下一条命令。

### 0.3 备份原Servo目录

已经成功执行过本次备份命令，就跳到0.4；否则执行一次：

```sh
if [ -d /home/xilinx/SoundSight_PYNQ_Servo ]; then sudo cp -a /home/xilinx/SoundSight_PYNQ_Servo /home/xilinx/SoundSight_PYNQ_Servo_backup_$(date +%Y%m%d_%H%M%S); fi
```

**返回提示符且无报错是正常的**：目录存在就完成备份，不存在就跳过。这个步骤不安装新包，也不加载FPGA。

### 0.4 解压最新完整包

先确认文件存在，再解压：

```sh
ls -lh /boot/soundsight_pynq_servo.zip
```

```sh
sudo python3 -m zipfile -e /boot/soundsight_pynq_servo.zip /home/xilinx
```

```sh
cd /home/xilinx/SoundSight_PYNQ_Servo
```

包会覆盖同名程序和bit/HWH；包里没有个人`settings.local.json`、`horizontal.local.json`或历史日志，因此不覆盖已有参数和日志。原Volume目录保留，不要同时从两个目录运行程序。

如果新建Servo目录、此前只在Volume调过音量和窗口，可选择复制原设置（只有原文件存在、目标文件不存在才复制）：

```sh
if [ -f /home/xilinx/SoundSight_PYNQ_Volume/settings.local.json ] && [ ! -e settings.local.json ]; then sudo cp /home/xilinx/SoundSight_PYNQ_Volume/settings.local.json ./settings.local.json; fi
```

不复制也可按第2节重新设置。不会自动猜测机械零位或限位。

### 0.5 在板上编译C库

```sh
sudo sh software/ps/build_solver.sh
```

无报错后继续。首次安装或C源码更新时需要此步；普通重启不必重新编译。不要复制电脑Windows的编译产物代替板端ARM库。

### 0.6 一键准备，再只测角度

```sh
sudo sh soundsight.sh prepare
```

看到`READY_FOR_DEBUG`后再执行：

```sh
sudo sh soundsight.sh run normal
```

此时只计算/显示，不驱动舵机。prepare自动选择PYNQ Python、执行必要检查、加载位流并配置时钟；不用手动设置XRT环境或再次输入SLCR寄存器命令。若中途出现STOP/Traceback，停在该步保留完整输出，不继续执行动作命令。

本次安装完成后，日常直接用下面第1节；手动标定看第3节，声音跟随看第4节。

## 1. 每次开机：进入目录并准备

以下命令在板子的串口Linux终端逐条执行，发送行尾选LF。目录按Servo软件包默认位置；如果实际安装在其他目录，只替换cd路径。不要同时运行两份采集/动作程序。

```sh
cd /home/xilinx/SoundSight_PYNQ_Servo
sudo sh soundsight.sh prepare
```

看到`READY_FOR_DEBUG`再继续。prepare可能加载位流、设置时钟并检查接口，但不主动驱动舵机；同一会话已准备好后，不必每次换模式都prepare。

| 想做什么 | 命令 | 舵机行为 |
|---|---|---|
| 只调音量和定位 | `sudo sh soundsight.sh run normal` | 不驱动 |
| 无声手动定角 | `sudo sh soundsight.sh servo-angle 180 --seconds 5` | 显式定角，需先配限位 |
| 声音跟随 | `sudo sh soundsight.sh run normal --horizontal-motion` | 合格声音方向经过筛选和映射后驱动 |
| 保存逐帧排查日志 | `sudo sh soundsight.sh run debug --frames 1000` | 不驱动，限量调试 |

手动和跟随都只控制水平T15；垂直W15保持LOW。命令中的角度/门限均是示例，不是实测标定值。

## 2. 先不驱动舵机，把角度输出调好

查看当前音量门限、每组帧数和合格数：

```sh
sh soundsight.sh level
sh soundsight.sh filter
```

启动连续只测角度模式：

```sh
sudo sh soundsight.sh run normal
```

每0.5秒打印当前方向或无有效输出的原因。默认连续运行，按Ctrl+C结束；普通正常模式不逐帧写SD，停止后保存必要汇总。日志路径显示在`OUTPUT=`。

### 2.1 调整音量门限

先Ctrl+C停止，等Linux提示符回来，再保存新门限。例如：

```sh
sudo sh soundsight.sh level 5000
sudo sh soundsight.sh run normal
```

- 5000只是试调示例。范围1～16777215，单位是去直流PCM平均绝对幅度计数，不是分贝。
- 门限越大越难通过；越小越容易通过。先观察安静环境的`LEVEL`，再观察目标声音，逐步选择合适值。
- 音量过关不等于角度过关；方向求解和多帧一致性仍需合格。
- 修改后下次运行生效，不需要重新生成bit或重新prepare；本地保存，重启后保留。

### 2.2 调整每组多少帧、最低多少个合格角度

同样先停止，再设置，例如一组10帧、至少6个有效角度：

```sh
sudo sh soundsight.sh filter 10 6
sudo sh soundsight.sh run normal
```

恢复默认20帧/12个：

```sh
sudo sh soundsight.sh filter 20 12
```

`filter N M`的含义：

- N是**一组总帧数**，不是“积累N个有效角度”。音量满足条件但求解拒绝的帧仍计入组内，不参与平均。
- M既是最低有效角度数，也是剔除离群角度后的最低保留数。
- 必须满足`1 <= M <= N <= 100`。仍要求至少三分之二有效角度落在中心±10°范围内，再做圆周平均和3°死区处理；仅达到M不保证输出。
- 低音量、断序等会清空窗口并重新积累，所以等待时间不固定。N小通常反应快，N大统计更多，但不能消除环境反射。

只想临时试一轮、不覆盖保存值：

```sh
sudo sh soundsight.sh run normal --min-level 5000 --window-frames 10 --min-valid 6 --frames 1000
```

这条会运行1000帧后停止。`--frames`是整轮数量，`--window-frames`是一组大小；不要混淆。门限和窗口配置保存在`settings.local.json`，正常和调试模式共用。

### 2.3 看懂串口提示

- `LEVEL`：当前音量计数；`NO_OUTPUT: LOW_VOLUME`表示音量未过关。
- `WINDOW=7/20 VALID=5 MIN=12`：这组收了7帧，其中5个有效角度，目标是收满20帧且满足最低12个要求。
- `LAST_GROUP`：上一组完整结果；`INSUFFICIENT_VALID_ANGLES`是有效角度太少，`INSUFFICIENT_CONSENSUS`是方向不够一致。
- `LAST_CLEAR`：最近一次清窗原因；反复LOW_VOLUME会导致一直收不满。
- `ACCEPTED_HELD_3DEG`：本组通过，但变化处于3°死区，保持目标；`TARGET=...(HISTORY)`是历史结果，不是当前新有效方向。

## 3. 无声手动标定水平轴

先停止采集，再查看机械配置：

```sh
sh soundsight.sh servo-config
```

第一次尚未配置时可能提示文件不存在。保存配置的格式为`servo-config 前方角度 正反方向 最小角度 最大角度`。以下仅为中位附近小范围示例，必须先确认机构允许这个范围：

```sh
sudo sh soundsight.sh servo-config 180 1 170 190
```

含义：声源在阵列前方0°时对应舵机180°；方向为+1；允许目标170～190°。方向只能是1或-1，角度满足`0 <= 最小角 <= 前方角 <= 最大角 <= 360`。
配置命令只保存，不动作。首次转到目标的途中仍可能经过大行程，目标限位不是当前位置反馈。

不需要播放声音，分别执行：

```sh
sudo sh soundsight.sh servo-angle 180 --seconds 5
sudo sh soundsight.sh servo-angle 185 --seconds 3
sudo sh soundsight.sh servo-angle 175 --seconds 3
```

每条返回提示符后再执行下一条。省略`--seconds`默认5秒，可设置0.1～60秒；到时撤PWM，Ctrl+C可提前停止。PL另有750ms续期看门狗，程序卡住或失联会撤输出，恢复后不自动重启。

手动指定的是**舵机绝对目标角**，不受音量、窗口、前方偏置、正反方向或阵列位置补偿影响；仍检查机械限位。撤PWM不代表机械必然锁定或瞬间停止；打印目标不代表机构已到位。

根据观察确定真实零位、方向和允许范围，再重新保存`servo-config`。例如同一已确认范围下把声音跟随方向反过来：

```sh
sudo sh soundsight.sh servo-config 180 -1 170 190
```

改变方向只影响声音到舵机角度的映射，不会改变`servo-angle 185`的绝对目标。不要为了跟随覆盖全周，直接把未验证的机械范围改成0～360。

## 4. 启用声音跟随

音量/窗口和机械配置调好后，显式开启：

```sh
sudo sh soundsight.sh run normal --horizontal-motion
```

使用保存的门限、窗口和机械配置。声音合格且完整窗口通过筛选后才请求更新方向，3°死区抑制小幅抖动；低音量/坏窗口等沿用撤输出保护。目标超出机械范围会拒绝，不强行夹到边界。

未启用位置补偿时，舵机目标为“前方角度 + 正反方向 × 声源方向”；有保存的安装位置/已知距离时按既有配置补偿，详见[pynq-horizontal.md](pynq-horizontal.md)。手动标定不使用这项补偿。

也可以仅本轮临时调整声音参数：

```sh
sudo sh soundsight.sh run normal --horizontal-motion --min-level 5000 --window-frames 10 --min-valid 6
```

## 5. 切换模式和改参数的固定步骤

1. 当前命令还在运行时，**按Ctrl+C**（串口工具发送Ctrl+C控制字符，不是输入字母“Ctrl+C”），等返回`xilinx@pynq:...$`。
2. 可先查看状态：

```sh
sudo sh soundsight.sh status
```

3. 正常结束后直接启动下一模式。若提示`OLD_FRAMES`或存在未消费旧槽，先保存排空：

```sh
sudo sh soundsight.sh drain
sudo sh soundsight.sh status
```

`drain`不启动新采集、不驱动舵机；保存到新的调试日志。若提示设备仍活动，先找回运行进程正常停止；其他故障先保留提示和日志排查，不用重下载或全清故障绕过。
只有普通STOP标记0x40时，新运行/手动标定入口会按既定流程处理，不需要自己写寄存器清错。

4. 选择下一条命令：

| 切换目的 | 停止上一模式后执行 |
|---|---|
| 跟随 → 只看角度 | `sudo sh soundsight.sh run normal` |
| 只测/跟随 → 手动 | `sudo sh soundsight.sh servo-angle 180 --seconds 5` |
| 手动 → 跟随 | `sudo sh soundsight.sh run normal --horizontal-motion` |
| 修改门限/窗口 | `sudo sh soundsight.sh level 5000` / `sudo sh soundsight.sh filter 20 12`，然后重新启动所需模式 |

没有后台永久“开舵机”开关：`--horizontal-motion`只对本次命令有效；手动命令只对本次有限时长有效。重启、prepare、修改配置都不会自动恢复动作。
旧`run normal --manual-angle ...`已经停用，统一用独立`servo-angle`。

## 6. 保留调试模式，但不拿它做默认长稳运行

需要逐帧排查时：

```sh
sudo sh soundsight.sh run debug --frames 1000
```

它保存详细JSONL，可能受SD速度影响。正常运行用`run normal`，只保留必要统计/故障和结束汇总。两种模式都自动生成日志名，不覆盖上一轮；长期多轮运行仍需整理旧日志。
调试模式不支持`--horizontal-motion`。停止并排空后，再切回正常只测或声音跟随。

## 硬件保护和接口

仅PS寄存器扩展，原SPI/冻结帧ABI与`0x6c`版本不变。STATUS bit18表示扩展存在（仍需bit19动作已绑定）；
软件先检查该位，再读新地址，旧位流拒绝前不会写寄存器。

| 地址 | 含义 |
|---|---|
| 0x70只读 | 能力版本0x4d534301 |
| 0x74 | 写0=STOP，1=ARM，2=COMMIT；读bit0=手动许可，bit1=当前脉冲排尾 |
| 0x78 | 手动目标角[8:0]，其余位必须0 |
| 0x7c | 最小角[8:0]、最大角[24:16]；其余位0。未写有效限位不能ARM |

ARM必须采集关闭、BIST关闭、无旧槽、无排尾、无故障；只ARM不输出PWM。
COMMIT必须已ARM、目标在软件写入的限位和硬件静态范围内。运行中不能修改限位。
PL固定750ms看门狗从ARM开始计时，只有有效COMMIT续期，反复ARM不能续期。PS每100ms提交同一目标；
串口打印在ARM前和STOP后，不阻塞续期。程序失联/卡住/被终止，PL超时撤输出并置FAULT bit8，恢复不自动重启。
STOP、总线复位、故障会撤许可；正在输出的高脉冲完整排尾。冷复位立即LOW。
普通ACT STOP与SYS禁用同样停止手动PWM；手动运行/排尾时禁止切入采集。任何异常模式切换按故障处理。
手动错误复用FAULT bit7、非法寄存器bit1、STOP bit6；保留原状态和错误，不自动全清故障。

## 验证范围

`python -B software/tests/test_manual_servo.py -v`：假寄存器/独立看门狗模型；无声音、限位、故障、旧硬件拒绝、Ctrl+C、续期失败不自动重启。
`python -B tools/run_sim.py manual`：真实AXI/寄存器/PWM，无声输入标定、限位/模式互斥、750ms比例时基看门狗、排尾、复位。
原`horizontal`仿真继续以61.44MHz计数配置检查500～2500us、声帧资格、STOP；`pslevel`检查音量/队列/BIST兼容。
自测与BD准备不等于新候选实现时序或实板机械验证。完整证据见`document/evidence/ps-manual-calibration-20261023`。

## 附录A：工程维护入口（日常安装无需执行）

### 重新修改RTL时使用

打开你现有的外部`SoundSight_PS_Servo`，确认没有运行中的综合/实现，在Tcl Console执行：

```tcl
source {你的仓库/project/bd/update_ps_manual.tcl}
```

脚本核对实际登记约束为T15/W15，备份到`handoff/before_manual_*`；复制更新`ss_ps_control_regs.sv`、
添加`ss_manual_servo.sv`到工作工程，刷新ps_link模块、Validate并生成Output Products。端口、BD连线、时钟与引脚不变。
看到`MANUAL_PREPARED`后，由你点击综合、实现和生成位流。导出同批bit/HWH/XSA后再更新完整SD包。
本批新增一套小型PWM计时/保护逻辑以保持原声音控制器和STM32路径不变，实际资源与时序以你的新实现报告为准。

### 仅更新PS软件时使用增量包

当前优先使用包含新bit/HWH的完整`soundsight_pynq_servo.zip`，按[pynq-horizontal-sd.md](pynq-horizontal-sd.md)安装，然后直接从本文第1节开始。无需再单独安装增量。
下面的`soundsight_manual_update.zip`仅供以后单独更新PS代码，不含bit/HWH；不能用软件增量让旧位流获得新硬件功能。

软件包复制到SD根目录后，在板端执行（当前Servo软件目录以实际位置为准）：

```sh
python3 -m zipfile -e /boot/soundsight_manual_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_normal_update/install.py --destination /home/xilinx/SoundSight_PYNQ_Servo
cd /home/xilinx/SoundSight_PYNQ_Servo
```

安装器备份原程序，不改bit/HWH、标定配置或自动启动动作。更新后再按以下短命令准备/标定。
新位流替换后使用干净启动状态再prepare，避免把仍驻留的旧位流误认为已更新。


## 附录B：常见卡点

| 现象 | 怎么处理 |
|---|---|
| 备份/解压后没有文字，提示符已返回 | 无报错通常正常；继续下一步。备份不存在的旧目录会直接跳过 |
| `/boot/...zip`找不到 | 先`ls -lah /boot`核对准确文件名和挂载；不要猜新路径反复解压 |
| sudo反复提示密码 | 此时只输入密码，不要粘贴下一条命令；输入不回显 |
| 串口只回显命令、不执行 | 行尾选LF；若看到`>`续行提示，先发送Ctrl+C再完整重发，不发送多行Python片段 |
| `OLD_FRAMES` | 停止原程序，再按第5节drain保存排空旧帧 |
| `New manual-calibration bitstream required` | 当前电路不具备无声标定；确认本次新完整包及新位流确实加载，不能只更新PS代码 |
| `LOW_VOLUME` | 声音未过门限；先停止后调整level，再运行 |
| `COLLECTING`长时间不结束 | 看WINDOW、VALID和LAST_CLEAR；低音量/断序清窗会重新累计 |
| 跟随不转但手动能转 | 查声音窗口是否通过、映射是否越限及故障提示；不要取消保护强行动作 |

更新bit/HWH应从干净启动状态开始；同一会话只修改门限/窗口或切换模式，不需要重新加载位流。保存测试记录后再正常关机，勿带电插拔麦克风或SD。
