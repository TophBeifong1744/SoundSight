# 水平舵机版完整SD包

> 2026-10-29 引脚更正：当前双轴方案为水平 T15、垂直 W16。本文旧 W15 位流及板测描述仅对应历史版本，不能作为新接线依据；现行操作见 [三维双轴说明](pynq-three-d-dual-axis.md)。仓库现行脚本按 W16 检查，旧工程需先更正约束并重新实现。

**PS兼容修复已接入：** 新手动状态位不会再被C桥误拒绝；安装后务必执行build_solver.sh重编库。在线遇到C bridge -2可按`document/pynq-manual-status-fix.md`处理，不必重载FPGA。

从SD备份/安装到日常开机、调参和动作切换的完整步骤，统一见`document/ps-manual-calibration.md`；其中第0节覆盖本次完整包安装。

**2026-10-23 22:59新位流：已接入独立无声手动标定，23:03新XSA核对一致。** 最新实现I/O报告确认水平T15、垂直W15，均为Bank34、LVCMOS33；
新bit/HWH与用户新导出的XSA逐字节一致。此前V7/U7包已被本同名包替换。

`soundsight_pynq_servo.zip`包含本次Servo工程的配套bit/HWH、最新PS程序、C求解器源码、短命令启动器、自测和实现报告。
解压根目录为`SoundSight_PYNQ_Servo`，与原Volume目录分开。保留现有PYNQ镜像，不替换BOOT文件。
水平轴具备输出能力，但软件默认关闭动作；垂直输出固定LOW。新组合的ARM/机械测试尚未执行。

本包已包含无声手动标定位流和最新PS命令。日常三种模式、门限/窗口调整、限位和切换见`document/ps-manual-calibration.md`。此前下午的T15/W15位流不含这项功能。

## 首次安装

将新的`soundsight_pynq_servo.zip`同名覆盖到SD卡可见分区根目录；保留BOOT.BIN、IMAGE.UB、boot.py等启动文件。正常关机、断电后搬运SD，安全弹出后插回板子并启动Linux。本轮从刚开机、尚未prepare的状态安装，串口每次发送一整行。

如果已经有Servo目录，先备份一次（不存在则跳过）：

```sh
if [ -d /home/xilinx/SoundSight_PYNQ_Servo ]; then sudo cp -a /home/xilinx/SoundSight_PYNQ_Servo /home/xilinx/SoundSight_PYNQ_Servo_backup_$(date +%Y%m%d_%H%M%S); fi
```

安装：

```sh
sudo python3 -m zipfile -e /boot/soundsight_pynq_servo.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_Servo
sudo sh software/ps/build_solver.sh
```

C库在本板编译，避免混用Windows或其他架构的二进制。原Volume目录不动；已有Servo目录会覆盖同名程序和bit/HWH。
若已安装过旧Servo包，停止程序后更新；建议本轮从刚开机、尚未prepare的状态开始。
解压会覆盖同名程序/bit/HWH，不覆盖包内没有的个人配置与日志。删除旧包留下、现已失效的警示文件：

```sh
sudo rm -f /home/xilinx/SoundSight_PYNQ_Servo/PIN_UPDATE_REQUIRED.txt
```

新目录没有你的个人音量门限/窗口设置。若原Volume目录设置已调好，可以复制这一份：

```sh
sudo cp -n /home/xilinx/SoundSight_PYNQ_Volume/settings.local.json ./settings.local.json
```

如果原文件不存在，直接用短命令设置你已试出的门限：`sudo sh soundsight.sh level 数值`。
`sh soundsight.sh level`查看当前值，`sh soundsight.sh filter`查看窗口设置；不要把默认试调值当成标定结果。
随后：

```sh
sudo sh soundsight.sh prepare
sudo sh soundsight.sh run normal
```

prepare自动选择PYNQ解释器、执行离线检查、加载新位流、配置时钟并检查接口；不会启动舵机。
如旧overlay仍被登记，先停止旧程序并保留日志，重启后从新目录prepare；不要在两个目录同时运行。
normal默认关闭动作，每0.5秒输出测角/无效原因。Ctrl+C停止并保存必要汇总。

## 以后每次开机

```sh
cd /home/xilinx/SoundSight_PYNQ_Servo
sudo sh soundsight.sh prepare
sudo sh soundsight.sh run normal
```

编译只需首次安装或C源码更新时执行。

## 手动启用水平轴

用户已确认麦克风固定。位置参数也可在PYNQ设置：`servo-geometry X_CM Y_CM`保存转轴位置，
不知道声源距离时维持只按方位；已知水平距离才加`--source-range-cm R_CM`补偿偏移。
坐标定义、零位标定与示例见下方水平轴说明；无需修改BD或重新生成bit。

先按`document/ps-manual-calibration.md`确认接线、设置前方零位/正反向/机械范围，并进行小范围无声定角标定。
包内不提供未经实测的机械标定值。完成后才用：

```sh
sudo sh soundsight.sh run normal --horizontal-motion
```

Ctrl+C停止；重新运行不带该参数的normal即恢复只测角度。详细调参、固定角试调、停止行为见同目录水平轴说明。
多帧筛选、圆周平均、3°死区和音量门限均已包含；启用动作每次需要明确指定，不会开机自动转动。

### 第一次水平标定

本包已具备无声标定。先设置机械限位，再用`sudo sh soundsight.sh servo-angle 180 --seconds 5`。
不再需要播放声音；命令默认5秒后停止，Ctrl+C可提前停止。180只是确认机构安全后的示例，
不是已测零位。完整流程、参数含义和模式切换见`document/ps-manual-calibration.md`。

## 包内容与证据

- `soundsight.bit`、`soundsight.hwh`：与本次XSA内文件逐字节一致。
- `soundsight.sh`、`software/ps`、`software/common`：运行入口、PS程序和可在板端编译的C源码。
- `software/tests`、`tools`：必要离线检查及支持文件。
- `document`、`README.md`：操作和接口说明；`reports`：本次实现时序与DRC原件。
- `SOURCE.json`：来源和验证边界。XSA用于打包配对检查，不需要传到PYNQ运行。

本次实现WNS=+0.371ns、WHS=+0.036ns，setup/hold/pulse-width失败端点均0；DRC仍有流水线/BRAM等Warning，不能称无告警。
本批RTL/软件自测与打包证据在仓库`document/evidence/ps-manual-calibration-20261023`；不能替代本次实物PWM和机械范围验证。
