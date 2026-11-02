# A → 用户 → B：CF1A三维测试结果

未执行项填“未测”，不要按预期预填通过。

- 测试人/实际日期时间（板上日期可能不准）：
- 基线：原样CF1A / 已合入A新功能（说明）：
- A新增改动/commit/补丁附件（若无填无）：
- 更新安装：成功 / 已安装 / 拒绝 / 失败；BACKUP_DIR：
- check及prepare退出码；是否同次开机跳过prepare：
- 本轮日志目录：
- SUMMARY原始路径：
- 返回tar.gz文件名：
- 阵列/通道/机构/供电/接线是否与原测试相同（说明变化）：
- 本轮轴选择、水平/垂直配置：
- 音源（讲话/播放）、距离、高度、移动过程和有声时段：
- 运行显示CF1A且SPEAKER=DISABLED：是 / 否（附原文）：
- 实际MIN_LEVEL/WINDOW/MIN_VALID（启动日志或JSON）：
- 角度输出：持续或间歇、有无长时间无输出（描述）：
- 水平轴：是否转动、方向是否合理、有无抖动/反转（描述）：
- 垂直轴：是否转动、方向是否合理、有无抖动/反转（描述）：
- 是否自动停止、是否使用Ctrl+C、停止后观察：
- 异常及处理（是否prepare/重启/改参数）：
- 视频/额外文件（可选）：

以下有原生JSON即可，由B复核；不清楚就留空，不用自行判读或改写JSON：

| 指标 | 本轮实测 |
|---|---|
| result / error / cleanup_errors | |
| epoch / packets / tail_packets | |
| consumed snapshots / sequence gaps | |
| drops起始、活动末、停止末 | |
| direction_frontend.revision | |
| solved / valid / resets / missing_pcm | |
| snapshot_gaps / backfilled_windows / max_windows_per_solve | |
| mean_solve_seconds / max_solve_seconds | |
| max_service_gap_seconds / max_frame_service_seconds（若有） | |
| 最终滤波有效输出 / motion commits | |
| first_fault / dma_halted / stop_reason | |
| 结束独立status读回 | |

初步结论分别填写：安装与启动 / 正常停止 / 方向可用性 / 双轴实际表现。不要把一项PASS当作整机验收；精确角度、长期运行、声纹及屏幕并发均非本轮必测。
