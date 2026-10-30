# 三维测角＋异步声纹许可：板端操作

可选整轮统计：运行时加`--speaker-stats`，结束后用`sudo sh soundsight-3d.sh speaker-stats`查询。默认关闭，仅统计成功计算，见[统计与更新说明](pynq-speaker-statistics.md)。

新增板端单段短录入、多目标保存/切换：见[录入和评分操作说明](pynq-speaker-enrollment.md)。默认录3秒，支持2～10秒；录入不动舵机。当前板子用 `soundsight_enrollment_update.zip` 更新，完整SD包也已同步。

2026-10-30：最近算出的分数单独保留显示，不再被无分数的跳过任务覆盖。串口以`SCORE_AGE`、`SCORE_USABLE_AT_COMPLETION`和`SCORE_REASON`标明分数状态；当前转动许可单独看`PERMIT`和`PERMIT_REASON`。分数显示不代表允许转动；许可策略现已按下述score_ttl_v2更新。安装及字段说明见上面的录入和评分说明。

> 2026-10-29 W16新位流已收件并更新联合SD包。水平T15、垂直W16；安装及复测见 [W16更新说明](pynq-w16-update.md)。旧10月28日报告仅属旧候选。

本版沿用已经生成的 SoundSight_PS_3D 位流（由 Reliaze 复制），不需要重新综合、实现。新增的是 PYNQ 联合运行程序：一个进程管理 PCM DMA、三维快照和舵机提交，独立声纹进程计算分数。板上联合负载和识别效果仍需实测。

2026-10-30更新：采用`score_ttl_v2`，取消声纹源年龄、等待年龄、语音段变化和语音心跳年龄的许可检查。保留同一次采集会话关联、数值与时间格式校验、故障和STOP处理。旧本地配置自动按新策略读取，门限和TTL不变，模板不动。见[更新与安装](pynq-speaker-ttl-update.md)。

## 这次的行为

- `run`：只做三维测角；旧习惯 `run --axes ...` 会自动转到声纹约束的跟随入口。
- `speaker`：三维测角与声纹同时工作。默认轴关闭，只有显式 `--axes` 才请求跟随。
- 声纹跟随要求同时满足：用户开轴、当前方向合格、音量和空间筛选合格、声纹许可有效、机械范围及硬件保护通过。
- 首个有效语音开始积累模型所需的 1 秒窗口。推理完成即发布分数；计算期间只保留最新待处理窗口，不堆积旧任务。
- 许可从**计算完成**起默认有效 3 秒。下一次推理期间沿用未过期许可；只有新的过线结果刷新有效期；低分、无评分、静音、语音换段不提前撤销。到期、会话结束、真实采集/进程故障或STOP撤销。当前音量不足仍禁止动作，但不清除声纹许可。进程间传输延迟不会重新起算有效期。
- 试验门限为 0.65，可调；没有保存门限时只显示分数，不给转动许可。原 P02 模板仍标记 score-only，试验放行不等于识别已经标定通过。
- 手动标定仍独立，不要求声音或声纹。

这是“最近目标声纹通过，允许跟随当前声音”，并不证明当前方向与几秒前的声纹属于同一个人。初测请用单个主要说话人，再分别测本人、其他人及交替说话。

## 安装一次

把私下交付的 `soundsight_pynq_3d_speaker.zip` 放入 SD 卡 Windows 可见分区。保留 BOOT.BIN、boot.py、BOOT.SCR、IMAGE.UB、REVISION。该包带原登记模板，不上传公开仓库。

板端每行单独发送，串口选择换行：

```sh
python3 -m zipfile -e /boot/soundsight_pynq_3d_speaker.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
```

首次安装使用新的独立目录，不覆盖原声纹程序。若这个新目录已经存在，先保留备份再更新；不要覆盖正在运行的程序。ZIP 不含板上真实 P02 模板，也不含个人限位和许可配置。

从原声纹目录导入**已登记的真实模板和目标选择**。下面路径是之前标准目录；若 B 用了不同目录，换成实际目录：

```sh
sudo sh soundsight-3d.sh speaker-import /home/xilinx/SoundSight_PYNQ_Speaker_Live
sudo sh soundsight-3d.sh speaker-config 0.65 --ttl 3
sudo sh soundsight-3d.sh speaker-check
```

导入会先核对原模型／前端绑定，保留原目录；目标文件已有不同内容时停止，绝不覆盖。不会重新登记 P02。可兼带源目录中已有的 `settings.local.json`、`servo3d.local.json`；双轴标定若只在旧三维目录中，按原双轴说明重新填写这些已知值。不得把示例范围当成你的实测标定。

首次准备包括本机 ARM 求解库编译、离线检查，以及用户显式要求的 FPGA 加载与时钟准备：

```sh
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh status
```

若旧会话留有数据或异常，先查看并保留其日志，按原 `drain` 流程处理；不通过反复 prepare 清掉失败事实。

## 先只看角度和声纹

```sh
sudo sh soundsight-3d.sh level 7000
sudo sh soundsight-3d.sh filter 20 12
sudo sh soundsight-3d.sh speaker --seconds 30
```

7000 只是此前音量试验值，按现场调整。每 0.5 秒显示三维角度、音量、累计帧、声纹分数、门限、许可剩余时间和未动作原因，全部英文。`AXES=off` 时不会驱动舵机。

例如 `SPEAKER_SCORE=0.7200 THRESHOLD=0.65 PERMIT=1 REMAIN=2.50s` 表示试验分数通过、许可还剩 2.5 秒；轴仍关闭时照样不转动。`SPEAKER_SCORE=NONE` 表示尚无评分，不是 0 分。

持续运行直到 Ctrl+C：

```sh
sudo sh soundsight-3d.sh speaker
```

正常运行只保留固定统计、最近方向、最近 32 次声纹结果和必要故障状态；不连续存 PCM 或逐帧 SD 日志。停止并确认 DMA 停止后才保存一个 `logs/speaker-3d-*.json`。要保留逐帧定位调试记录，可有界运行：

```sh
sudo sh soundsight-3d.sh speaker --frames 1000 --debug
```

## 调整声纹门限与有效期

配置在下次会话生效，修改前 Ctrl+C 停止当前会话：

```sh
sudo sh soundsight-3d.sh speaker-config
sudo sh soundsight-3d.sh speaker-config 0.65 --ttl 3
sudo sh soundsight-3d.sh speaker-config 0.70
sudo sh soundsight-3d.sh speaker-config --ttl 2
sudo sh soundsight-3d.sh speaker-config --disable
```

最后一条清空门限，禁止声纹跟随许可，但仍可测角／打分。分数是余弦相似度，不是概率。先用同一位置、音量的目标本人和其他人分别测，再比较分数分布，不根据一个分数宣称识别准确率。

## 手动与跟随

先核实实际 CH0～CH3、水平和垂直的零位／方向／限位。手动命令不要求声音：

```sh
sudo sh soundsight-3d.sh manual --horizontal 185 --seconds 3
sudo sh soundsight-3d.sh manual --vertical 115 --seconds 3
```

185 和 115 只是命令格式示例，必须在你的实测限位内。完成标定、角度与评分验证之后，显式选择声纹约束的轴：

```sh
sudo sh soundsight-3d.sh speaker --axes horizontal
sudo sh soundsight-3d.sh speaker --axes vertical
sudo sh soundsight-3d.sh speaker --axes both
```

各模式之间先 Ctrl+C，确认 `SPEAKER_3D_STOPPED` 无清理错误，再运行下一条。T15 水平、W16 垂直，PL 的限位、完整 PWM 排尾和 750ms 租约不变。旧习惯 `run --axes ...` 也会进入声纹许可模式；建议统一使用上面的 `speaker --axes ...` 命令。

## 以后每次开机

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh speaker
```

不会自动启动转台。许可配置、目标和限位保存在本地，下次开机沿用；会话许可本身不会保存或恢复。
