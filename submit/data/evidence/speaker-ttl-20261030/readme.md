# 声纹许可按评分TTL续期验证

用户明确要求取消声纹结果的源年龄和语音段时效限制；过线刷新有效期，直到到期且没有新通过结果才撤销。此决定替代旧的静音、低分及语音换段立即撤销规则。

## 改动

- `software/ps/live_speaker_follow.py`：移除等待窗口250ms年龄限制；完整计算不再因语音段变化作废。保留原模型、特征尺寸、有效语音窗口要求、有限队列、采集失败处理。结果邮箱额外保留最新过线结果，后续低分不能覆盖掉一次续期。
- `software/ps/speaker_permission.py`：策略名score_ttl_v2，过线从完成时刻刷新TTL；低分、跳过、静音、换段和语音心跳年龄不清除许可。同会话关联、非法数据、重复/未来完成时间、无配置、故障及停止保护仍保留。
- `software/ps/speaker_process.py`与`software/tetra3d/linux/speaker_runtime_3d.py`：将本次锁定的门限交给子进程邮箱；串口显示新策略名。旧本地配置兼容读取，保存的个人门限和TTL不变。
- `software/tetra3d/linux/client_3d.py`仅更新注释；当前方向的音量、空间窗口、750ms角度读取预算和轴保护不变。低音量会停止当前跟随动作，但声纹许可可仍有效。
- 同步当前使用说明及增量/完整SD打包入口；不改RTL、BD、bit/HWH，不执行构建、下载或舵机动作。

## 实际验证

Linux离线运行：

```sh
python3 -B tools/check_speaker_ttl.py
python3 -B tools/check_latest_sd_package.py --evidence document/evidence/speaker-ttl-20261030
```

开发机WSL无PATH中的Python3，使用已有`sh software/tests/run_stream_python.sh -B ...`执行相同入口。

- 源码回归69项通过：许可/联合27、评分显示7、角度过期5、实际进程通信9、三维控制21。
- 完整SD包实际解压后78项通过：上述许可/显示/角度/三维共60项，加录入18项；与源码回归有重叠，不作为额外78个独立用例。包内Python与仓库相符，bit/HWH与原收件一致，6个模拟私人文件保留。
- 增量包真实安装通过：旧文件备份可读取，4个模拟私人文件原样保留，旧策略配置0.45/10秒兼容读取，新代码逐文件一致，bit/HWH原样保留。安装不接触硬件。
- 关键预期覆盖：旧语音段推理可通过；等待4秒仍计算；连续通过延长TTL；低分/无分数/静音不延长也不缩短；恰好到期关闭；以后通过重新许可；未配置不得许可；过线事件后紧随低分不会漏续期；低音量/旧角度不提交动作；采集及进程错误STOP。

结果见tests.json、各test日志、increment-check.json与sd-package-check.json。测试临时目录通过TemporaryDirectory自动清理，未创建codex_out；无板端实测结果，不宣称声纹准确率或新版声纹双轴实板通过。未提交或推送Git。

## 现场依据与边界

用户现场输入：有效方向124.92/-50.87度，评分0.5519超过0.45，但旧代码标SPEECH_STATE_CHANGED，PERMIT=0。先前完整30秒摘要在`project/reports/ps_3d/latest_result/board-speaker-30s-001-summary.txt`；新行为不是重解释旧日志，而是按用户决定修改许可规则。

许可有效期内，目标人停止说话或另一人接着说话不再立即撤销许可，因此可能跟随后来的声音；当前方向仍须合格。模型、声纹门限与用户模板未被自动修改。
