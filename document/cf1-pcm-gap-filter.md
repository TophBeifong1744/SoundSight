# CF1 连续音频与最新定位快照衔接修复

修订：CF1_PCM_GAPS_V1，2026-11-03。PS/Python 与触屏软件更新，不修改 RTL、位流、HWH、C 数值求解器、声纹模型、个人配置或引脚。

## 本轮问题与结论

用户的 59.226 秒 SPEAKER 联合运行正常结束：5546 个 PCM 包，声学采集 errors=0/rejected=0；2336 个已消费定位结果、1780 次定位序号缺口、361 个原始有效方向、0 个合格滤波组、0 次运动提交。定位快照 drops 增加3207，不能称为音频丢包。声纹有通过门限的结果，许可通过不能替代有效方向。

CF1 已从连续 PCM 补算频谱历史，但旧球面滤波仍在每次快照跳号时清空，造成处理速度低于快照生成速度时难以收满组。1432 个 NORM 拒绝、1223 个低音量帧也是真实存在的独立原因。本文件不是“声学问题全部解决”的声明。

## 本次行为

- 联合 CF1 模式显式启用连续 PCM 证据；旧非 PCM 路径仍要求连续快照序号。
- 两次已处理快照相隔最多16个512采样点步长（约170.7ms），同一音频 epoch，正向序号与采样时间，区间 PCM 块全部在已校验缓冲中且无削波时，允许保留组内已处理结果。该证据在协作式收包可能淘汰缓冲前计算。
- 每组仍只计实际处理的定位结果；不会把跳过的快照补成有效角度，也不声称知道跳过帧的音量或质量。当前帧音量、原始解算有效性、最少有效数、10°共识、2/3比例、3°死区不变。
- 组内主机时间跨度与源采样起点跨度均受750ms上限约束。单帧来源过期/未来时间、缺失证据、音频断裂、epoch变化、逆序、大缺口会拒绝或清组；STOP和故障仍清组。
- `NORM`、残差不合格不会被强行归一化放行。硬件原始有效对数不少于4、声纹许可、位置限位和超时仍单独检查。
- 串口增加 `RAW_REASON` 与 `RAW_PAIRS`（后者是软件求解有效对数，不等于硬件原始对数）。无角度时触屏显示 `No angle: ... W=已处理/总数 V=有效/最少`。
- 新增结束摘要 `direction_diagnostics`：跳号接续数、窗口完成/通过数、重置和运动原因、单帧求解拒绝原因、门限以上帧的模长/残差范围与总和/数量（平均值=total/count）、每种原因最多两个样例。记录量有固定上限；不逐帧写SD、不保存新增音频、不随运行时长堆积记录。

## 安装（WinSCP上传新ZIP到 /home/xilinx）

先在屏幕点击 STOP，等显示 IDLE。使用新文件名 `soundsight_direction_filter_update.zip`，不要重新安装旧的 capture 修复ZIP。

```sh
sudo systemctl stop soundsight-product.service
sudo python3 /home/xilinx/soundsight_direction_filter_update.zip --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh check
python3 -B software/tetra3d/tests/test_pcm_gap_filter.py
```

安装器接受已安装的上一版 CAPTURE_COOPERATIVE_V1；校验后备份并更新安装清单。配置、档案和旧日志保留。出现 BASELINE_MISMATCH / LOCAL_CHANGE_PRESERVED 时保留输出，不手工强覆盖。安装器不会加载FPGA或启动舵机。

## 先关轴复测，再双轴

当前已 prepare 且未重启的板子无需重新加载位流。屏幕服务停止期间先执行：

```sh
sudo sh soundsight-3d.sh status
sudo sh soundsight-3d.sh speaker --axes off --seconds 60 --speaker-stats
```

保持当前音量、窗口（本轮5/2）、声纹门限及TTL，目标人在固定位置持续说话，以便与上一轮比较。终端应出现 `FILTER_POLICY=CF1_PCM_GAPS_V1`。若 status 提示旧帧，先 `sudo sh soundsight-3d.sh drain`；若提示 NOT_PREPARED，再执行 `sudo sh soundsight.sh prepare`。若有新采集故障，保留日志并按上一版 `recover-capture` 处理，不通过重启抹掉现场。

确认摘要无错误、采集无新错误、开始出现合格方向组后，再开启双轴：

```sh
sudo sh soundsight-3d.sh speaker --axes both --seconds 60 --speaker-stats
```

也可执行下句恢复触屏，然后在 HOME 选 SPEAKER、先 off 复测，再 STOP、选 both、显式 START：

```sh
sudo systemctl start soundsight-product.service
```

服务启动不会自动让转台跟随。若重启，按现有产品启动流程准备，屏幕默认不开轴。安装器的通用提示可能建议重启，本次纯PS补丁不要求重新导出/更换位流。

## 导出最近一次 SPEAKER 结果

停止测试后执行（使用普通 xilinx 用户运行，导出ZIP可直接通过WinSCP读取）：

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo python3 -c "import os,pwd,time; from pathlib import Path; from zipfile import ZipFile,ZIP_DEFLATED; p=max(Path('logs').glob('speaker-3d-*.json'),key=lambda p:p.stat().st_mtime_ns); out=Path('/home/xilinx')/('soundsight-direction-check-'+str(time.time_ns())+'.zip'); z=ZipFile(out,'x',ZIP_DEFLATED); z.write(p,p.name); z.close(); u=pwd.getpwnam('xilinx'); os.chown(out,u.pw_uid,u.pw_gid); os.chmod(out,0o600); os.sync(); print('SOURCE=',p); print('OUTPUT=',out)"
```

每轮分别导出；不要将软件提交次数当作机械到达次数。若仍无角度，回传新摘要，重点比较 `direction_diagnostics.by_solver_reason`、`resets`、`completed_groups`、`raw_valid_above_volume`，不凭 permit=YES 就降低定位质量门限。

## 验证边界

PC合成声场与寄存器模型只能验证算法、衔接和拦截行为，不能证明当前房间、阵列布局与机械跟随效果。板测59秒原件是修复前输入；并无完整逐帧PCM，不能把合成对照称为该板测的离线重放。新板测待回传，所有物理验收仍以实物结果为准。
