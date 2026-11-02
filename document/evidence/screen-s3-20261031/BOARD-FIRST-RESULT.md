# S3 首次板端回传 — 2026-10-31

原文：S3-FIRST-BOARD-RAW.txt。命令由用户在 PYNQ 执行，非本机模拟。

## 已确认

- 安装成功：SCREEN_CONTROL_S3_INSTALLED=1，备份 backup_screen_control_s3_s1887ly8；位流/私有配置保持，安装未操作硬件。
- prepare 所列118项测试全部OK（板上执行的软件测试，不等于118项硬件实测）；ARM库加载、实际位流加载成功，FCLK0约100 MHz，真实末次fault=0、drops=0、actuator=0、dual_axis=0。MIN_LEVEL=12000。
- PS I2C0动态启用success=true，cdns-i2c绑定/dev/i2c-0、100 kHz。
- SCREEN_S3 / VDMA_STARTED / GT911@0x14 / SCREEN_READY CONTROL=1 AXES=off。
- 两次status按钮命令、一次SOUND关轴连续模式启动命令被面板发出。

## 未闭合的运行结果

```text
PANEL_COMMAND={"operation": "SOUND", "arguments": ["follow-sound", "--axes", "off", "--frames", "0"]}
PANEL_RUNTIME=STOP: KeyboardInterrupt:
PANEL_STOP_CHECK={"verified": true, "runtime_code": 1, "status_code": 0,
 "device": {"status": 983040, "fault": 0, "drops": 0, "sys": 8, "actuator": 0, "dual_axis": 0}}
VDMA_STOPPED=1 HALTED_ACK=1 BACKLIGHT_REQUEST=OFF
```

设备空闲读回和显示DMA停止均已确认，没有这次故障位/丢帧增加的证据；但 runtime_code=1 不能当作正常会话通过。只有外层STOP: KeyboardInterrupt，缺少操作时机、完整后台输出和原生运行报告；可能在启动检查阶段被中断，**不能凭现有日志确定原因**。S3会保守锁定失败会话，Recheck不会把它恢复为成功。

本轮没有SPEAKER启动、非off轴选择/运动、有效当前角度/声纹结果或完整正常STOP证据；面板最终退出码也未回传。不能将其记为双人声纹、三维运动或S3全功能已通过。

## 交给 C 的具体核对

先读当前配置/状态，在SOUND运行出现实际帧/方向或RUNNING后再STOP，记录从START到STOP的时机与屏幕状态。正常运行后STOP若仍非零，保存面板日志与原生会话JSON交回；没有原生报告时如实注明。此项可作为C三项集中测试的第一步，不要求用户现在重新完成整轮，也不在证据不足时改代码隐藏异常。

prepare输出中的usage/error和fault72/64出现在软件单元测试夹具内，最终均OK；不能把夹具值当作本板真实故障。overlay memory-leak警告涉及覆盖层移除，本次启用成功，未要求移除或重复绑定。
