# 当前PS定位结果：满槽时保留较新的未锁结果

2026-10-30。用户授权在PS处理不及时的时候丢弃过时定位结果，避免仅因两个结果槽占满而停止整个采集。本变更适用于当前带PCM的三维PL+PS工程；尚未生成新位流或完成板测。

本策略不是无损记录。普通运行与debug调试都可能跳过旧定位帧，DROP_COUNT和序号间断会如实记录；它不改变PCM音频DMA/FIFO、声纹评分、求解格式或舵机许可保护。不能把定位队列不再报满解释成所有采集与声纹堵塞已解决。

## 槽位规则

两槽仍只有FREE、READY、LOCKED三个状态。写入整帧时，六对数据、音量、PCM关联元数据、标志和完整32位序号一起更新。

1. 先处理本拍的ACQUIRE、RELEASE或CONSUME，再放入新帧。有FREE时优先使用FREE，不丢已有帧。
2. 无FREE且允许替换时，只淘汰序号最小的READY。LOCKED始终保持不变；同拍ACQUIRE刚锁住的帧也受保护。
3. RELEASE已经明确交回所有权，因此其变成READY的旧帧可在同拍被替换。CONSUME释放出的FREE优先接新帧。
4. 每替换一个READY，DROP_COUNT饱和加1，gap置1并保持；不会为此产生overflow_pulse，也不会仅因此置FAULT 0x08。
5. 如果没有任何可替换槽、命令非法，或者停止/故障收尾期间不允许替换，满槽仍拒绝新帧并按原规则计丢帧、报溢出。已有记录不被覆盖。FREE存在时，取消尾帧仍可正常存入FREE。

示例：PS锁着445，446处于READY，正常采集产生447。新策略保留445，把446整帧替换为447，DROP_COUNT增加1；PS之后消费445，再锁到447。序号间断真实可见，不能伪造成连续帧。没有锁帧、两个READY都满时，保留其中较新的一帧并写入最新帧；ACQUIRE继续锁现存最老帧，不改变其所有权协议。

## 何时允许替换

仅在`AUDIO_ENABLE=1`的PS实例、真实采集run_enable有效、本拍为真实非BIST特征且没有计算排尾时，才可能替换。STOP请求同拍、host_stop、已锁存FAULT、本拍fault_events（包括源故障、格式/快照错误、取消标志等）立即撤销替换许可，不等下一拍FAULT寄存器更新。BIST和取消尾帧不能淘汰旧READY。

LR-001复核修正：事务到达拍还检查未知地址、写只读寄存器、非法字段/SYS组合，以及SNAP必须为0/1/2/4、RELEASE/CONSUME必须有锁。字段规则与原顺序写入共用，不因错误标志下一拍才出现而先淘汰旧记录；SNAP原有错误类型和时序保留。已待执行的ACQUIRE会纳入锁状态判断，正常PAIR_SELECT、合法动作及其他合法寄存器访问不一概禁止替换。同拍非法SNAP、只读写入、未知地址读和无锁RELEASE已纳入真实寄存器层仿真。

普通总线复位仍保留已保存快照；冷复位才清队列与统计。正常锁帧关联、原始麦对资格、完整序号检查、同帧防重放和动作租约均未放宽。

## 硬件识别与兼容

当前PS地址空间新增只读寄存器，地址是`ps_link`基址内的字节偏移：

| 偏移 | 名称 | 含义 |
|---|---|---|
| 0x98 | LATEST_RESULT_CAP | `0x4C415431`，ASCII `LAT1`，表示本策略存在 |

仅`AUDIO_ENABLE=1`时该地址有效；没有扩展旧7位PS地址宽度，不改变0x6C ABI、原STATUS保留位或冻结头。旧位流没有LAT1，不能仅安装PS软件就认为硬件已更新；探测旧硬件前先核其地址空间，非法访问仍沿原规则报错。

共享`ss_snapshot_queue`新增`LATEST_WINS`参数（默认0）和`replace_enable`输入。历史SPI和不带PCM的旧PS保持原来“满时丢新并报错”的行为；只有当前带PCM的PS显式启用参数。默认参数0时替换输入不参与逻辑，不改变历史接口字段。测试中使用`.*`实例化队列的用例需显式连接此输入；产品中的历史SPI使用命名端口，可维持参数0。

PS滤波器遇到序号间断应继续重置当前累计窗口、撤销旧目标，下一组合格再提交；其他FAULT继续停止。无需把FAULT 0x08改成可忽略错误，因为主动淘汰READY本身不会产生它。

由于LOCKED不会被覆盖，PS长时间停顿后仍可能持有旧锁帧。配套PS增量沿用750ms方向新鲜度预算，从开始读取快照计时，在ARM及COMMIT前复查；超时会清空角度窗口、撤销目标、处理并释放记录，重新积累一组合格结果。2026-10-30按用户新决定，声纹许可独立采用score_ttl_v2，低音量不再清除许可；当前方向仍受音量门限和上述750ms保护，旧角度不能用于转动。

这个软件检查不是采样到PWM的硬实时上界：它不覆盖读帧前的排队时间，Linux也可能在检查与MMIO写之间被抢占。硬件原有动作租约和STOP仍保留。此次没有增加硬件锁帧超时强制覆盖，以免PS读取一半时混入另一帧。

## 更新用户工程副本

先由用户自行复制当前三维工程，在Vivado中打开这个仓库外副本，然后执行：

```tcl
source {<SoundSight所在位置>/project/bd/update_ps_latest_result.tcl}
```

脚本要求xc7z020clg400-2、当前3D/PCM的ps_link配置以及已经复制到副本内的两份唯一登记源。它备份并替换`ss_snapshot_queue.sv`和`ss_ps_control_regs.sv`，刷新现有module reference、验证BD并生成原有输出产物；不重新套用旧BD配置，不改T15/W16、100MHz/61.44MHz、DDR/MIO、地址段或其他源码。备份和登记原路径放该副本`handoff/before_latest_result_*`，输出给出具体位置。

模块刷新后重新核对AUDIO_ENABLE、DUAL_AXIS_ENABLE、LEVEL_ENABLE和CLK_FREQ_HZ；若刷新丢失参数，明确停止并保留备份，不打印完成或继续生成输出。

看到`LATEST_RESULT_PREPARED`之后，由用户点击综合、实现和生成位流。新bit与匹配HWH仍需按现有打包入口交接；本脚本不创建副本、不启动综合/实现/位流生成或硬件动作。

## 安装PS配套增量

本次软件包是`release/output/soundsight_latest_result_update.zip`，不是包含新位流的完整SD包。复制到SD启动分区，板子启动后，停止当前运行程序再输入：

```sh
python3 -m zipfile -e /boot/soundsight_latest_result_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_latest_result_update/install.py --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -B software/tests/test_latest_result.py -v
```

安装仅更新三维客户端、专项测试和说明，自动备份被替换文件；用户声纹、门限、帧数、舵机标定和历史日志保持原样，不加载FPGA。该软件也可先装在旧位流上，但旧位流的队列仍会满。

用户完成新候选综合、实现、位流及XSA/handoff导出后，再收件形成匹配bit/HWH的完整SD包。不要将当前旧的完整SD包误当成LAT1硬件。新包加载后应核对0x98为LAT1，先关轴运行声纹联合负载，再测转动。原短命令保持不变：

```sh
sudo sh soundsight-3d.sh speaker --axes off --seconds 30
```

验收关注：PS有意慢取时，READY旧帧可跳过、DROPS可增加；这种主动替换本身不产生FAULT 0x08，LOCKED整帧不变。停止/真实故障仍须终结；其他PCM/DMA、声纹IPC或算法故障不被本策略掩盖。

## 本批验证边界

真实XSim：最新队列427项、PS接合76项、旧队列随机1500步/10047项、旧PS852项、双轴319254项检查通过。Linux离线：新鲜度/撤许可5项、三维21项、声纹跟随23项通过。Tcl离线命令模型4项通过；这不是实际Vivado BD Validate结果。

测试覆盖满槽替换、LOCKED完整数据保护、同拍所有权命令、计数饱和、停止/源故障/非法事务/BIST禁止替换、FREE接收取消尾，以及过期帧不重启动作。具体命令、失败事实与日志见[evidence/ps-latest-result-20261030](evidence/ps-latest-result-20261030/README.md)。

新候选综合、实现、STA和板测尚未进行；旧W16位流时序不能直接沿用。新RTL增加READY选择和门控路径，其资源与时序必须由用户后续实际报告确认。
