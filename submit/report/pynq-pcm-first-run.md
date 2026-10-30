# 四麦PCM独立测试包：沿用现有PYNQ环境

后续：已有[CDC修复后的新包](pynq-pcm-cdc-first-run.md)，原3条Critical已消除。本文及旧ZIP保留为修复前历史版本，请按新包说明继续。

日期：2026-10-24。包名 `soundsight_pynq_pcm.zip`，解压根目录 `SoundSight_PYNQ_PCM`。
原 `soundsight_pynq_servo.zip` 和板端 `SoundSight_PYNQ_Servo` 保留，不覆盖。

## 当前进度

- 已完成：原PYNQ环境导入/加载位流、ARM求解、旧版采集和方向计算；不从安装PYNQ重新开始。
- 已完成：Reliaze四麦PCM硬件候选的定向仿真、用户综合/实现/生成bit，bit/HWH与XSA逐字节匹配。
- 本包补齐：新硬件、最新PS兼容修复、只读音频检查、有限包数DMA接收、四通道24位WAV、原始包、同帧定位时间记录、超时/错误退出和STOP处理。
- 尚未完成：本组合ARM运行、真实四麦包连续性/通道试听、连续接收调度性能、声纹登记识别、声纹驱动转向、独立评审。

实际布线后WNS +0.165ns、WHS +0.036ns、WPWS +2.208ns，三类失败端点均0；
LUT 32.70%、寄存器18.19%、BRAM 22.86%、DSP 18.64%。时序最紧处是定位结果跨域FIFO的写地址布线。
DRC无Error，但音频RAM异步控制、官方互联复位/LUT警告尚未完成逐项关闭。
本次从同一布线检查点补出CDC报告：CDC-10 Critical 3条，CDC-15 Warning 1252条。
3条分别到达音频 `drain_sync`、`run_sync` 和计算模块 `enable_sync`，均涉及同步器前的组合逻辑；
CDC-15主要位于官方XPM异步FIFO。没有把这些条目自动豁免，不能标记CDC/RDC通过。
这些结果不代表真实音频或动作验证通过；本次仅做无动作诊断。

## 安装一次

使用原SD/PYNQ系统，不替换BOOT文件。把新ZIP放到SD可见分区根目录。
保留原Servo目录与日志；正常关机断电搬运SD。此次从新启动、尚未加载旧overlay的状态开始，避免同名bit路径缓存和运行中覆盖。

板端执行（串口一次发一整行）：

```sh
sudo python3 -m zipfile -e /boot/soundsight_pynq_pcm.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_PCM
sudo sh software/ps/build_solver.sh
sudo sh soundsight.sh prepare
```

新目录的C库重新编译，包含原先STATUS bit18的兼容修复；不是重装PYNQ。
prepare沿用旧系统已确认的时钟处理：实际PS参考33.333333MHz，FCLK0设为100MHz；
已加载本包则只检查，检测到其他overlay则拒绝切换，保留旧状态。
个人门限和机械配置不从旧目录自动复制；PCM测试不需要它们，也不提供动作许可。
不要同时启动旧Servo程序；所有新旧程序共用进程锁。

## 第一步：只检查接口

```sh
sudo sh soundsight.sh pcm-check
```

预期打印 `PCM_INTERFACE_OK=1 NO_CAPTURE=1 SERVO=OFF`，音频48000Hz、4通道、每包8224字节。
此命令不启动DMA/录音，不清故障，不自动下载。先把这一步的完整输出返回。

## 后续采集入口：待CDC问题处理后执行

当前下一步停在上面的只读接口检查；以下接收程序已经补齐并做PC测试，但新组合尚未板测。
CDC问题确认/处理并核对相应硬件后，先运行：

```sh
sudo sh soundsight.sh pcm --blocks 1
```

一包512组四麦采样，约10.67ms。只验证完整传输和包格式，不能靠这么短的声音判断声纹或声学质量。
通过后再执行：

```sh
sudo sh soundsight.sh pcm --blocks 256
```

目标约2.73秒，最大1024包约10.92秒；结束时还会排出已经封存的完整包，因此实际包数可以稍多。
录音期间正常说话，保持声源条件稳定。测试始终无动作，不运行声纹模型。

每轮保存到新的 `logs/pcm-*`：

- `result.json`：PASS/FAIL、会话号、包号/采样编号、定位原始帧和时间元数据、四路幅度、停止前硬件错误、DMA停止结果。
- `packets.bin`：实际收到的包，含32字节包头；异常完整包也保留。
- `four_mic.wav`：通过格式验证的四路24位48kHz录音，不自动归一化；失败时只是部分录音，须结合JSON，不以WAV存在判断成功。

PASS只表示本次软件检查的包格式/编号/停止条件通过，不等于麦克风物理编号、声学质量或声纹正确。
正常停止可能留下不足512组的尾部，JSON明确记为 `partial_tail`，不会补零伪造完整包。
1包通常没有完整定位窗；较长录音才检查有效方向窗的epoch、1024点长度与512点步进。
窗口编号跨启停保留，采样编号在新会话重启；不能把窗口编号当包号。

程序每包轮询有0.5秒超时，接收时只存RAM且持续消费定位槽，停止后再写SD。
Linux调度抖动超过FIFO余量仍可能失败；失败会显式STOP，保存错误，不掩盖丢样或自动重试。
如提示旧帧/旧故障，保留日志后按已有drain流程处理，不盲目清全部故障；音频故障先返回结果诊断。
若出现 `DMA_NOT_HALTED`，程序保留DMA缓冲和所有权等待，避免硬件仍在写时释放内存；
此异常下先给板断电，不能强杀程序后继续用同一硬件状态。

`pcm_epoch.local.json`保存会话计数，勿与日志一起随意删掉；更新包不包含/覆盖这个本地文件。
恢复旧版时停止并保留结果，重启后从原Servo目录prepare；新旧目录不能热切换。

## 接口核对依据

本轮发现旧方案把音频状态错误位写成[23:16]；实际已仿真/构建RTL为[15:8]，现按硬件修正文档和软件，RTL不变。
DMA完成使用状态及实际接收字节数检查，缓冲先确认停止再释放；依据
[AMD PG021状态寄存器](https://docs.amd.com/r/en-US/pg021_axi_dma/S2MM_DMASR-S2MM-DMA-Status-Register-Offset-34h)、
[长度寄存器](https://docs.amd.com/r/en-US/pg021_axi_dma/S2MM_LENGTH-S2MM-DMA-Buffer-Length-Register-Offset-58h)和
[PYNQ缓冲接口](https://pynq.readthedocs.io/en/latest/pynq_libraries/allocate.html)。
PC假寄存器/包测试不等同ARM或真实DMA运行；以板端实际输出接续。
