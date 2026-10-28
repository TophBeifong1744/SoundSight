# 无声标定新位流完整SD包接收

输入为用户外部SoundSight_PS_Servo：2026-10-23 22:59:05 bit、22:50:16 HWH、23:03:59 pl_ps_servo.xsa。
起初发现16:51旧XSA与新bit不匹配，没有混入交付；用户随后重新导出，新XSA内bit/HWH均逐字节一致。

## 实际核查

- routed WNS=+0.371ns、WHS=+0.036ns、WPWS=+2.208ns；setup/hold/pulse-width失败端点0；check_timing列出的12类问题计数0。约束范围内通过，原DRC Warning保留。
- 实现报告包含/manual/层级；综合/实现日志含成功结束及Bitgen Completed Successfully。
- 实际placed I/O：servo_pwm=T15、servo_vertical_pwm=W15，Bank34/LVCMOS33。
- ss_manual_servo.sv、ss_ps_control_regs.sv与仓库已测候选逐字节一致，修改时间早于bit；实际登记RTL全部文本一致，7份旧采集RTL只有行尾差异，不擅自覆盖外部源码。
- 原件和注册清单见hardware-receipt.json、actual-source-inputs.zip、实现报告和两份runme日志。初次归档未展开Vivado $PGENDIR导致路径异常；补全真实生成目录后完成归档，未改工程或产品代码。

## 包和验证

命令：

```text
python -B tools/package_pynq.py --hardware-project F:/AMD/work/SoundSight_PS_Servo --xsa F:/AMD/work/SoundSight_PS_Servo/pl_ps_servo.xsa --horizontal --manual-calibration --output release/output/soundsight_pynq_servo.manual-next.zip
```

验证后替换同名soundsight_pynq_servo.zip。61项，根目录SoundSight_PYNQ_Servo；包含新bit/HWH、当前PS/C源码/短命令、自测、三模式说明、实现时序/DRC/I/O报告。没有个人settings.local.json或horizontal.local.json，因此解压不覆盖用户参数；没有系统启动文件/XSA/编译出的异架构so。

新增打包选项要求实际登记的手动RTL匹配已测源码、修改不晚于bit、routed报告包含该层级且时序通过，不靠HWH参数单独声称新功能已经存在。

CRC和Python3.8语法通过。全部PS Python与已验证的软件增量包逐字节相同；C/H和shell入口与上一完整包相同。从新完整包独立解压执行manual_servo 8、board_tools 15、horizontal_motion 28、normal 17，共68项通过。其他同代码测试复用父目录software/final-checks证据，不把复用计作本轮新执行；必要结果见package-checks.json与原日志。

旧完整包SOURCE元数据保留在previous-package-source.json，新包SOURCE.json已归档。软件和工程增量包同步更新说明，除文档外逐字节保持不变。

新组合ARM运行、实物PWM、机械范围和声学跟随未测试；没有启动Vivado、综合、实现、下载、复位或动作。临时解压目录已自动清理，不创建新的codex_out材料。
