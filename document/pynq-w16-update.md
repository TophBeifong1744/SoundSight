# W16垂直舵机更新与复测

2026-10-29：本包为 `soundsight_pynq_3d_speaker.zip`，根目录 `SoundSight_PYNQ_3D_Speaker`。水平输出 T15，垂直输出 W16，均为 Bank34 / LVCMOS33。硬件登记输入相对10月28日只改XDC的 W15→W16；XSA、bit、HWH已对应核验。实现WNS +0.047ns、WHS +0.036ns；同路由补查垂直20ns预算余量+11.935ns。旧CDC警告保留，不能称零警告；W16实板动作待本轮复测。

包含三维测角、双轴无声手动、显式纯声源 `follow-sound`、声纹许可 `speaker`、原音量/窗口/死区设置和短命令。加载不自动开轴。原板P02、声纹门限和个人标定不在ZIP内，不重新登记、不重装PYNQ。模型/原始模板属于私下交付内容，完整ZIP不上传公开GitHub。

## 更新

先停止板端正在运行的应用。关机断电后恢复正式信号连接：水平T15、垂直W16；交叉测试时接到T15的垂直线必须换回。不要带电换线。

在电脑将新ZIP覆盖SD卡Windows可见分区中的同名文件。保留BOOT.BIN、boot.py、BOOT.SCR、IMAGE.UB和REVISION。插回板子启动后，每条命令单独发送，串口开启换行：

```sh
cd /home/xilinx
sudo cp -a SoundSight_PYNQ_3D_Speaker SoundSight_PYNQ_3D_Speaker_backup_$(date +%Y%m%d_%H%M%S)
sudo python3 -m zipfile -e /boot/soundsight_pynq_3d_speaker.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -c "import json; s=json.load(open('SOURCE.json')); print('SERVO_PINS=',s['servo_pins'])"
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh status
sudo sh soundsight-3d.sh servo-config vertical
```

备份和解压有报错时先停止，不跳过。解压只更新包内文件，已有 `servo3d.local.json`、`settings.local.json`、`speaker-follow.local.json`、`speaker-target.local.json`、`speaker-profiles/` 和日志不会被此包覆盖。不要删除原应用目录再安装；不需要再执行 speaker-import。

应看到 `SERVO_PINS` 为T15/W16，prepare完成、LOADED=True、约100MHz、复位释放；status故障为0、双轴尚未启用。如果有故障或旧帧，保留状态再处理，不直接开始转动。

## 垂直复测

B此前试探配置是前方110、方向1、范围105～115。你若已改成90～130，下面110/115仍在范围内；以实际打印配置为准，不自动覆盖你的标定。确认机构在这两个目标附近不会顶住，逐条运行：

```sh
sudo sh soundsight-3d.sh manual --vertical 110 --seconds 3
sudo sh soundsight-3d.sh manual --vertical 115 --seconds 3
sudo sh soundsight-3d.sh status
```

本轮只开垂直轴，不要求声音或声纹。观察每条命令运行的3秒内是否转动；第一条可能已在当前位置，第二条约5°变化。顶住或持续嗡鸣立即Ctrl+C，必要时断电。不要为了看清动作直接跳到0/220°。

回传两条MANUAL_RESULT、实际动作和最后状态。commits表示控制器接受，不能代替机械动作；stop_confirmed表示撤销已确认。若仍无动作，下一步测命令有效期间W16至舵机端PWM，禁止靠继续放宽限位判断。

## 后续开机与模式

每次开机进入该目录执行 `sudo sh soundsight-3d.sh prepare`，无需再次解压。`run`默认只测角；`follow-sound --axes vertical`是明确选择的纯声音跟随；`speaker --axes vertical`及`run --axes vertical`要求声纹许可。先确认手动复测成功和机械标定，再开启自动跟随。完整模式说明见 [三维操作](pynq-three-d-dual-axis.md) 和 [声纹操作](pynq-speaker-3d.md)。
