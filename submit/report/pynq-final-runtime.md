# 联合运行包：三维、声纹、双轴和触屏

版本：`S2_S3_CF1A_NO_DAS_20261102`。本次是接近最终版本的**程序整合包**，没有更换算法、放宽门限。不是全功能整机验收证书。

## 包含什么

- CF1A四麦三维定位、音量门限、多帧空间筛选及3°死区。
- CP1/VF1声纹、单段录入、保存和切换目标、评分显示、可选累计统计、score_ttl_v2许可。
- 双轴手动标定、显式纯声音跟随、显式声纹双轴跟随；默认不开轴。
- S2匹配bit/HWH、PS I2C0 EMIO触摸驱动、S3 RGB触屏控制面板。
- ARM声纹后端、模型和许可证、C求解器源码/构建入口、离线测试与使用说明。

不包含旧Vivado工程、XSA、启动镜像或SD卡系统。当前硬件是主线已归档S2：水平 **J3-2/M15**、垂直 **J3-3/J14**。不是早期T15/W16版。安装不会加载位流或驱动舵机。

包含原有私人基础声纹模板，因此仍是私人交付包，不直接提交公共GitHub。新的录入用户、已选目标、门限和机械标定不预填。原始模型/后端保持原字节，原有第三方许可随包携带。

## 更新现有板端：不用手工解压覆盖

1. 将`soundsight_pynq_3d_speaker.zip`复制到SD启动分区，或通过已配置的USB网络上传到板端。
2. 先Ctrl+C退出运行、退出屏幕面板，等命令提示符回来。不要在采集或屏幕运行中安装。
3. SD路径执行下面一条；USB上传则将ZIP路径换为实际上传位置：

```sh
sudo python3 /boot/soundsight_pynq_3d_speaker.zip
```

默认更新`/home/xilinx/SoundSight_PYNQ_3D_Speaker`。也可指定`--destination /home/xilinx/SoundSight_PYNQ_3D_Speaker`。

安装先核包内完整性和板端bit/HWH。若出现`HARDWARE_MISMATCH`，说明板端配套硬件与此S2不同，程序不会替换它；保留输出核对，不绕过检查。本包不覆盖更新的B侧未知硬件。

已有匹配S2目录只更新包内文件，备份放在该目录的`backup_runtime_*`；原`*.local.json`、`speaker-profiles`、日志和旧安装回执保留。私人基础模型若有独立修改会拒绝覆盖。安装器只更新包内文件，不扫描删除用户自行添加的目录。

成功输出`RUNTIME_INSTALLED=...`。如果其中`reboot_required=true`，先执行`sudo reboot`，重启登录后继续；若为false，无需为安装额外重启。不要手工伪造SCREEN-INSTALL.json。新空目录可以完整安装，但没有用户参数，需自行配置并录入/导入真实目标。

## 每次开机

沿用已验证的12V适配器供电；串口或USB线用于调试，不恢复此前仅靠电脑串口供电的接法。

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh status
```

prepare会编译本机ARM求解器、执行已有离线检查，随后加载配套位流和设置时钟。只在开机准备且没有其他运行会话时执行。新包PC检查不替代此步骤，也不替代实板验证。

需要触屏时接着运行：

```sh
sudo sh soundsight-screen-i2c.sh apply
sudo sh soundsight-panel.sh
```

在面板选择SOUND或SPEAKER、选择轴，再按START；按STOP结束。面板启动本身不开轴。终端和面板二选一作为运行控制者，不同时启动两套采集。声纹录入仍使用下面的终端命令，录入前退出面板。USB网络使用现有已安装配置，本包不重新配置网卡/服务。

## 查看和调整配置

```sh
sudo sh soundsight-3d.sh level
sudo sh soundsight-3d.sh filter
sudo sh soundsight-3d.sh servo-config horizontal
sudo sh soundsight-3d.sh servo-config vertical
sudo sh soundsight-3d.sh servo-geometry
sudo sh soundsight-3d.sh speaker-list
sudo sh soundsight-3d.sh speaker-check
```

以下是格式示例，不是替你标定出的新参数。升级会保留板上当前值；只有确实要修改才执行：

```sh
sudo sh soundsight-3d.sh level 12500
sudo sh soundsight-3d.sh filter 3 1
sudo sh soundsight-3d.sh speaker-config 0.45 --ttl 10
```

`filter 3 1`表示每组3帧、至少1帧有效；仍须通过现有空间一致性等判据。声纹0.45/TTL10是既有试验设置，不是通用阈值或身份识别率保证。机械配置格式是`servo-config AXIS FRONT DIRECTION MIN MAX`，必须按实际机构填写，不能把舵机标称最大范围当成安装后可安全全行程。

## 从无动作到联合跟随

只测三维，不转动（Ctrl+C结束）：

```sh
sudo sh soundsight-3d.sh run --axes off --frames 0
```

只测声纹评分与三维，先运行30秒，不转动：

```sh
sudo sh soundsight-3d.sh speaker --axes off --seconds 30 --speaker-stats
```

声纹许可联合双轴，持续到Ctrl+C：

```sh
sudo sh soundsight-3d.sh speaker --axes both --frames 0 --speaker-stats
```

明确不要求声纹的纯声音双轴：

```sh
sudo sh soundsight-3d.sh follow-sound --axes both --frames 0
```

声纹未选目标或门限未配置时不会凭空授予许可。每次过线评分从完成时刷新TTL；低分/等待期间旧许可按原TTL保留，方向/音量/故障/停止保护仍独立。该机制没有把声纹身份与空间声源严格绑定，不承诺两人同时讲话时只追踪登记人。

## 手动标定与新用户

手动命令不需要声音，角度必须在现有限位内；以下是示例，确认机构可到达后才运行：

```sh
sudo sh soundsight-3d.sh manual --horizontal 180 --seconds 3
sudo sh soundsight-3d.sh manual --vertical 110 --seconds 3
```

新增用户（录入时不开轴）：

```sh
sudo sh soundsight-3d.sh speaker-enroll user2 --seconds 5
sudo sh soundsight-3d.sh speaker-list
sudo sh soundsight-3d.sh speaker-select user2
sudo sh soundsight-3d.sh speaker --axes off --seconds 30 --speaker-stats
```

看到RECORD_NOW后再连续说话。选择新用户会清除旧声纹门限；先比较本人/其他人的评分，再用`speaker-config SCORE --ttl SECONDS`配置试验门限，然后开启联合跟随。不要重复覆盖已有用户ID。

## 日志、故障与验证范围

普通运行保留有界统计，结束后写到`logs`，不逐帧无限写SD；`--speaker-stats`统计成功计算次数、过线次数及平均/最大计算耗时。查看上一轮累计统计：

```sh
sudo sh soundsight-3d.sh speaker-stats
```

异常退出先保留SUMMARY和status；需要保存残留快照时执行`sudo sh soundsight-3d.sh drain`，不要先prepare覆盖现场。STOP后的0x40与运行中故障分开判断。

本次打包复用已有S2/S3/CF1A和声纹成果，未运行Vivado、下载或板测。已有CF1A长稳归档中的定量摘要为30.016秒，用户另回报几分钟连续跟随；两者未直接关联，不能写成已验证全部联合长稳。触屏、声纹、双轴同时运行的稳定性仍应由这一完整组合的板端结果确认。

## 维护者重新打包

在仓库根目录，用含原始私人模型资产的旧完整包作为输入；输入输出不要指向同一个文件：

```sh
python -B tools/package_current_runtime.py --private-assets-from PRIVATE_ORIGINAL.zip --output release/output/soundsight_pynq_3d_speaker.zip
python -B tools/check_current_runtime_package.py --package release/output/soundsight_pynq_3d_speaker.zip --output simulation/work/runtime-check --cc gcc
```

检查输出目录须不存在。工具从当前源码、S2匹配硬件和指定私人模型组成包；不会借用旧包的应用代码。PC检查会编译主机C库并使用合成输入、模拟重启ID，不执行ARM推理或板端操作。首次启动仍须使用上文prepare。
