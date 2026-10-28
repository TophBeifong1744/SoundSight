# 给 B：声纹与三维双轴接合说明

> 公开同步范围：本文描述此前私有完整包的联合接口和验证。识别引擎继续由 B 维护；main 只同步 A 侧许可接收器和三维适配器。下文提及的 `pynq-speaker-3d.md` 和完整运行资产随私有联合包交接，不能由 main 单独重建；公开子集说明见[维护入口](rtl-3d-maintenance.md)。134 项和实际模型测试是此前完整组合的证据，不是本次公开子集测试数。

拓芙确认采用延迟声纹许可原型：角度快路独立计算；声纹一算完就更新许可。上一次通过可以覆盖下一轮推理等待，但发布后默认 **3 秒**到期，可调。新失败、静音、失联、故障和停止撤销许可。试验余弦门限 **0.65** 可调，未配置不放行。这取代本入口原来“结果必须在源数据 2 秒内、尚不驱动舵机”的试验约束；旧诊断入口仍保留原策略。

## 接好了什么

- 新短入口 `soundsight-3d.sh speaker`：当前三维测角、CP1/VF1、评分显示和许可判断一起运行，默认不动；显式 `--axes horizontal|vertical|both` 才参与双轴跟随。
- 三维短入口的 `run` 默认仍只测角；如果附带 `--axes`，自动转到同一声纹门控路径，避免沿用旧命令绕过许可。手动标定依然独立。
- 一个硬件所有者服务 PCM DMA 与三维快照。不要再同时启动原独立 PCM／speaker／三维采集程序。
- 原四路 48kHz S24-in-S32 输入、原 C 前端、16kHz VF1 状态、192 维嵌入／归一化／模板余弦不变。CP1 只接 1 秒原生 98×80 特征；登记仍用原动态模型。
- 原始模型、模板绑定及 P02 score-only 标记保留。0.65 是外部的 `delayed_permission_v1` 试验门限，不把 P02 改成已标定识别器。
- 结果通道有界，前端状态和推理结果各一个最新槽；输入仍用 32 包信用限制。推理是一项在算＋一项最新待处理，不积压历史窗口。正常模式不逐帧写 SD。
- 当前 SoundSight_PS_3D 位流已有所需 PCM、双轴接口，因此本批没有修改 RTL、BD 或舵机引脚。硬件仍校验锁帧、限位、STOP 和 750ms 租约。

## 程序接口

| 数据 | 主要字段 | 含义 |
|---|---|---|
| 前端状态 | `kind=voice, epoch, voice_epoch, active, at, end_sample16` | PCM 会话、语音段及最新前端进度；静音切换递增 voice_epoch |
| 每次评分 | `kind=result, epoch, voice_epoch, start_sample16, end_sample16, score, usable, completed_at, compute_seconds, source_age_seconds, target_id, model_selection` | 样本范围以 16kHz 计；时间为同一台 Linux 单调时钟，不是系统日期 |
| 本地许可配置 | `threshold, permit_seconds, policy` | 门限可为空；有效期默认 3 秒；会话间只保存配置，不保存许可 |
| 许可状态 | `permit, reason, remaining_seconds, latest_result` | 由唯一硬件所有者计算；传输/轮询不会续期 |

新结果必须属于当前会话和当前语音段。静音后旧推理即使晚到也不能恢复许可；音量门限导致的静音还会使跨过该静音边界的旧窗口失效。当前方向仍需要自身合格和新鲜，身份通过不会绕过方向筛选。

核心源码：

- `software/ps/speaker_models.py`：显式 CP1/VF1 路由，原动态模型用于登记。
- `software/ps/live_speaker_follow.py`：持续前端、最新窗口、完成即发布。
- `software/ps/speaker_process.py`：有界实时结果 IPC，与原 packet ACK 分开。
- `software/ps/speaker_permission.py`：3 秒许可和撤销规则。
- `software/tetra3d/linux/speaker_capture_3d.py`：唯一 DMA／三维／舵机所有者。
- `software/tetra3d/linux/client_3d.py`：方向与声纹许可同时满足才提交。

## 继续调试的重点

保留原板上的 P02 模板及选择文件，导入新目录即可，不重复登记。板端先用 `speaker --seconds 30` 不开轴，看连续采集故障／丢帧、分数、VAD 状态及完整计算延迟，再测试目标本人、其他人和交替说话，以确定门限。新方案允许延迟，但不能把离线 1.296 秒说成实际并发延迟，也不能把“许可通过”说成当前角度一定属于同一人。

后续可继续优化模型和运行耗时，保持上述评分事件接口即可。详细安装和自由调参命令见 `document/pynq-speaker-3d.md`。新增包带模型与原登记模板，私下传递；本批不公开推送私人资产。

本轮离线验证：134项策略／接口／回归通过；真实模型96块前端/VAD、3窗嵌入与原版逐位一致，564包历史PCM跑通独立进程评分通道。独立复核发现并关闭了ARM至COMMIT间许可过期的问题。已验证独立解压包与P02配置迁移；没有进行本次ARM联合实麦或舵机板测，0.65仍是试验门限。
