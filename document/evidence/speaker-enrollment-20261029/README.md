# 单段板端声纹录入：实现与验证

后续用户实板进展：5秒单段录入成功，已取得本人关轴评分；3秒录入失败事实、全部三次评分和未完成项见[板测回报](board-result.md)。下方主机测试范围保留当时状态。

用户最终范围：只录一段、缩短录音，保存多个目标并切换，录入不驱动舵机；先测分数再显式开启声纹双轴跟随。实现默认3秒，可设2～10秒，没有自动录三段，也没有自动启动跟随。

## 本批改动

- `software/ps/speaker_enrollment.py`：复用既有PCM采集、STOP、DMA排尾/缓冲生命周期；全程持有现有PS所有者锁。双轴仅revoke及等排尾，没有ARM/COMMIT。CPU推理在DMA停止后运行，独立进程组180秒上限，取消/失败保留录音。
- 同一CH0和CP1/VF1原生前端，按不重叠1秒窗筛选活动语音覆盖≥80%的窗，最多均匀选3窗，不按相似分数挑窗；各窗向量L2归一化后均值并再归一化。至少1个可用窗，削顶超过1%拒绝。音量跟随门限未用于绕过录入质量检查。
- `speaker_targets.py`：新增schema2档案，原P01/P02保留。录入不改变selector，不覆盖重名；目标选择先清许可门限。切换与跟随启动在同一锁下读完整模板/门限组合。
- 板端短入口、共享采集回调、模板导入及文档同步；RTL/BD/bit/HWH未改。T15/W16不变。

## 验证与边界

Linux主机5组共82项通过，原日志在本目录：录入18、声纹许可23、进程9、PCM采集19、短命令13。重点包括中断/失败不发布模板、旧资料不变、重名/非法ID拒绝、模型绑定不符拒绝、导入和选择清门限、跟随配置在锁内读取、仅撤双轴、静音拒绝及原采集故障排尾。

`native.json`：实际CP1/VF1模型，历史epoch26 PCM的两个3秒片段，主机原生后端提取与独立组合的均值向量最大误差0；保存后在线模板加载一致；全零PCM被拒绝。两段相似分数0.5471873946，只是该历史输入的回放结果，不是准确率，也说明0.65不能当通用合格线。真实新用户录入、ARM耗时及本人/他人分布未测。

`package.json`和`relocated-tests.log`：完整包与小更新包ZIP检查通过；隔离解压安装后18项再通过；7份合成个人配置/档案/日志逐字节不变，被替换程序有备份；bit/HWH与既有收件原件相符。私有真实模板、语音不进入本次公开测试或报告；完整包仍含原有私有基线资产，只私下交付。

独立只读审查上下文 `/root/enrollment_review`，没有参与产品/测试写入。发现并修复：①跟随启动锁外读旧门限、锁内加载新模板的竞态；②无selector目录导入新人时可能继承旧门限。两个问题均已加回归并由原审查上下文增量确认。复核范围为软件逻辑，未代替实板测试。

## 复现入口

在有项目主机Python/ORT依赖的Linux环境：

```sh
sh software/tests/check_speaker_enrollment.sh
sh software/tests/build_speaker_live_host.sh
sh software/tests/run_stream_python.sh -B software/tests/test_speaker_enrollment_native.py
sh software/tests/run_stream_python.sh -B tools/check_speaker_enrollment_package.py
```

原生测试从现有私有完整ZIP读取模型及epoch26 PCM，必须拥有这些既有输入；输出限于忽略的 `software/build/enrollment-validation`，不对板端发起操作。该测试拒绝覆盖已有同名测试工作目录。最终有效代码在正式software/tools目录，说明在document，未创建codex_out。任务结束清理本次生成的模型解压副本、合成私有模板与主机测试二进制，保留本目录结果；既有私有交接包和历史失败原件不删。

板端操作见[短录入说明](../../pynq-speaker-enrollment.md)。本批不包含新上板、执行器动作、综合或实现。
