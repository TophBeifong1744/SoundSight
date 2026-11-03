# 给 A：屏幕声纹模式采集溢出，排查并修复

交接日期：2026-11-03。用户明确要求由 A 完成排查和修复，结果通过用户返回本对话。
本文件仅交接证据和任务，本对话没有修改产品代码，也没有实际发送消息到 A。

## 目标与复现现象

用户在屏幕选择 SPEAKER，点击 START 后，声纹会话 FAIL，屏幕提示：

```text
STOP NOT VERIFIED. Inspect status; restart blocked.
```

随后照片显示 `SPEAKER | ERROR | SELECTED AXES OFF`，诊断页包含：

```text
SPEAKER_3D_STOPPED RESULT=FAIL OUTPUT=/home/xilinx/SoundSight_PYNQ_3D_Speaker/...
PYTHON_EXE=/usr/local/share/pynq-venv/bin/python3
PYNQ_IMPORT_OK=1
DEVICE_STATE={"status":999430,"fault":64,"drops":378,"sys":8,...}
```

照片右侧被截断，actuator/dual_axis 的完整数值没有提供，不应补造。
照片底部后来显示 `Wait for confirmed STOP/exit before another operation`。
尚未收到本次 drain、重启或恢复成功的回报，不把建议执行的命令算成已执行。

请完成：确定积压的具体原因、修复持续运行、补齐屏幕故障恢复入口，并交付更新包及实测结果。
仅通过复位消除当前错误、仅降低门限、或恢复后能 START 一次，都不能作为本故障修复完成的依据。

## 代码基线

- 最新候选：[PR #43](https://github.com/TophBeifong1744/SoundSight/pull/43)，分支 `codex/product-screen`。
- 本次核对提交：`89dd7fc2e6bb172cbb165a9a6a2e70fcd581225b`。
- P1 软件功能提交：`eb05bd5bfa2e5f8d3d01d494965497bd70e3209e`；后续提交只同步 submit 和报告。
- P1 安装包：仓库 `release/output/soundsight_screen_product_p1.zip`，submit 内为 `submit/board/artifacts/soundsight_screen_product_p1.zip`。
- 板端目录：`/home/xilinx/SoundSight_PYNQ_3D_Speaker`。
- 现有组合：S2 PS I2C0/EMIO 屏幕硬件、P1/S3 面板、CF1A 三维、CP1/VF1 声纹、score_ttl_v2。
- 请先核对实际板端版本与此候选是否一致，再复现；不假定板端没有 A 或用户后续修改。
- 本机 `F:/NUEC/SoundSight-product-screen` 属原对话工作区。A 使用自己的分支/工作副本，避免同时写入该目录。

## 原始故障数据（用户提供）

板端文件：`logs/speaker-3d-20211119-093218-301074.json`。
文件名使用板端时钟 2021-11-19，不是实际交接日期；未修改该文件或其日期。

```json
{
  "result": "FAIL",
  "error": "RuntimeError: Capture/servo fault; stop and preserve diagnostic state",
  "speaker_worker": {
    "status": "FAIL",
    "error": "CAPTURE_FAILED_IDENTITIES_INVALID",
    "input_packets": 277,
    "generated": 0,
    "replaced": 0,
    "consumed": 0,
    "results": [],
    "retained_result_limit": 32,
    "max_front_lag_seconds": 0.04274260599988877,
    "statistics": {"enabled": false},
    "policy": "score_ttl_v2",
    "current_identity": "insufficient",
    "reason": "session_ended",
    "recognition_qualified": false,
    "model_selection": "cp1_vf1",
    "motion_commands": 0,
    "ipc": {
      "process_isolated": true,
      "packet_limit": 32,
      "sent": 277,
      "frontend_taken": 277,
      "highwater": 3,
      "kernel_send_buffer_bytes": 360448
    },
    "eligible_results": 0
  }
}
```

```json
{
  "first_fault": {
    "audio": {
      "raw": 278,
      "errors": 1,
      "armed": false,
      "pending": true,
      "partial_tail": true,
      "idle": false,
      "dma_reset_released": true,
      "ready": false,
      "rejected": 1,
      "published": 282,
      "epoch": 62
    },
    "status": 999430,
    "fault": 0,
    "drops": 378,
    "dma_status": 4098
  },
  "hardware": {
    "audio": {
      "raw": 278,
      "errors": 1,
      "armed": false,
      "pending": true,
      "partial_tail": true,
      "idle": false,
      "dma_reset_released": true,
      "ready": false,
      "rejected": 1,
      "published": 282,
      "epoch": 62
    },
    "status": 999430,
    "fault": 64,
    "drops": 378,
    "dma_status": 4098
  },
  "cleanup_errors": [],
  "dma_halted": true,
  "packets": 277,
  "max_service_gap_seconds": 0.029291731000057553,
  "max_dma_rearm_seconds": 0.0006097109999245731
}
```

## 已确认与尚未确认

已对照当前代码确认：

1. `audio.errors=1` 对应 `ss_audio_capture.sv` 的 errors[0]：数据 FIFO 或描述队列满条件；这是本次直接停采原因。该位不能单独区分哪一种队列满。
2. `rejected=1` 记录一次拒收；`published=282` 和软件已接收277存在积压，不能简单把差值当作永久丢失包数。
3. 首次主 `fault=0`，停止后为64（`FAULT_CANCEL_STOP`）。不能把停止标记当作最初故障，也没有证据将本次归因为舵机机械故障。
4. `status=999430=0xF4006` 含 `SNAP_STATUS_QUEUED=0x2`；屏幕的 idle_state 拒绝残留队列，所以阻止重新启动。
5. 故障分支保留旧帧；正常退出才执行尾部排空。音频硬件状态在 DMA reset 前记录；`dma_halted=true` 是之后 reset 确认成功，不能声称这份 hardware 字段是 reset 后状态。
6. 声纹结果尚未生成。`CAPTURE_FAILED_IDENTITIES_INVALID` 是会话采集失败后的作废结果，不是本人匹配失败，不应改门限或重新录入来掩盖。

尚未确认：

- FIFO 满的具体服务瓶颈，是否由屏幕绘制、三维处理、CPU调度、DMA续接或多因素叠加造成。
- 每包512样点/48kHz约10.67ms，最大服务间隔29.29ms提示服务压力，但单次间隔不足以证明根因；数据FIFO默认2048样点，不能以29ms大于10ms就断言必然溢出。
- 声纹前端lag和主采集循环gap是不同计时边界，不能直接相加。IPC highwater=3/32、sent=taken=277，也不能据此认定IPC队列满。
- 原有141项离线测试通过不覆盖本次真实ARM屏幕并发故障，不能作为本次已修复证据。

## 建议 A 的排查与修复顺序

1. 先保存上述完整 JSON、当次面板/service日志及实际版本。核对没有另一采集进程或重复服务，不先覆盖日志或清除所有故障位。
2. 在关轴条件下，以相同几何、声纹参数和输入比较屏幕声纹与直接CLI声纹。轻量记录DMA接收/续接、CF1A接包/解算、IPC和屏幕绘制耗时及CPU调度；避免高频同步打印本身扰动采集。
3. 检查 `capture_joint` 每轮接收一个已完成包后进入同步三维处理的行为，是否导致积压增长。根据测量选择受限追赶、计算解耦或调度调整；现有代码已在计算前续接DMA，不应把“先续接”当作尚未实现的新修复。
4. 如需调整三维任务频率，保持PCM连续性、精确窗口对应、时效限制和动作门禁，不静默丢PCM来制造通过。不预先认定需要修改位流或扩大FIFO。
5. 增加明确的屏幕故障恢复操作：保存诊断、确认运行进程退出、撤销双轴许可、停止音频与DMA、处理残留定位/音频状态、按支持的硬件时序重新初始化并读回。全程保持单所有者，恢复后关轴且旧身份许可失效，必须再次明确START。
6. 当前 `Recheck / reload` 只重读状态；`drain` 仅处理定位残留帧，不能保证清除音频sticky错误。不能把两者描述成完整RESET。`prepare`对已加载同一overlay也不会自动重新下载清错。请设计有依据的恢复流程，不添加未经验证的任意MMIO清零。

重点源码：

- `software/tetra3d/linux/speaker_capture_3d.py`：采集服务、首次故障和清理。
- `software/tetra3d/linux/speaker_runtime_3d.py`：会话、推理进程与输出报告。
- `software/tetra3d/linux/coherent_frontend.py`、`client_3d.py`：CF1A与定位处理。
- `software/ps/pcm_capture.py`、`speaker_scheduling.py`：DMA与CPU调度。
- `software/screen/backend.py`、`ui.py`、`product.py`：停止检查、屏幕刷新、自启服务。
- `project/rtl/ss_audio_capture.sv`、`ss_audio_fifo.sv`：错误位、FIFO及复位/新epoch语义。

## 回传与验收

请 A 回传根因证据、修改文件/提交/PR、安装包及恢复/回滚说明。不要只回传“已修复”。

建议先关轴做屏幕+声纹连续运行，再测双轴。每轮保留实际时长、packets/published、音频errors/rejected、首次故障、服务耗时、声纹结果、STOP和DMA停止读回。若做10分钟或更长测试，按实际时长和结果报告，不以短测替代。

至少覆盖：

- 相同复现场景不再出现FIFO满，音频errors=0、rejected=0，正常STOP后的完整包计数按尾部规则一致。
- 有声输入下能产生声纹结果；本人许可/到期规则沿用原逻辑，不将本次当成重新标定识别率。
- 故障后可在屏幕恢复到经读回确认的待机；不自动转动、不沿用旧许可、不遗留重复采集进程。
- 多次START/STOP及至少两次故障恢复过程；恢复失败仍阻止启动并保留错误。
- 新P1上电自启与屏幕关机仍按原清单验收，不因修复采集就一并宣称通过。

原声纹/阈值/TTL、机械标定和用户数据保留。用户不需要再提供相同错误的重复截图；需要进一步板测时给出明确单轮步骤和应回传字段。
