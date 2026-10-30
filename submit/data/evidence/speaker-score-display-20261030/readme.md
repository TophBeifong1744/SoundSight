# 声纹评分展示与许可分离

日期：2026-10-30。软件显示修复，不改RTL、BD、位流、VAD、声纹门限、许可寿命或执行器条件。

## 现场输入与原因

用户10秒关轴测试：937个PCM包均进入前端，产生119个候选窗、115次替换、4条处理结果。
实际分数0.5018032608和0.4157561204，计算耗时3.4707秒、3.3042秒，均为
`usable=false / speech_state_changed`。随后分别出现无分数的`stale_before_start`，
启动年龄0.3865秒、0.4441秒，超过原250ms时限。串口因此显示NONE，掩盖已经算出的分数。
现场音量门限12000、声纹门限None、轴关闭；不能解释为身份匹配通过。

## 修改及预期

- 最新事件邮箱仍保持原许可事件合并规则，另附最后一条数值结果用于诊断，槽位固定。
- 许可状态保留原score/latest_result语义，增加独立display_result，空分数不覆盖历史数值。
- 展示计算完成后的年龄、完成时可用性、分数原因；PERMIT及PERMIT_REASON单独显示。
- 错会话、NaN、越界分数、负时间、未来时间、旧时间及非字典诊断不进入展示。
- 新会话清空历史显示；低音量、静音、换段、失败、超时和STOP仍按原规则撤销许可。

## 验证

Linux离线命令（有Python3的主机/板端可直接执行）：

```sh
python3 -B software/tests/test_speaker_display.py -v
python3 -B software/tests/test_speaker_follow.py -v
python3 -B software/tests/test_speaker_process.py -v
```

结果：7+23+9=39项通过。覆盖现场“有分数结果紧随无分数跳过结果”、跨轮显示保留、
静音/过期/无门限不授权、数据校验、固定空间及实际Linux IPC故障。
开发机WSL没有PATH中的python3，使用既有`software/tests/run_stream_python.sh`运行，未更改系统环境。

独立只读复核通过：10,000次事件对照中原许可状态逐步一致；另10,000次邮箱发布中，
移除诊断字段后的外层事件与原合并规则一致。复核发现的负时间诊断问题已修复并复测。

更新包沿用soundsight_enrollment_update.zip；完整soundsight_pynq_3d_speaker.zip也更新。
真实解压安装验证、包内测试结果另见unpacked-tests.log；私人模板和设置保留，原bit/HWH与收件记录一致。
没有执行板测或驱动舵机，板端实际显示效果待用户复测。测试临时解压目录在检查后自动清理。
