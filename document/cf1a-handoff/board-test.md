# A执行：CF1A安装与30秒三维测试

每条命令整行输入。使用板端Bash串口，在同一登录会话执行，以保留日志目录变量。先停止并退出屏幕及其他采集程序；不要同时运行另一采集入口。

## 1. 留出本轮日志目录

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
```

```bash
A_CF1A_LOGDIR=$(mktemp -d /home/xilinx/a-cf1a-XXXXXX)
```

```bash
echo "$A_CF1A_LOGDIR"
```

记下输出。若串口重新登录，先用 `A_CF1A_LOGDIR=/home/xilinx/a-cf1a-实际后缀` 重新设置为刚才真实路径（以输出为准，不照抄示例）。

```bash
pgrep -af '[b]oard_3d.py|[r]un_pcm.py|[r]un_buffered.py|[s]peaker_process.py|[p]ipeline_backend|[s]oftware/screen/ui.py'
```

若有运行进程，通过原界面STOP/EXIT或Ctrl+C（串口HEX 03）结束，再继续。不要随意kill后假设硬件已停止。

## 2. 安装

内层更新ZIP已在/boot后，核对文件：

```bash
sha256sum /boot/soundsight_three_d_coherent_cf1a.zip | tee "$A_CF1A_LOGDIR/package-sha256.txt"
```

应为 `5649788d4962df613f25e8060c31a4a8ea9f6543e01355ce667fcf70db2f6698`。

```bash
sudo python3 /boot/soundsight_three_d_coherent_cf1a.zip 2>&1 | tee "$A_CF1A_LOGDIR/install.log"
```

紧接着执行（中间不要插入其他命令）：

```bash
echo INSTALL_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/install-exit.txt"
```

预期退出0，`THREE_D_CF1A_INSTALLED=1`或`ALREADY_INSTALLED=1`。记录BACKUP_DIR。若拒绝未知版本，停止本流程并返回install.log，按交接说明核对A新改动；不要强制覆盖。

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh check 2>&1 | tee "$A_CF1A_LOGDIR/check.log"
```

```bash
echo CHECK_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/check-exit.txt"
```

检查通过再继续。更新本身不要求额外重启；本次开机尚未prepare时执行：

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh prepare 2>&1 | tee "$A_CF1A_LOGDIR/prepare.log"
```

```bash
echo PREPARE_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/prepare-exit.txt"
```

若本次开机已经prepare成功，可跳过这两条并在回传模板说明。

## 3. 保存当前轴配置、版本和运行前状态

```bash
sudo sh soundsight-3d.sh servo-config horizontal 2>&1 | tee "$A_CF1A_LOGDIR/horizontal.log"
```

```bash
sudo sh soundsight-3d.sh servo-config vertical 2>&1 | tee "$A_CF1A_LOGDIR/vertical.log"
```

只读取，不改值。两轴须使用这套机构已经验证的配置；配置为空、机构/接线已变或限位未确认时先不要开both，可用off观察方向并注明机械测试未完成，不能填示例限位冒充标定。

```bash
sha256sum soundsight.bit soundsight.hwh software/tetra3d/linux/coherent_frontend.py software/tetra3d/linux/board_3d.py software/tetra3d/linux/speaker_runtime_3d.py | tee "$A_CF1A_LOGDIR/runtime-sha256.txt"
```

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh status 2>&1 | tee "$A_CF1A_LOGDIR/status-before.log"
```

```bash
echo STATUS_BEFORE_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/status-before-exit.txt"
```

若NOT_PREPARED先正确prepare；若其他异常，保存状态并处理，不能跳过检查直接开轴。

## 4. 一轮30秒普通声音双轴

阵列仍为40mm正四面体。建议约1米、无遮挡，以正常音量讲话或持续播放声音。最初数秒在前方保持位置，随后缓慢左右移动声源，后段在机构已验证范围内稍改变高度。记录实际距离/高度/移动情况；无需精确测角或绕完整一圈。不要同时多个人讲话。声源何时开始以实际运行输出为准，不依赖启动前计时。

```bash
sudo env PYTHONUNBUFFERED=1 PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh follow-sound --axes both --seconds 30 2>&1 | tee "$A_CF1A_LOGDIR/run.log"
```

```bash
echo RUN_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/run-exit.txt"
```

预期标记 `THREE_D_FRONTEND=CF1A`、`SPEAKER=DISABLED`。30秒自动停止；如需提前停止，Ctrl+C/HEX 03。保持原音量和滤波配置，不追加降低门限参数。若本轮改用off，注明原因和未测双轴。

看角度是否出现并更新、两轴是否向声源方向运动、有无长时间不动/反向/抖动。命令结束不等于机械到位。保存末尾 `THREE_D_STOPPED SUMMARY=...` 的真实路径。

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh status 2>&1 | tee "$A_CF1A_LOGDIR/status-after.log"
```

```bash
echo STATUS_AFTER_EXIT=${PIPESTATUS[0]} | tee "$A_CF1A_LOGDIR/status-after-exit.txt"
```

若出现错误仍保留日志和结束状态，不连续重跑或清掉现场。无SUMMARY时也返回现有日志，不需要为了凑齐文件重新运行。

## 5. 导出并交回用户

从本轮run.log末尾复制真实SUMMARY路径。下面一行必须替换为**本次**文件在工程目录下的相对路径：

```bash
A_CF1A_SUMMARY=logs/three-d-本次真实文件名.json
```

```bash
sudo ls -lh "$A_CF1A_SUMMARY"
```

```bash
sudo cat "$A_CF1A_SUMMARY" | tee "$A_CF1A_LOGDIR/summary-copy.json"
```

以下命令包含本次日志、原生SUMMARY及安装身份。输出文件名使用随机日志目录后缀，避免不同测试相互覆盖：

```bash
A_CF1A_RETURN=/boot/soundsight-$(basename "$A_CF1A_LOGDIR")-return.tar.gz
```

```bash
sudo tar -czf "$A_CF1A_RETURN" -C /home/xilinx "$(basename "$A_CF1A_LOGDIR")" -C /home/xilinx/SoundSight_PYNQ_3D_Speaker "$A_CF1A_SUMMARY" THREE-D-CF1A-INSTALL.json SCREEN-INSTALL.json
```

```bash
sudo tar -tzf "$A_CF1A_RETURN"
```

```bash
sudo ls -lh "$A_CF1A_RETURN"
```

```bash
sync
```

如果安装失败或没有SUMMARY，改用下面这条导出已存在的日志即可（先按上面设置A_CF1A_RETURN）：

```bash
sudo tar -czf "$A_CF1A_RETURN" -C /home/xilinx "$(basename "$A_CF1A_LOGDIR")"
```

导出后按原方法正常关机再取SD。将生成的tar.gz和填写好的 `测试结果回传模板.md` 一起给用户。模板可在电脑填写，视频也可单独发送；无需打包全部logs、声纹模板或原始录音。若你随后添加新功能，这份原样CF1A结果须单独保留。
