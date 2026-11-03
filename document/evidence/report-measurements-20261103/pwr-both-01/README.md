# PWR-BOTH-01：独立供电后纯声音双轴短测

收件2026-11-03。用户在确认舵机独立电源模块已准备好后，回报双轴复测没有问题，并提交本包。用户决定继续自己测试，先前委托交接包仅保留为历史准备材料，不表示已派单或已接单。

原ZIP按原名完整保存；CRC及嵌套product-check.zip检查通过。`analysis.json`含提取结果及原件摘要。未修改板端程序、原始日志或供电。

## 已确认结果

| 项目 | 原日志结果 |
|---|---|
| 业务文件 | logs/three-d-20211119-090638-402214-892.json |
| 模式 | SOUND / follow-sound，axes=both；speaker_enabled=false |
| 单调时长 | 85.345991971秒，约1分25秒 |
| 结束 | PASS，user_stop，error=null，cleanup_errors=[] |
| 处理帧数 | consumed=7834，另drained=2 |
| 有效方向 | raw_valid=399，accepted_windows=158 |
| 动作提交 | motion_commits=148；不是148次实测机械到位 |
| PCM | packets=7999，tail_packets=1，最终audio.errors=0 |
| 运行故障 | first_fault=null，fault_or=0 |
| 定位淘汰 | DROPS从888增至1051，本轮增加163；不是本轮新增1051 |
| 快照缺口 | sequence_gaps=161，backfilled_windows=163 |
| 前端诊断 | missing_pcm=1，resets=2；最终排空记录pcm_window_not_received |
| 参数 | 音量9000，窗口3，至少1帧有效；名义40mm四面体几何 |
| 停止读回 | verified=true，runtime_code=0，status_code=0，actuator=0，dual_axis=768，返回READY |

停止后fault=64（0x40），与活动期fault_or=0分开报告；dual_axis保留原值，不把整个状态寄存器要求为0。本轮末尾缺PCM窗口记录按原样保留，不据此声称全程无诊断异常或PCM零丢失。

## 日志关联与新增操作证据

产品服务日志明确记录09:06:31的SOUND/both命令、09:08:12上述同名业务文件正常结束，以及09:08:27 STOP核查通过。产品最终boot_id为93074123-8324-47d5-b9a0-0f059fee2d66，same_boot=true；这段会话没有重启记录，与用户“本轮正常”的观察一致。

面板还记录了08:59:13执行level 9000，且本轮settings.min_level=9000，支持面板参数修改已用于后续业务。speaker-config TTL9.0命令也在服务日志中，但本轮未开声纹，不能证明该TTL在声纹运行中实际生效。

服务日志包含其他短会话；本ZIP只含当前一个业务摘要，不把其他片段拼成连续长稳。previous.json上一启动停在PREPARING、再前一启动为RUNNING的事实保留，不能仅凭摘要确定那些启动为何终结。

## 可用于报告的限定结论

独立舵机供电调整后，用户确认本轮纯声音双轴跟随无异常；配套原日志记录85.35秒正常运行、148次动作提交及正常停止。这支持改线后的短时运行结果，不证明压降根因已经测量确定，不替代声纹联合长稳，也不证明机械指向精度或到位时间。

相比P1-UI-01，本轮轴开启且门限由12500改为9000，其他现场条件未完整记录，不能作为单变量性能对照。保新策略下163次定位淘汰与PCM丢包分别统计；尚未评估其对角度连续性、控制延迟的实际影响。

下一步：在当前板端选择实际目标并确认门限/TTL，完成本人→许可到期→另一人独立讲话的SPEAKER双轴有界测试，保留同轮评分、许可、动作和STOP证据。完整报告提示词仍等待统一材料收口。
