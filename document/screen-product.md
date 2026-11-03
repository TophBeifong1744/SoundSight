# P1：上电直接进入屏幕

2026-11-03统一维护版包含P1及采集服务、方向窗口、180°显示/触摸、旧Pillow、确认删除用户和快速启动更新。适用匹配S2＋CF1A＋CP1/VF1板端。现场操作与本次补测见[证据](evidence/final-board-20261103/README.md)，PC模拟验证单独记录。

## 一次安装，以后不需要串口启动

将 `soundsight_screen_product_p1.zip` 放到 SD 启动分区。先在旧面板按 STOP，等待停止确认，
再到 DIAGNOSTICS → EXIT panel。出现命令提示符后执行以下两条单行命令：

```sh
sudo python3 /boot/soundsight_screen_product_p1.zip
sudo reboot
```

安装成功标志为 `SCREEN_PRODUCT_P1_INSTALLED=`，其中 `autostart_enabled=true`、
`service_started=false`、`hardware_actions=0`。安装只更新文件并登记下一次开机的服务，
不会当场运行采集或驱动舵机。旧文件保存在应用目录的 `backup_screen_product_p1_*`。

保留板端声纹、选中目标、声纹门限/TTL、音量和筛选参数、两轴标定、日志、匹配的 bit/HWH。
如果提示 `BASELINE_MISMATCH` 或 `LOCAL_CHANGE_PRESERVED`，记录该文件名；安装没有覆盖未知版本。
这不是新的 SD 系统镜像，不需要重新复制旧更新包，也不需要改 Vivado 工程。

## 四项产品化内容

- 开机服务在bootpy完成后执行快速prepare，保持ABI、安装完整性、时钟和互斥检查，进入默认关轴界面。
- HOME选择模式、轴与启停；USERS录入/切换/二次确认删除指定用户；SETTINGS保存下一会话参数；DIAGNOSTICS诊断与确认关机。
- STOP需读回确认；故障不自动恢复跟随。用户设置、声纹模板与日志在升级中保留。

系统准备和位流加载期间屏幕可能暂时无画面；视频通路就绪后显示触摸初始化状态。
能够正常输出视频时，触摸或运行错误保留在屏幕上。若位流、视频 DMA 或显示供电本身故障，
无法保证屏幕显示错误，此时保留系统日志，服务不循环重启或自动恢复跟随。

## 屏幕操作

### HOME

- Change mode：SOUND 是普通声源跟随；SPEAKER 要求当前声纹许可。模式选择会保存。
- Select axes：off / horizontal / vertical / both。每次开机及停止后回到 off，不保存动作许可。
- START：明确按下才开始当前模式；STOP 在所有页面固定可见。
- SPEAKER 显示当前目标、分数、许可与剩余 TTL；没有门限时不授予许可。

### USERS

- Next user → SELECT：切换已登记的目标。沿用原规则，切换时清除旧门限；随后在 SETTINGS 配置该目标的门限。
- NEW voice：自动分配尚未使用的 `userN`，原用户不覆盖。默认录 5 秒，可选 2～10 秒。
- RECORD 后显示 3、2、1 倒计时；看到 **SPEAK NOW** 后持续讲话，看到 Processing 后停止讲话。
- 保存后显示新用户编号；新录入不会自动切换目标或授予动作。选择该用户，再配置其门限即可使用。
- 录入失败或取消保留原目标和旧声纹；STOP 可取消录音/计算。出现错误后先到 DIAGNOSTICS → Recheck，确认设备空闲。

DELETE仅针对当前选择用户，显示姓名后再次确认；运行中拒绝，取消/STOP不删除其他用户。

本次复用既有单段录入算法，不改评分模型、门限含义或声纹与空间方向的关联方式。

### SETTINGS

Next field 选择音量、窗口帧数、最少有效帧、声纹门限或 TTL；用 +/− 调整，再按 APPLY。
数值交给原程序校验和保存，在下一次 START 生效。`minimum` 不能大于 `window`。
切换用户后不要把原用户的门限自动沿用到新用户。现有已选择用户的设置在安装及开机时保留。

### DIAGNOSTICS 与关机

Read status 读取状态；Recheck 在错误解除且 STOP 读回正常后恢复待机，**不会自动开始跟随**。
触摸失效时立即请求停止；最多尝试 3 次初始化，恢复后仍需明确 Recheck 和 START。

SHUT DOWN → CONFIRM shutdown：先停止采集/推理并检查设备空闲，再停止显示 DMA，最后请求 Linux 关机。
STOP 未确认时不会请求关机；显示 DMA 不能停止时保留缓冲并阻止关机。关机命令被系统拒绝时尝试恢复错误界面。
关机时保持供电；屏幕熄灭后继续等约 15 秒，让 Linux 完成关机，再断电。
屏幕黑屏本身不是电源已经断开的反馈，PYNQ 仍需手动断开适配器。

## 导出操作记录

在屏幕STOP并退出会话后，可通过SSH/串口执行：

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-product.sh check
sudo sh soundsight-product.sh export
```

导出为logs/product-check.zip，包含启动/配置摘要及服务日志，不含声纹向量或录音。原生记录、人工测试表及屏幕照片分别见[统一资料](evidence/final-board-20261103/README.md)。

## 维护和回退入口

需要恢复手工启动时关闭下一次自动启动：

```sh
sudo python3 /boot/soundsight_screen_product_p1.zip --disable
```

它不会停止当前运行；仍可先在屏幕 STOP 后关机。之后手动方式仍为 `soundsight-3d.sh prepare`、
`soundsight-screen-i2c.sh apply`、`soundsight-panel.sh`。不能在自启面板仍运行时另开第二套面板或采集。

诊断命令（无硬件动作）：

```sh
sudo systemctl status soundsight-product.service --no-pager
sudo journalctl -u soundsight-product.service -b --no-pager -n 100
```

源码入口：`software/screen/product.py`、`backend.py`、`ui.py`；安装器 `tools/install_product.py`。
离线测试：`python -B software/tests/test_screen_product.py`。没有把模拟重启结果写成实际板测通过。
