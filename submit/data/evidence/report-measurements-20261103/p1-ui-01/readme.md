# P1-UI-01：触屏启动、关轴测角与停止

收件日期2026-11-03；板端2021年文件时间按原文保留。用户改为照片留存，不再要求视频。未修改板端程序、原日志或照片。

## 本轮可确认的结果

`product-check.zip`的服务日志明确指向原业务文件`three-d-20211119-085141-188466-685.json`（本目录保存为`runtime.json`），支持同轮关联。

- 面板发出`follow-sound --axes off --frames 0`，本轮没有启用声纹。
- 运行57.648402秒，5403个PCM包，处理5396帧，另排空1帧；172个原始有效方向、50个通过筛选的方向组。
- 音量门限12500，窗口3帧，最少1帧有效；低于音量门限4122帧。没有逐阶段标记，不能推算前方/侧方/安静各段的效果或方向精度。
- 动作提交0；结束原因user_stop，程序结果PASS，error为空，清理错误为空，DMA停止。
- 面板STOP读回通过，runtime_code/status_code均0，回到READY；actuator/dual_axis均0。
- 活动统计fault_or=0；结束硬件fault=64（0x40），原值保留。定位结果DROPS由0到5，序号缺口4，前端补算5窗；不是零淘汰，也不能把DROPS直接写成PCM丢包。
- 尾部保留`pcm_window_repeated_or_reversed`及1次前端重置，未扩大为全程无异常。前端mean_solve约7.157ms、max_solve约20.380ms；最大服务间隔约31.344ms。
- 面板STOPPING至READY约14.756秒，包含状态检查启动和回读；不能当作舵机停止时间。

## 不能由本轮覆盖的事项

- 当前boot_id为`c3064f49-5efc-44e3-b87b-1447b25c8e68`，与先前首次出画面的boot_id不同；不合并成一次连续启动/长稳。
- 包内previous.json保留上一启动ERROR、stop_verified=false和“STOP NOT VERIFIED”。本轮正常停止不证明上一失败根因已解决。
- 本轮没有声纹或运动，不证明双轴到位、声纹识别、联合长稳、参数修改生效或多用户持久化。
- 照片显示HOME/SETTINGS页面、整机和停止后的可见状态。没有录像，不量化触摸延迟、机械起转/到位时间；现有图无法单独验证四通道编号、40mm尺寸或电源规格。

## 照片索引

| 文件 | 可以用于报告的内容 |
|---|---|
| photos/home-idle.jpg | HOME，SOUND/IDLE/AXES OFF，音量12500、筛选1/3 |
| photos/settings-level.jpg | SETTINGS音量参数12500及保存值；不能单图证明更改生效 |
| photos/whole-system.jpg | 阵列、双轴机构、主板、RGB屏幕和连接的实物总览；屏幕可见STOP verified |

原图包含学校标识；后续如需匿名展示，另制裁切副本，保留原件。未对图像进行编辑。

机器可读结果见`analysis.json`，原件来源文件名及完整性记录见`files.json`。当前只本地归档，尚未据此修改两份报告或生成报告提示词。
