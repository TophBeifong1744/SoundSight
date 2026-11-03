# 方向筛选修复：板端离线检查回报

收件2026-11-03。原始串口输出见console.txt；该附件没有包含安装器回执，不能据此单独认定全部22份安装文件身份已核实。

用户在PYNQ上运行soundsight-3d.sh check，输出Python3.8、二维/三维C库构建完成：在线三维21项、纯声音7项、CF1/所有权16项均OK，THREE_D_OFFLINE_OK=1 HARDWARE_ACTIONS=0。

随后运行test_pcm_gap_filter.py，9项均OK；合成缺口对照old_groups=0、new_groups=9、bridged=47。合计53项板端离线测试通过。这是在板上运行合成/模型测试，不是53项真实采集/机械测试；0到9组也不是实麦效果或识别率。

侧边聊天的候选与源码仍在codex/screen-speaker-capture-fix独立工作树中，最新交付为soundsight_direction_filter_update.zip，包含CAPTURE_COOPERATIVE_V1和CF1_PCM_GAPS_V1。主聊天已核对包内清单、CRC、源码一致性和Python3.8语法；本记录不覆盖其132项PC验证。

下一步保持既有音量、筛选、目标、门限及TTL，停止屏幕服务并确认准备状态后，先运行60秒speaker axes off，保存原始speaker-3d摘要。重点核查采集错误、direction_diagnostics、合格方向组与评分；实麦效果仍待回传。
