# T15/W15新位流接收与同名包覆盖

输入：`F:/AMD/work/SoundSight_PS_Servo`，用户2026-10-23 16:50完成bit、16:51导出`pl_ps_servo.xsa`。
实际placed I/O报告：servo_pwm=T15，servo_vertical_pwm=W15，均Bank34/LVCMOS33。
实际登记XDC位于`.srcs/constrs_1/imports/horizontal_constraints`；根下horizontal_constraints是旧来源副本，仍有V7/U7，不能用其推断本次构建。
实现时序WNS=0.104ns，WHS=0.036ns，WPWS=2.208ns；setup/hold/pulse-width失败端点0；DRC普通Warning保留。

打包命令：

```sh
python -B tools/package_pynq.py --hardware-project F:/AMD/work/SoundSight_PS_Servo --xsa F:/AMD/work/SoundSight_PS_Servo/pl_ps_servo.xsa --horizontal --output release/output/soundsight_pynq_servo.next.zip
```

通过验证后按用户明确授权覆盖原`soundsight_pynq_servo.zip`。58项，包含新bit/HWH、时序/DRC/实际I/O报告、软件与说明。
实际bit/HWH与XSA逐字节一致；新bit不同于旧包。打包器增加实际I/O校验，错误V7、U7和缺报告内容3项负例均拒绝。
解压新包HWH检查返回0x40000000/4096；CRC、Python3.8语法通过，没有预填机械校准值。
38个软件/测试/短入口文件与上一版逐字节一致，复用`document/evidence/ps-horizontal-20261022/geometry`的174项测试，没有重复宣称本轮运行这些测试。
本轮检查初次使用系统默认GBK读取含中文的XDC失败，改为显式UTF-8后完成检查，未改产品源码。

外部Vivado工程只读，未构建、下载、复位或执行机械动作。临时解压目录自动清理，旧引脚警示在新包内移除；用户若覆盖旧板端目录，按说明删除原遗留警示文件。
