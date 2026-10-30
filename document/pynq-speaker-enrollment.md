# 板端录入、切换目标人与声纹双轴跟随

可选整轮统计：运行时加`--speaker-stats`，结束后用`sudo sh soundsight-3d.sh speaker-stats`查询。默认关闭，仅统计成功计算，见[统计与更新说明](pynq-speaker-statistics.md)。

当前声纹许可已更新为**score_ttl_v2**：过线刷新有效期，低分和静音不提前清除；旧语音段结果仍可评分授权，当前方向的音量筛选独立生效。以下历史语音段作废示例仅解释旧日志。安装见[TTL更新说明](pynq-speaker-ttl-update.md)。

现在可以直接在板上录入：**只录一段，默认3秒，可改成2～10秒。** 不用电脑预录或重做Vivado。录入时双轴撤输出，采集停止并确认DMA停止后才计算模板；不会自动开启跟随，也不会自动替换当前目标。

## 安装这次的软件更新

将 `soundsight_enrollment_update.zip` 复制到SD卡的Windows可见分区。停止正在运行的程序（Ctrl+C并等待停止结果），插回板子、进入Linux后：

```sh
sudo python3 -m zipfile -e /boot/soundsight_enrollment_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_enrollment_update/install.py --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -B software/tests/test_speaker_enrollment.py -v
sudo sh soundsight-3d.sh prepare
```

测试应显示 `OK`。安装器备份被替换的程序，保留现有P01/P02、新用户档案、目标选择、音量门限、双轴限位及旧日志。更新包不含bit/HWH，不用改Vivado；完整 `soundsight_pynq_3d_speaker.zip` 也已同步，用于完整安装。现有板子用小更新包即可。`prepare` 是用户显式执行的硬件准备；安装和离线测试本身不下载位流。

## 录入一个人

先停止其他采集/跟随程序，然后：

```sh
sudo sh soundsight-3d.sh speaker-enroll toph
```

看到倒计时，等 `RECORD_NOW` 后，用正常音量连续说一句话，例如“我是拓芙，现在录入我的声音”。保持说话直到 `RECORDING_DONE`，随后等待 `ENROLLED=toph`。录音约3秒，加载模型和计算模板另外需要时间，不表示整条命令3秒结束。仅目标本人说话，避免音响同时播放人声。

更短或稍长的单段录入：

```sh
sudo sh soundsight-3d.sh speaker-enroll alice --seconds 2
sudo sh soundsight-3d.sh speaker-enroll bob --seconds 5
```

名字用英文字母开头，后接字母、数字、`_`或`-`，最长32个字符。已有名字不会覆盖，包括大小写相同的名字；想重录用 `toph_v2`，确认后切换。P01、P02及旧P02目录保留。

系统使用CH0的语音，要求至少有一个可用的1秒语音窗；不是录满3秒就一定合格。静音、语音不足、明显削顶、采集错误会拒绝保存新档案，原档案和目标不变。若2秒录入提示 `NOT_ENOUGH_SPEECH`，下一次改3秒或5秒，依然只录一段。不要通过调低声音跟随的音量门限来绕过录入质量检查。

## 查看、选择目标

```sh
sudo sh soundsight-3d.sh speaker-list
sudo sh soundsight-3d.sh speaker-select toph
sudo sh soundsight-3d.sh speaker-check
```

录入只新增档案，`speaker-select`才切换当前人。选择后会显示 `THRESHOLD_CLEARED=1`：清除上一人的许可门限，防止把旧门限直接用于新人。即使重新选择同一个人，也需重新设置门限。目标档案持久保存，重启不用重录；当前会话的临时通过令牌不保存。

## 先只测试评分，不转动

2026-10-30：评分展示已与转动许可分开。现有板子仍使用本页的
`soundsight_enrollment_update.zip` 增量安装步骤，保留个人模板、门限和限位。
安装后另运行 `python3 -B software/tests/test_speaker_display.py -v`，应为7项通过。
无需重做Vivado或更新位流；重启后按原步骤prepare。

串口示例：

```text
SPEAKER_SCORE=0.5018 SCORE_STATE=LAST_COMPLETED SCORE_AGE=1.20s SCORE_USABLE_AT_COMPLETION=0 SCORE_REASON=SPEECH_STATE_CHANGED THRESHOLD=None PERMIT=0 REMAIN=0.00s PERMIT_REASON=STALE_BEFORE_START
```

- `SPEAKER_SCORE`保留本会话最近一次算出的有限分数，包括不能用于许可的结果。无分数的跳过任务不再清掉它。
- `SCORE_AGE`是该分数计算完成至今的时间；`LAST_COMPLETED`表示历史计算结果，不表示当前声音刚刚通过。
- `SCORE_USABLE_AT_COMPLETION`和`SCORE_REASON`说明推理结束时是否可用；即使当时可用，当前许可也可能已过期；score_ttl_v2下静音不提前撤销未过期许可。
- `PERMIT`、`REMAIN`、`PERMIT_REASON`才是当前声纹许可状态。许可通过仍须有效角度、限位及用户显式开轴才能转动。
- 新会话没有算出分数时仍显示`NONE`。保存摘要增加`display_result`诊断字段，最近一次任务及原许可字段保留。

当前显示与许可独立；TTL可调。下面旧日志中的语音段作废状态不代表当前score_ttl_v2规则。

```sh
sudo sh soundsight-3d.sh speaker --axes off --seconds 30
```

先由目标本人正常说话，停止后再让其他人说话，各测一次。串口显示 `SPEAKER_SCORE`，结束摘要保存在 `logs/speaker-3d-*.json`，含最近最多32次声纹结果。分数是余弦相似度，不是百分比；`NONE`代表没有可用评分，`UNCONFIGURED`代表还未设置许可门限，这两者不等于0分。`profile_score_only=true`、`recognition_qualified=false`表示尚未完成识别效果标定，不妨碍无动作评分测试。

短录入只是快速建模板，不保证身份识别精度。对比本人/其他人、多次和不同说话内容的分数，若两者明显重叠，先改善录音、距离或重新录入，不能仅靠降低门限声称识别有效。初步0.65是试验值，并非每个人通用的合格线。本批历史PCM的两个3秒片段间得到约0.547的相似度，也说明不能把0.65当成必过门限或识别准确率。

## 设置门限，再开启声纹双轴跟随

先确认测角、限位和评分符合预期，停止上一条测试后：

```sh
sudo sh soundsight-3d.sh speaker-config 0.65 --ttl 3
sudo sh soundsight-3d.sh speaker-check
sudo sh soundsight-3d.sh speaker --axes both
```

最后一条持续运行到Ctrl+C。同时满足有效声音方向、音量/多帧筛选、声纹许可和机械限位才允许转动。下一轮声纹计算保留未过期许可；低分和静音不提前撤销；采集/处理故障、STOP或有效期到期撤销。水平T15、垂直W16不变。`follow-sound`是另外的纯声源模式，没有声纹限制；需要身份判断时使用这里的 `speaker`。

常用修改（都在停止会话后执行，下次运行生效）：

```sh
sudo sh soundsight-3d.sh level 7000
sudo sh soundsight-3d.sh filter 20 12
sudo sh soundsight-3d.sh speaker-config 0.70
sudo sh soundsight-3d.sh speaker-config --ttl 3
sudo sh soundsight-3d.sh speaker-config --disable
```

这些数值都是可调示例，保留你的现场设定即可。`--disable`撤掉声纹许可门限；不开轴的评分仍可运行。

## 以后开机和换人

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh speaker-check
sudo sh soundsight-3d.sh speaker --axes both
```

不换目标且门限已设好，重启不需要重复 `speaker-select`。要换人则先Ctrl+C，再 `speaker-select 名字`、评分、配置门限、启动跟随。

## 保存位置与未测范围

- `speaker-profiles/名字/profile.json`：私有模板、模型来源和录入质量信息。
- `speaker-target.local.json`：当前选择；`speaker-follow.local.json`：当前试验门限和令牌有效期。
- `logs/pcm-*/`：每次有限录入的原始PCM、四通道WAV、采集结果和临时提取向量，失败记录也保留。这些是私有语音资料，不上传公开GitHub；不会在正常跟随时持续增长录音。
- 安装器打印的 `backup_3d_*`：本次替换程序的备份，不包含被清除的个人资料。

本批完成离线故障测试、真实CP1/VF1主机回放及包检查。用户随后已完成5秒单段实麦录入和本人关轴评分；3秒那次因语音窗不足被拒绝，失败原件保留。其他人对照、重复评分分布和声纹联合双轴效果仍待验证，详见[板测回报](evidence/speaker-enrollment-20261029/board-result.md)。没有代用户上板或驱动舵机。
