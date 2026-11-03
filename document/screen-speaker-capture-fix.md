# 屏幕声纹联合采集修复候选：CAPTURE_COOPERATIVE_V1

本次修改 PS/PYNQ 程序和屏幕恢复入口，不需要重新生成位流。目标是解决屏幕 SPEAKER + 双轴运行中音频采集溢出后停止，以及恢复入口不能处理残留采集队列的问题。板上是否完全解决，需要按下列步骤复测；离线通过不能替代板测。

## 已知故障与判断边界

交接材料引用的失败会话接收 277 个 PCM 包，硬件发布 282 个，audio.errors=1、rejected=1；第一故障时 PS fault=0，STOP 后才出现 0x40。声纹 IPC highwater=3/32，尚未生成评分。本次是采集失败，不是低声纹分数，也没有证据表明是电源重启。

audio.errors 的 bit0 表示数据 FIFO 或描述符队列满，单凭该位不能区分两者。29.29 ms 的最大服务间隔提示接收延迟，但不能单凭一次最大值确定所有根因。原程序已在计算前重挂 DMA；不足在于收包和 CF1A 计算仍在同一进程，历史窗口补算期间没有收包检查点。屏幕、声纹计算、Linux 调度的实际贡献仍须在板上测量。

## 修改内容

- 每次主循环最多连续处理 4 个已完成 DMA 包；CF1A 每个历史窗口计算前及末尾也检查收包、停止和故障，避免整组历史补算期间无人接收。
- 每个包仍先复制、重挂 DMA，再校验序号与格式，交给定位和声纹。没有静默丢弃音频，没有增加无界队列，没有降低声纹、方向、音量、限位、许可超时等门限。
- 当前求解最多固定引用 17 个不可变 PCM 块，避免合作收包淘汰环形缓冲后改变同帧输入。谱运算顺序、1024 点窗口、16 窗历史、三维几何及声纹 TTL 策略不变。
- 日志增加 `capture_service`：检查点最大间隔、补收包数、解码/PCM 入队/声纹提交/许可轮询/显示耗时；增加当前 `capture_scheduling`。只保存有界统计，运行中不逐帧写盘。
- 增加 `recover-capture`：独占原设备锁，撤销轴和停止采集源，持久保存故障现场、保存旧定位帧后才 CONSUME，明确丢弃已失败会话的残留音频，复位音频 DMA，用新 epoch 在采集源停止时清除音频错误，再立即 STOP。核对空队列、轴关闭、音频 idle、DMA halted 后才报告成功。不会启动音频源或轴，不继承旧声纹许可。
- `status` 增加音频/DMA 状态；屏幕故障态的 DIAGNOSTICS 提供 **Recover capture → CONFIRM recovery**。恢复不是启动，成功后仍需重新选轴并按 START。原 Recheck 保留配置/触摸故障检查语义。
- 不自动清除除 STOP 取消位以外的 PS 故障；保存失败、复位失败、未确认停止均保持阻止重启。

## 安装

使用 WinSCP 将 `soundsight_screen_speaker_fix.zip` 放到板子的 `/home/xilinx/`。无需解压覆盖，不替换 BOOT.BIN、IMAGE.UB 或位流。

先在屏幕按 STOP，等待运行退出，再在串口执行：

```sh
sudo systemctl stop soundsight-product.service
sudo python3 /home/xilinx/soundsight_screen_speaker_fix.zip --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh check
python3 -B software/tetra3d/tests/test_capture_recovery.py
```

安装器验证已知 P1/S2/S3 与 CF1A 基线、备份旧文件、更新安装回执，不改声纹档案、录音、门限、标定与日志，不自动启动屏幕或运动。若出现 `BASELINE_MISMATCH` 或 `LOCAL_CHANGE_PRESERVED`，保留输出，不强行复制绕过；应对照板端实际文件合并。

已有采集故障时先执行（日志保存到 `logs/capture-recovery-*.jsonl`）：

```sh
sudo sh soundsight-3d.sh recover-capture
sudo sh soundsight-3d.sh status
```

成功应显示 `CAPTURE_RECOVERED=1 AXES=OFF NEXT_START=EXPLICIT`，音频 errors=0、pending=false、armed=false、idle=true，DMA halted。PS fault=0x40 可以是停止取消位；其他故障不应忽略。`drops` 是历史累计，恢复不将其伪造为零。

## 复测顺序与证据

先保持屏幕服务停止，运行 60 秒声纹采集、不动作：

```sh
sudo sh soundsight-3d.sh speaker --axes off --seconds 60 --speaker-stats
```

目标人自然连续讲话，确认结束 `RESULT=PASS`、有评分结果。若 FAIL，保留该 JSON 和恢复 JSON，不重复清错重试。

再恢复屏幕：

```sh
sudo systemctl start soundsight-product.service
```

HOME：选择 SPEAKER，先 axes off 运行约 60 秒并 STOP；通过后选择 both 并 START，运行至少 3 分钟再 STOP。确认设备独立舵机电源和共地保持已验证接线。复测至少两轮 START/STOP，并测试声音中断、恢复后旧许可不会跨会话保留。不要为了通过采集测试改变现有门限与滤波参数。

每轮自动保存 `logs/speaker-3d-*.json`。看 `result/error`、`first_fault`、`cleanup_errors`、`packets/tail_packets`、`capture_service`、`direction_frontend`、`speaker_worker.ipc/results` 与 `stats.motion_commits`。定位快照 drops 不等同 PCM 丢包；需对照音频 rejected、published 与接收总数。提交次数也不等于机械实测到位。

若屏幕再次显示 ERROR：DIAGNOSTICS → Recover capture → CONFIRM recovery，等待成功后重新选轴；不得将恢复成功写成采集测试通过。

导出本次日志，用 WinSCP 下载返回的 ZIP：

```sh
python3 -c "from pathlib import Path; from zipfile import ZipFile,ZIP_DEFLATED; import time; r=Path('/home/xilinx/SoundSight_PYNQ_3D_Speaker'); fs=sorted((r/'logs').glob('speaker-3d-*.json'))[-6:]+sorted((r/'logs').glob('capture-recovery-*.jsonl'))[-6:]; p=Path('/home/xilinx')/('speaker-capture-retest-'+str(time.time_ns())+'.zip'); z=ZipFile(p,'x',ZIP_DEFLATED); [z.write(f,f.relative_to(r).as_posix()) for f in fs]; z.close(); print('OUTPUT='+str(p),'FILES='+str(len(fs)))"
```

再用 `sudo sh soundsight-product.sh export` 导出屏幕/服务诊断，下载 `logs/product-check.zip`。该文件每次导出覆盖，下载后按轮次另存。无需导出个人声纹模板或原始录音来判断这次采集故障。

## 验证范围

PC 模型测试覆盖：同输入数值一致、环形缓冲淘汰时当前窗口不变、长历史补算时接收检查点、采集异常/停止中断、先保存后消费、DMA 复位失败、意外 PS 故障不清除、ARM 写异常仍 STOP、屏幕确认恢复与安装备份回滚。

本机 Windows 使用原生 C 求解器进行数值对照。既有声纹测试导入 Linux `resource`，Windows 测试入口仅提供空模块占位且不提供其函数；测试不调用该 API。Linux 内核调度、ARM 实时负载、实际 FIFO/DMA 时序与屏幕联合运行尚未由本机测试证明。板端按上方命令运行原始测试入口，不使用占位模块。

本次不修改 RTL/BD/约束、不综合实现、不操作硬件，也不将取消的定向拾音功能恢复。源码保存在独立任务分支，主目录的其他聊天修改不被覆盖。
