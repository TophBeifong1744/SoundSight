# Reliaze构建接收与独立PCM测试包

用户目标：对齐当前工程/Servo交付包，补齐下一步四麦PCM接收；新包独立，不覆盖Servo。

## 输入与核查

- 外部工程：`F:/AMD/work/SoundSight_PS_Reliaze`，只读。bit内部时间2026-10-24 10:34:34，用户导出`pl_ps_reliaze.xsa`。
- 原交付：`release/output/soundsight_pynq_servo.zip`，62文件；软件与本轮开始时工作区一致，包含C桥bit18修复；硬件为旧Servo，不含audio_capture/DMA。
- 新包：`release/output/soundsight_pynq_pcm.zip`，独立根目录`SoundSight_PYNQ_PCM`；原包未改。
- 新bit、HWH与XSA内文件逐字节一致，外部登记16份更新RTL与先前仿真候选一致；产物摘要见receipt.json，包中SOURCE.json/FILES.sha256.json绑定交付内容。

资源与时序取用户实际报告，不是估算：WNS +0.165ns、WHS +0.036ns、WPWS +2.208ns，三类失败端点0，LUT17398/53200、FF19351/106400、BRAM32/140、DSP41/220。36,090条完全布线网络，布线错误0。
最紧路径为结果FIFO写地址至分布式RAM，9.474ns数据路径中9.126ns是布线延迟。T15/W15、Bank34、LVCMOS33保持。

## 补出的报告与未关闭项

`report_existing.tcl`只open_checkpoint既有routed DCP，输出report_cdc和层级资源；没有synth/impl/write_bitstream/硬件操作。
实际命令参数、Vivado版本与路径见report-existing.log；可由Vivado batch传入DCP和输出目录复现。

首次失败是沙箱无法发现厂商appinit包，不是设计失败；原文保留report-initial-failure.log。
随后仅对当前Tcl进程补充安装目录中的auto_path，未修改用户TclStore，报告成功。用户TclStore初始化Critical Warning仍在日志中，与设计CDC条目分开表述。

- CDC-10 Critical 3：`audio_capture/.../drain_sync`、`audio_capture/.../run_sync`、`compute/.../enable_sync`；同步器前有组合逻辑，报告源涉及bus_io_reset。未自动豁免。
- CDC-15 Warning 1252：主要在官方XPM FIFO数据路径；仍需结合握手/复位/约束核对，不以工具识别为Warning即宣布失败或通过。
- DRC REQP-1839/1840异步RAM控制、LUTAR-1互联异步复位、PDCN-1569厂商互联LUT项保留；无DRC Error不等于全部关闭。
- 原时序check_timing计数全0，但详细Unconstrained Path表仍有PS复位/IP内部路径，不能简化成“所有路径均已审查”。

## 软件变更与判据

新增pcm_capture.py/run_pcm.py，短入口在board_tools.py；复用VolumeClient/原锁帧消费和共用进程锁，无动作ARM/COMMIT。
沿用PYNQ环境/时钟处理，增加独立HWH模块/参数/地址检查。Simple S2MM仅轮询，不实例化会自动启动DMA的驱动。
检查实际8224字节、包头、epoch、连续包号/采样起点、S24符号扩展；同时消费原定位槽，元数据在锁帧期间读取。
停止/超时先撤动作许可与停采，保存复位前错误/尾部，确认DMA reset完成且Halted才释放内存。
若确认失败，保留进程/缓冲等待板断电，绝不声称安全释放或自动重启；正常停止允许明确记录不完整尾部。
采集期间仅RAM保存，结束输出packets.bin、four_mic.wav、result.json；WAV未归一化，PASS不等于声学/声纹通过。

发现并修正原方案文档把audio错误位写成[23:16]的问题：实际RTL为[15:8]；此次只改文档/软件，RTL和bit保持不变。
窗口编号跨启停保持，采样编号按会话从0起，软件不把两者混为相同计数。

## 验证与边界

定向PC测试和包内复测的命令/原件见tests.json及logs；包括真实包格式边界、错误注入、只读检查无写、DMA所有权/缓存可见性/停止、旧入口回归和包CRC/hash。
最终解压包7组共90项通过：PCM19、board_tools15、serial_english3、manual8、filter13、normal17、volume15；Python3.8语法检查通过。ZIP共73文件、71项载荷摘要核对通过，原Servo包仍795482字节、62文件。
这都是作者自测/PC假硬件验证，不是独立评审、ARM运行、CDC签核或实板音频通过。
新包当前用于下一步prepare/pcm-check；持续录音前处理CDC/RDC未关闭项，声纹登记/识别和转向留后续阶段。

已删除本任务的codex_out/pcm-package-check、simulation/work/pcm-receipt（只读报告会话缓存）及误建的空simulation/work/simulation目录；codex_out已为空并移除。正式报告、成功/失败日志、receipt与新包分别归入此目录和release/output。原Servo包及外部Vivado工程未写入；未删除他人仿真结果。
