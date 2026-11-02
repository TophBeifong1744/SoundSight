# 三维 CF1A 软件更新与一轮确认

本包修复已安装 CF1 的计算开销及定位快照跳过后反复清历史问题。保留原 CF1 工程和更新包；此次只安装 `soundsight_three_d_coherent_cf1a.zip` 即可，不用重装 CF1。尚未安装 CF1 的目录会被版本检查拒绝。

## 已确认的问题

CF1 两轮30秒实板采集各收到2811个完整PCM包，没有音频错误或拒收；定位快照分别跳过452、441个，频谱历史被清除453、442次，最终滤波输出仅0、4组。第二轮结束drops为894，是累计值（包含结束尾部一次），不是该轮丢了894个PCM包。会话PASS表示正常结束，并不表示跟随效果合格。

原最大前端解算耗时约13.4ms，超过512/48000=10.67ms的源窗口周期，整帧服务还需其他时间。此次在频谱历史中只保留使用的79个频点，以滚动累加替代每帧重复堆叠16份全频谱；每256窗口重新求和，限制浮点累积漂移。若PCM完整而PL快照跳过，使用已缓存的过去PCM补齐历史，单次最多16窗。缺失、削顶、陈旧音频仍拒绝，重复和倒序窗口也拒绝。

不改变位流、舵机引脚、S2触摸驱动、S3面板、用户声纹、机械限位、音量门限和滤波设置。原C几何门限、硬件动作门禁、下游空间滤波断帧重置和score_ttl_v2保持。只补算已有音频，不补造PL帧或运动命令。

## 本机验证结果与限制

- 五段既有录音：4598个完整窗口与已交付CF1分类及有效方向向量一致；每6窗跳过1个定位快照但保留PCM的3833个比较窗口也一致。覆盖超过256窗的重新求和点。
- 受影响的三维、普通跟随、声纹接合、显示及CF1A边界测试共74项通过。
- Windows电脑同录音前端计算、四轮交替顺序比较：1022窗总耗时中位数CF1为0.2719秒、CF1A为0.1482秒，下降45.5%。这是PC前端证据，不包含DMA、声纹并发或集中补算负载，不可换算为PYNQ实时性能。
- 安装器测试检查重复安装、私有数据保留、原CF1记录保留、未知改动拒绝、11个替换位置故障回退及显式回退到CF1。

本轮仍以方向能够有效输出为目标，不声称精确角度、连续跟随、声纹联合、屏幕并发或长稳已验收。板子可保持关机，方便时再做下述一轮确认；不需要重录整套声学实验。

## 安装

停止并退出面板/采集程序后，将ZIP放到SD启动分区。以下每条命令整行复制，不拆行。

```bash
sudo python3 /boot/soundsight_three_d_coherent_cf1a.zip
```

预期 `THREE_D_CF1A_INSTALLED=1`，同时显示准确BACKUP_DIR。安装不会访问硬件，不要求额外重启；拔卡后重新开机仍需prepare。遇到未知文件版本会停止，不覆盖本地修改。

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
```

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh check
```

本次开机尚未prepare时执行：

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh prepare
```

## 一次30秒自动停止的普通声音双轴测试

使用原来已经测试的轴配置，讲话或播放连续声音，在阵列前方缓慢改变方向；不用做精确角度标定。不要同时开屏幕或另一个采集程序。只观察角度时可把both换为off。

```bash
sudo env PYTHONUNBUFFERED=1 PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh follow-sound --axes both --seconds 30
```

应显示 `THREE_D_FRONTEND=CF1A`、`SPEAKER=DISABLED`，随后有方向输出；30秒后自动结束并打印 `THREE_D_STOPPED SUMMARY=...`。需要提前停止可发送Ctrl+C，串口HEX为03。

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh status
```

把串口全文及SUMMARY对应JSON交回分析。JSON可用 `sudo cat` 加本次实际SUMMARY路径读取，不要照抄上次路径。需要核对：

- 新版标记、实际音量/滤波配置，以及采集是否完整、有无新增故障。
- `direction_frontend`统计里的解算最大/平均耗时、快照跳过、历史重置和补算数。
- 原生三维汇总的有效方向、最终滤波输出和动作提交，结合实际观察，不能仅凭PASS宣布可用。
- 结束时DMA停止、音频空闲、清理无错误及动作停止。比较drops必须扣除本轮起始累计值，区分定位快照与PCM。

如果仍然大面积无有效输出，保留本轮日志分析，不降低物理门限或反复prepare清现场。此次CF1A的PYNQ实际性能尚未测量。

## 屏幕与声纹入口

原S3面板的普通/声纹START自动使用CF1A，无需新屏幕包。新开机且触摸I2C未启用时，用已有命令：

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen-i2c.sh apply
```

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-panel.sh
```

屏幕与声纹联合运行不是这次首轮必测项，也未因此被宣布通过。

## 回退

先退出面板及采集。用安装显示的真实BACKUP_DIR替换下列占位路径，恢复准确CF1软件及SCREEN-INSTALL记录；原THREE-D-CF1-INSTALL.json始终保留。

```bash
sudo python3 /boot/soundsight_three_d_coherent_cf1a.zip --restore /home/xilinx/SoundSight_PYNQ_3D_Speaker/backup_three_d_cf1a_实际后缀
```

不要直接输入“实际后缀”。如果安装后文件又被修改，回退会拒绝覆盖，先保留现场。软件回退不改机械/声纹资料或硬件。
