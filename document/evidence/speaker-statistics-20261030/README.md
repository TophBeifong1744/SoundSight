# 可选整轮声纹统计验证

用户要求：显式开启，统计整轮成功计算中的过线次数和平均/最大耗时，结束后保存，并有短命令查看上一次。默认正常运行不新增逐帧写盘。

## 实现及边界

- 新增`software/ps/speaker_statistics.py`，只保留成功次数、通过次数、耗时和、最大值；平均值结束时计算。推理线程在生成结果时更新，早于有限32条明细截断及IPC合并，不从日志末尾推算全程统计。
- `speaker --speaker-stats`显式启用，经运行入口和ProcessSpeaker配置传到FollowSpeaker；默认None，不创建累计器。沿用现有compute_seconds，不增加热路径计时、文件操作、锁或线程。
- 有效分数及有效非负耗时才计数；无分数、无效数值、抛异常的计算不计。过线判定为score>=本轮已锁定门限，包含恰好相等。未配置门限时通过次数为null；没有成功计算时均值/最大值为null，不伪造0秒。
- 成功计算和授权、转动次数不同。统计包括本轮正常关闭时完成的尾部推理；发生真实采集故障仍标FAIL，统计不能改变会话状态或转动许可。
- 结束后随原会话JSON保存`speaker_worker.statistics`，再原子替换单个`logs/speaker-last-stats.json`。后续未启用统计的运行写DISABLED，防止展示旧数字。没有子进程汇总写UNAVAILABLE。
- `sudo sh soundsight-3d.sh speaker-stats`纯文件读取，不导入PYNQ、不检查HWH、不触碰硬件；固定最新摘要避免板端日期回退选错。没有新版记录时提示NO_SAVED_SESSION。
- 不改RTL、BD、bit/HWH、声纹模型、模板、门限、TTL或音量/角度/轴保护。

## 运行命令及结果

```sh
python3 -B tools/check_speaker_statistics.py
python3 -B tools/check_latest_sd_package.py --evidence document/evidence/speaker-statistics-20261030
```

开发机使用已有WSL Python入口`sh software/tests/run_stream_python.sh -B ...`运行同一脚本，不修改系统环境。

源码侧91项通过：新增统计9、实际短启动器13、TTL/联合27、显示7、旧角度保护5、进程通信9、三维控制21。完整包解压后87项通过（统计9、TTL27、显示7、角度5、三维21、录入18），两组有重叠，不相加声称独立用例。

定向输入/预期：100次成功计算中60次达到含边界的门限，前50次耗时1秒、后50次3秒；得到成功100、通过60、总200秒、平均2秒、最大3秒。NaN/无分数/越界/非法耗时不增加分母。100000次更新后字段和结构大小不变，禁止open/fsync的上下文中累计成功。真实推理入口开启前后输出分数和许可字段相同；错误形状推理不计数，finish汇总含累计值。

持久化/查看覆盖：无记录、未开启、零成功、无门限、真实故障标识、子进程结果缺失、日期回退、原子替换失败保留旧文件，以及查询入口禁止硬件检查。

增量包真实解压安装通过，旧源码备份可读，4份模拟私人文件保留，旧门限0.45/TTL10秒配置继续可用，bit/HWH未变。完整包检查6份私人文件保留、包内源码与仓库相符、bit/HWH与原收件相同。结果见tests.json、increment-check.json、sd-package-check.json及对应日志。

本次未执行Vivado、下载、复位、板端运行或舵机动作；新统计的真实ARM板端验证仍待用户复测。测试临时目录自动清理，未创建codex_out，未提交或推送Git。
