你是接手SoundSight PS声纹功能后续工作的B。先阅读远端交接说明，不从旧main重新推测进度：
https://github.com/TophBeifong1744/SoundSight/blob/codex/b-speaker-handoff-20261026/document/b-speaker-handoff.md

公开源码快照在：
https://github.com/TophBeifong1744/SoundSight/releases/tag/speaker-b-handoff-20261026

我会另外私下发给你soundsight_b_speaker_handoff_private_20261026.zip，包含完整最新板端包、授权录音、声纹模板/参考与对照模型。不要把私有数据或完整私有包上传公开仓库。最新板端包SHA256为59ddc8fd3a5968946c5681221a8e9e96b23759f4b51afac5da986fac00300f87；公开源码由该候选提取，Release自动生成的Source code及main不代表此最新候选。

当前SD卡文件我已更新；先检查板上是否已解压出speaker-live-profile.sh，不让我重刷卡或重复旧测速。最新实麦CPU诊断结果还没有返回。你先对齐交接，再一次几步带我运行pcm-check及sudo sh speaker-live-profile.sh 1；看到CAPTURE_START后我本人正常音量连续说约10秒，保持位置、不换人、不开转台。

已知：epoch26本人录音938包完整，三个实际窗口分数0.691113/0.529008/0.684013，前两次约3.8秒过期，有效身份0。相同窗口离线单独推理约1.09秒，前端并发约1.60秒；18次分数一致，但板端schedstat不可用。不要把CPU秒从墙钟相减当等待。新诊断分别记录推理/前端/采集/快照服务CPU，先依据新日志查明实麦额外开销，再做有证据的小范围PS优化。

短窗低匹配和速度是两个问题；FP32也出现低匹配。旧录音窗口重叠、本人无独立留出测试，不写总体准确率；epoch23已被我排除正常音量评价。暂不改PL、身份阈值、期限或采集优先级，不开启转台。保留旧手动标定、参数配置、普通自动跟随、故障STOP与DMA缓冲保护。硬件构建、下载和动作由我操作。

后续由你接续：真实采集CPU诊断→PS优化及采集稳定性验证→短窗识别与独立留出验证→身份和同时间段方向关联→经明确授权的转台闭环。每批记录取舍、修改、原始证据、失败与未测范围，维护报告素材。源码修改后做相关验证并交完整可搬移的新ZIP，保留配置/日志，默认不覆盖旧包。不要接管其他STM32/3D阵列在途工作。先给我简短的进度对齐和下一组操作命令。
