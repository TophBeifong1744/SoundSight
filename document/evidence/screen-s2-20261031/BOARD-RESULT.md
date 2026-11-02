# S2 实板结果 — 2026-10-31

证据来源：用户在本对话回传的 PYNQ 串口日志和现场观察；命令由用户执行。

## 安装与启用

- 安装返回 SCREEN_PS_I2C_S2_INSTALLED=1，备份目录为 /home/xilinx/SoundSight_PYNQ_3D_Speaker/backup_screen_ps_i2c_s2_vhrsvudu。
- prepare 完成下载，随后 status：status=983040、fault=0、drops=0、sys=8、actuator=0、dual_axis=0。
- apply 返回 success=true、SETUP_EXIT=0。PS I2C0（e0004000）由 disabled 转为 okay，100000 Hz，绑定 cdns-i2c，设备 /dev/i2c-0。
- ARM ABI 检查：pointer_bytes=4、msg_bytes=12、buf_offset=8、transfer_bytes=8。apply 本身未进行触摸事务。
- 动态 overlay 有移除属性时的内核内存泄漏警告；未移除或重复绑定。

## 两轮关轴屏幕测试

两轮均使用：

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen.sh --seconds 60 2>&1 | tee -a screen-s2-test.log
echo SCREEN_EXIT=${PIPESTATUS[0]}
```

两轮日志均包含：

```text
SCREEN_S2 transport=PS_I2C0_EMIO_LINUX Python=3.8.2 Pillow=7.0.0 numpy=1.20.3
SCREEN_PREFLIGHT={'status': 983040, 'fault': 0, 'drops': 0, 'sys': 8, 'actuator': 0}
VDMA_STARTED version=0x62000050 frame0=0x38100000 frame1=0x38300000 stride=2400 height=480
TOUCH=Goodix 911 @0x14
SCREEN_READY=1 CURRENT_FRAME_ACK=1 AXES=off CONTROL=0
VDMA_STOPPED=1 HALTED_ACK=1 BACKLIGHT_REQUEST=OFF
SCREEN_EXIT=0
```

第一轮用户明确确认“触摸有响应，没有提前黑屏”。第二轮日志确认重复启动、触摸芯片识别和正常退出；第二轮没有另行回传逐点触摸观察。两次命令均设置 60 秒，日志没有独立墙钟测量，不记为精确 120 秒长稳。

第二轮结束后实际状态：

```text
DEVICE_STATE={"status": 983040, "fault": 0, "drops": 0, "sys": 8, "actuator": 0, "dual_axis": 0}
```

结论：PS I2C0/EMIO + Linux Cadence 基础显示/触摸首板及重复启动检查通过；此前 AXI IIC 报错本轮未复现。不据此认定原 AXI IIC 唯一故障根因。

仍未验收：触摸全屏坐标精度/全部按钮、异常总线超时恢复、长时间运行、重启后的重复完整启用，以及屏幕控制与声音/声纹/双轴联合运行。当前 AXES=off、CONTROL=0，不能解释为屏幕已控制跟随。

本次仅补充板测记录，产品源码、位流及已交付 ZIP 保持不变；不重新构建或打包。基础链路子任务完成，等待用户下一步功能指令。
