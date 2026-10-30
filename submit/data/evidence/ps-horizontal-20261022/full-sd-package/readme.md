# Servo完整SD包核查

输入：用户实际`F:/AMD/work/SoundSight_PS_Servo`工程及`pl_ps_servo.xsa`；只读，未启动EDA或硬件操作。

打包命令：

```sh
python -B tools/package_pynq.py --hardware-project F:/AMD/work/SoundSight_PS_Servo --xsa F:/AMD/work/SoundSight_PS_Servo/pl_ps_servo.xsa --horizontal
```

输出为`release/output/soundsight_pynq_servo.zip`，根目录`SoundSight_PYNQ_Servo`，57项。
打包器逐字节验证bit/HWH与XSA一致、HWH动作/音量参数正确、ZIP复制完整性。
另核6份动作通路RTL与仓库一致，以及副本XDC水平V7、垂直U7。

解压包后在独立临时目录运行7组96项测试，全部通过，日志在本目录；Python3.8语法和shell LF通过，HWH地址0x40000000/4096。
临时目录已由TemporaryDirectory清理。新组合未执行ARM编译、PYNQ下载或实物动作。
检查脚本第一次把返回的`(base, bytes)`当成单个地址断言，已修正并完整复验，产品未因此改变。

实现报告由用户生成，原件随ZIP的reports保留。WNS=0.278ns、WHS=0.036ns、WPWS=2.208ns；失败端点全0。
check_timing缺时钟/缺输入输出延迟/未约束内部端点均0。DRC含DSP流水线、BRAM异步控制等Warning，不能声称零告警。
实际PWM、转向、机械限位与声音跟随仍需实物验证。
