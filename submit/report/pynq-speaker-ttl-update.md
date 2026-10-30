# 声纹通过后按有效期续期：score_ttl_v2

可选整轮统计：运行时加`--speaker-stats`，结束后用`sudo sh soundsight-3d.sh speaker-stats`查询。默认关闭，仅统计成功计算，见[统计与更新说明](pynq-speaker-statistics.md)。

本次只更新PS软件；不改RTL、BD、bit/HWH，不需要运行Vivado或重新录入用户。

## 当前规则

- 同一次运行中，每个有效声纹分数大于或等于门限，就把到期时间设为“该次计算完成时间＋TTL”。例如TTL=10秒，10:00:00通过、10:00:07再次通过，则有效至10:00:17。
- 推理开始前的等待时间、输入声音年龄、计算期间的语音段变化不再使结果作废。推理期间仍只保留一个最新待处理窗口，不无限积压。
- 低分、无评分、停顿、静音或新语音段不缩短已有许可，也不延长它。直到TTL到期仍没有新的通过结果，许可关闭；之后再通过可重新取得许可。
- 起算点是计算完成，而不是消息被主进程收到；重复消息不刷新。新的会话不继承旧许可，停止、真实采集/进程故障会撤销，未配置门限不给许可。模型输入/数值校验继续保留。
- 声纹许可与方向控制独立。即使PERMIT=1，当前音量不足、方向不合格、角度过期或超机械限位也不能提交转动。水平T15、垂直W16不变。
- 该模式允许“刚才目标人的声纹通过后，在有效期内跟随当前声音”；当前声音可能来自其他人。声纹分数展示可以低于门限而PERMIT仍为1，表示上一次通过尚未到期。

## 更新已有板端目录

先Ctrl+C停止运行并等待退出。把新的完整`soundsight_pynq_3d_speaker.zip`复制到SD卡Windows可见分区，覆盖同名旧包；保留启动文件。板端执行：

```sh
python3 -c "from pathlib import Path; import shutil,time; p=Path('/home/xilinx/SoundSight_PYNQ_3D_Speaker'); q=p.with_name(p.name+'_backup_ttl_'+str(time.time_ns())); shutil.copytree(p,q); print('BACKUP=',q)"
python3 -m zipfile -e /boot/soundsight_pynq_3d_speaker.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -B software/tests/test_speaker_follow.py
python3 -B software/tests/test_speaker_display.py
sudo sh soundsight-3d.sh speaker-check
```

若已有目录由root创建导致备份或解压权限不足，上面备份、解压命令前加sudo。包不含`*.local.json`、`speaker-profiles/`和个人日志，不覆盖已录入的toph/user2、门限、TTL和舵机限位。旧`delayed_permission_v1`配置兼容读取为`score_ttl_v2`，不改变门限和TTL；下次配置写入保存新策略名。

若使用小型`soundsight_enrollment_update.zip`而非完整包，则执行以下两条替代完整包解压，其他检查相同，不需两个包都装：

```sh
python3 -m zipfile -e /boot/soundsight_enrollment_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_enrollment_update/install.py --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
```

本次位流未变；同一开机中已经prepare的板子不必重新prepare。若断电换卡并重新启动，执行：

```sh
sudo sh soundsight-3d.sh prepare
```

## 配置与测试

查看`speaker-check`中的target_id是否为所选的人、policy是否为`score_ttl_v2`。沿用当前门限0.45、TTL10秒时：

```sh
sudo sh soundsight-3d.sh speaker-config 0.45 --ttl 10
sudo sh soundsight-3d.sh speaker --axes both --seconds 30
```

过线后应看到`PERMIT=1`、`REMAIN`倒计时；每个新通过结果刷新倒计时。低分或语音段改变不应马上清零。没有新通过超过TTL才变为`PERMIT=0`。`POLICY=score_ttl_v2`是新版串口标识。许可不等于实际提交转动，仍看有效方向和MOTION。

持续运行直到Ctrl+C：

```sh
sudo sh soundsight-3d.sh speaker --axes both --seconds 0
```

仅评分不转动使用`--axes off`。若启动提示OLD_FRAMES，先执行`sudo sh soundsight-3d.sh drain`保存并释放旧帧，正常完成再启动，不反复prepare清除证据。

0.45仍是试验门限，未完成本人和他人的对照标定。离线回归与包验证见`document/evidence/speaker-ttl-20261030/`；真实板端新版跟随尚待复测。
