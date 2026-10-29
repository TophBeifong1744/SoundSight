# PYNQ最新操作说明：录音、调参、转台与声纹测速

> 2026-10-29 引脚更正：当前双轴方案为水平 T15、垂直 W16。本文旧 W15 位流及板测描述仅对应历史版本，不能作为新接线依据；现行操作见 [三维双轴说明](pynq-three-d-dual-axis.md)。仓库现行脚本按 W16 检查，旧工程需先更正约束并重新实现。

**实麦CPU诊断包已准备（新板测待执行）：** 新完整包`soundsight_pynq_speaker_live_profile.zip`新增`sudo sh speaker-live-profile.sh 1`，在原实麦路径测声纹J墙钟/CPU及同期前端、算法协调、采集进程CPU，并累计DMA取包/重提交、定位快照获取/消费及IPC提交用时。原模型、PL、阈值、优先级与停止保护不变；默认命令不开诊断。9项定向、154项默认回归、开关各5种模拟生命周期、两段各938包/26次实际推理回放、独立只读复核及最终ZIP检查通过。该候选没有实板测速，计数开销也需实测。安装和命令见[实麦CPU说明](pynq-speaker-live-profile.md)，失败修正及证据见[验证记录](evidence/ps-speaker-live-profile-20261025/README.md)。

**CPU对照板测完成：** 同样三个1秒窗、18次数值一致。独立前/后均值1.086/1.092秒，前端并发1.597秒，比合并独立组增加46.64%；网络CPU量增加19.35%。调度等待计数全部不可读（null），不能算出等CPU的准确时间。并发前端未复现此前实麦约3.8秒耗时，下一步在真实采集路径加入同口径CPU/墙钟诊断，保留采集优先级和原保护。此次不接触硬件、不修改程序或ZIP，声纹实时性和匹配仍未验收。见[板端原值与解释](evidence/ps-speaker-profile-20261025/BOARD-PROFILE.md)。

**CPU对照诊断包已交付（板测待运行）：** 新完整包`soundsight_pynq_speaker_profile.zip`在opt1上增加`speaker-profile.sh check/bench`，原模型、ARM后端、bit/HWH和控制功能逐字节保留。复用epoch26三个实际1秒窗，按“独立推理→32ms前端并发→独立推理”记录进程CPU秒、墙钟、线程调度等待；没有DMA/寄存器/定位负载，不代替实麦复测。8项定向检查、主机三组9次和最终ZIP独立解压18次、ARM模拟3窗通过；板端CPU/等待尚未知。旧两人短窗证据重新核对，1秒本人仍有误拒，1.5/2秒改善但有不确定，阈值未调。旧ZIP不覆盖，安装与命令见[CPU测速说明](pynq-speaker-profile.md)，过程见[验证记录](evidence/ps-speaker-profile-20261025/README.md)。

**最新PS opt1：** 完整独立包`soundsight_pynq_speaker_live_opt.zip`增加等价前处理优化、C实麦转换、缓冲区复用和合并推理调用，继续保留rx3接收隔离、同一bit/HWH及原控制入口。安装目录不改，旧包不覆盖。更新后先`sh speaker-opt.sh bench`做包内原录音新旧后端对照；该命令不访问硬件、不启动转台。板端速度和真实采集尚待测，见[opt1操作说明](pynq-speaker-opt.md)。

**最新rx3候选：** 将采集与Python声纹协调分成两个进程，避免共享解释器锁；同名ZIP覆盖更新，保留位流、原控制功能、个人参数和日志。先确认`revision=rx3`及`SPEAKER_PROCESS_READY=1`，再做正常音量本人单人测试；speaker始终不开转台。离线回归/原录音回放通过不等于实板溢出已修好，仍待复测。见[操作说明](pynq-speaker-live.md)及[rx3证据](evidence/ps-speaker-live-rx3-20261025/README.md)。以下rx2/rx1为历史。

**rx2更新：** rx1的speaker仍报快照溢出，但普通纯采集和CPU0固定纯采集均PASS。rx2只将C前端移到CPU1，采集留在CPU0，推理继续低优先级。更新同名ZIP并覆盖解压后，确认SPEAKER_SCHEDULING中revision=rx2、frontend_cpus=[1]，再执行speaker --window 1；原参数/日志保留，修复效果待板测。见[rx2记录](evidence/ps-speaker-live-rx2-20261025/README.md)。下文rx1为历史。

**实麦接收修复rx1：** 按用户要求更新同名`soundsight_pynq_speaker_live.zip`。旧实麦曾出现硬件队列溢出，新版提前提交DMA并降低推理优先级，增加接收计时和停止前故障记录；真实修复效果待板测。保留旧logs和参数，按[同名覆盖步骤](pynq-speaker-live.md)关机断电重启后更新，显式使用`speaker --window 1`。不要仅把新ZIP复制到SD而不覆盖解压安装目录。

**连续回放已板测（2026-10-25）：** 默认bench已完成，无需重复。前端跟得上，但1.5/2秒窗推理结果全部超过当前2秒期限；1秒窗仅4次有效身份结果。接下来首次实麦显式运行`sudo sh soundsight.sh speaker --window 1`，替代下文首次用1.5秒的旧建议；旧包默认值未改。参见[板端结果与限制](evidence/ps-campplus-stream-board-20261025/README.md)。

**新增实麦入口（待板测）：** 独立`soundsight_pynq_speaker_live.zip`保留原PCM CDC位流及所有原控制入口，新增`sudo sh soundsight.sh speaker --window 1.5`，可改为1或2秒。默认采集约10秒，声纹测试不开转台。安装时先按[实麦操作说明](pynq-speaker-live.md)导入旧个人参数、构建原S1库、prepare及speaker-check；旧目录和日志保留。原自动追踪仍按声源方向工作，尚未由身份控制，不能与speaker同时运行。离线验证见[记录](evidence/ps-speaker-live-20261025/README.md)，真实麦克风和PS并发负载尚待验证。

**最新操作：PS连续回放包。** 将新的`soundsight_campplus_stream_armhf.zip`放到旧卡启动分区，按[连续处理操作说明](../software/ps/speaker_core/CAMPPLUS-STREAM.md)独立解压到`SoundSight_CAMPlus_Stream_ARMHF`，执行`sh campplus-stream.sh check`及`sh campplus-stream.sh bench`。默认比较1/1.5/2秒，两段已有录音各回放一次，不需说话、下载bit或开启转台。原短窗包保留。新包会报告替换旧候选、开始过旧、结果过期及前端积压；通过表示数值/调度检查通过，尚不证明识别可靠或实麦实时跟随。见[验证证据](evidence/ps-campplus-stream-armhf-20261025/README.md)。

**上一轮短窗状态（2026-10-25）：** 用户继续使用正常旧SD卡，`bench`、`bench fp32`、`full`规定对照均已完成，无需重复跑。部分INT8短窗比浮点少耗时4.07%～9.20%；优化后整段由16.824/15.082秒降到12.580/10.772秒，数值通过但尚未证明持续实时或可靠短窗识别。保留当前目录及`logs/short-bench-int8-58Ydef`、`logs/short-bench-fp32-BHbbOC`、`logs/short-full-int8-KaWWAz`。当时提出的连续VAD与有界窗口调度现已放入上方独立回放包；旧短窗包仍只做文件窗口评估。不烧录、不启动转台。见[补测结果](evidence/ps-campplus-short-board-20261025/FP32-FULL.md)及[现有文件测速命令](../software/ps/speaker_core/CAMPPLUS-SHORT.md)。

此前完整文件包默认pair实板四次参考检查通过，但10.923秒文件平均需16.824/15.082秒，尚不实时。见[原结果](evidence/ps-campplus-pipeline-board-20261025/README.md)。保留logs/pipeline-pair-mVlBln，后续C转换整段对照继续使用这份基线。

现有独立 `soundsight_campplus_pipeline_armhf.zip` 的复测、静音和全量命令仍见[完整文件链路操作说明](../software/ps/speaker_core/CAMPPLUS-PIPELINE.md)。默认本人和另一人各一段、各两遍，模型只加载一次，不需要说话或烧录。日常PCM、调参和转台命令不变。

新包独立目录为 `SoundSight_CAMPlus_Pipeline_ARMHF`，使用Python标准库和原ARM运行库，不需pip或安装PyTorch；不采集、不控制转台。旧核心/优化包与下方第3节保留用于历史对照，不能将其特征输入计时当作完整WAV耗时。静音与全部12段回归命令见新说明。

更新：2026-10-24。日常控制继续使用 `SoundSight_PYNQ_PCM_CDC`；原ECAPA测速目录 `SoundSight_Speaker_Core_ARMHF` 保留，本次另装 `SoundSight_CAMPlus_Core_ARMHF`。不需要重新刷系统或生成bit。

原ECAPA核心两次约9.06秒、127.438MiB，数值通过但速度偏慢。本次第3节改为CAM++新包测速命令；旧包无需重复安装或删除。见[轻模型评估](speaker-light-model-assessment.md)和[CAM++验证记录](evidence/ps-campplus-core-armhf-20261024/README.md)。

## 1. 两个包分别负责什么

| 功能 | PCM CDC程序 | 声纹核心测速包 |
|---|---|---|
| 加载FPGA、四麦采集、方向求解 | 有 | 无 |
| 音量门限、方向筛选参数 | 有 | 无 |
| 无声手动定角、机械标定 | 有 | 无 |
| 选择是否开启水平转台声音跟随 | 有，每次显式开启 | 无 |
| 保存四路PCM录音 | 有 | 无 |
| 对预先计算的特征运行声纹网络、测耗时/内存 | 无 | 有 |
| 实时判断是否本人并只跟随本人 | 尚未接入 | 尚未接入 |

**新声纹包是独立测速工具，不是替换旧程序的完整升级包。** 之前的重要操作继续从PCM CDC目录运行，不需要为了手动调参而换回旧Servo位流。普通声音跟随目前依据声音方向，不区分说话人。水平T15可控制，垂直W15仍不驱动。

已完成实板PCM录音及电脑声纹基线；ARM核心包已通过主机和ARM指令模拟验证，真实板端速度仍待本次运行确认。保留功能入口不等于本轮重新验收了所有机械行为。

## 2. SD卡旧包备份与清理

SD上的旧 `soundsight_pynq_servo.zip` 已独立备份到仓库：

`document/evidence/sd-servo-backup-20261024/soundsight_pynq_servo.zip`

原SD包与原电脑发布包内容不同。按用户明确要求，现已用SD版本覆盖 `release/output/soundsight_pynq_servo.zip`，被覆盖的电脑版本也另行保留。原卡、独立备份和覆盖后的发布文件SHA256一致，ZIP完整性检查通过，详见[备份记录](evidence/sd-servo-backup-20261024/README.md)。可以删除SD卡上的这份ZIP；备份安装ZIP不包含板端后来修改的个人参数或新增日志。此次覆盖不代表重新验收旧Servo包，当前推荐运行入口仍是PCM CDC。

SD上的 `BOOT.BIN`、`BOOT.SCR`、`IMAGE.UB`、`boot.py`、`REVISION` 全部保留。Windows看到的是启动分区；删除其中安装ZIP，不会删除Linux分区内已经解压的程序。

本次将 `release/output/soundsight_campplus_core_armhf.zip` 复制到SD根目录。取卡前正常关机、断电；复制后安全弹出。

## 3. 现在先做：CAM++声纹核心测速

**每个代码框只有一条命令。逐条发送，等提示符返回再发下一条，不复制提示符，不添加行尾反斜杠。**

先确认新ZIP：

```sh
ls -lh /boot/soundsight_campplus_core_armhf.zip
```

首次解压；已经存在目录时明确提示，不覆盖：

```sh
if [ -e /home/xilinx/SoundSight_CAMPlus_Core_ARMHF ]; then echo DIRECTORY_ALREADY_EXISTS; else unzip -q /boot/soundsight_campplus_core_armhf.zip -d /home/xilinx; fi
```

```sh
cd /home/xilinx/SoundSight_CAMPlus_Core_ARMHF
```

```sh
sh campplus-core.sh check
```

预期包含 `CORE_PACKAGE_OK=1`。检查失败就保留输出，不继续测速。若已有目录来源不确定，也先核对，不能把“目录存在”当成最新版本已安装。

```sh
sh campplus-core.sh bench
```

此时不需要说话，不需要sudo、不需要prepare或加载FPGA。先结束其他采集/跟随程序再测速，避免争用CPU影响结果；测速程序本身也不会替你关闭其他程序已经开启的转台。

程序对代表3.104秒语音的特征计算两次，整个测试最多180秒，超时先请求退出，5秒后仍未退出则强制结束。运行时可能暂时没有新输出，等待即可。

正常末尾：

```text
CORE_BENCH=PASS NOT_END_TO_END=1 MOTION_COMMANDS=0
```

把完整输出发回，重点是 `MODEL=CAMPPLUS`、`LOAD_SECONDS`、两次 `seconds`、`peak_rss_mib` 与最终PASS/FAIL。`MOTION_COMMANDS=0`只表示此程序不发动作指令，不是舵机状态测量。日志在该目录 `logs/campplus-XXXXXX/`；退出码124/137可能是超时/终止，不能当成功。默认两线程；通过后可用 `sh campplus-core.sh bench 1` 对照一线程，详细见[独立包说明](../software/ps/speaker_core/CAMPPLUS.md)。

## 4. 日常开机：回到原功能

以下操作都在PCM CDC目录。你已经安装、编译并成功录过音，不必重复解压或编译。

```sh
cd /home/xilinx/SoundSight_PYNQ_PCM_CDC
```

```sh
sudo sh soundsight.sh prepare
```

看到 `READY_FOR_DEBUG` 后，选择下面需要的模式。prepare不启用转台。同一会话只换模式或调参数，不必反复prepare。若提示已经加载另一套overlay，停止旧程序、保留日志并重启后从本目录准备，不热切换新旧位流。

## 5. 查看与调整参数

先Ctrl+C结束运行中的采集/跟随，等提示符返回。

查看音量门限：

```sh
sh soundsight.sh level
```

查看筛选窗口：

```sh
sh soundsight.sh filter
```

查看机械标定与限位：

```sh
sh soundsight.sh servo-config
```

查看安装位置补偿：

```sh
sh soundsight.sh servo-geometry
```

个人设置属于当前程序目录：`settings.local.json`保存音量/窗口，`horizontal.local.json`保存机械标定/位置参数。旧Servo目录里的参数不会自动带到PCM CDC目录；机械配置缺失时，先按以前已实测的数值配置，不用下方示例代替实际标定。不要覆盖现有有效配置。

以下是明确要修改时才执行的例子：把音量门限设为7000，把筛选恢复为20帧/至少12个有效角度。

```sh
sudo sh soundsight.sh level 7000
```

```sh
sudo sh soundsight.sh filter 20 12
```

修改保存后下次运行生效，重启保留，不自动启动动作。音量计数不是分贝；门限越大越难通过。`filter N M`要求 `1 <= M <= N <= 100`，还会检查方向一致性，不是有M个角度就一定输出。

## 6. 选择是否启动转台

### 只测角度，不转动

```sh
sudo sh soundsight.sh run normal
```

连续输出方向、音量和筛选状态。Ctrl+C结束。`LOW_VOLUME`表示音量不足；`WINDOW`是当前窗口进度；历史 `TARGET` 不等于当前有新方向。

### 无声手动定角

先查看并核对机械配置。配置格式为 `servo-config 前方角度 方向 最小角 最大角`。下面仅在机构已确认允许170～190°、前方为180°、方向为+1时使用：

```sh
sudo sh soundsight.sh servo-config 180 1 170 190
```

保存配置不会转动。以下命令会真正请求转到180°并保持PWM 5秒：

```sh
sudo sh soundsight.sh servo-angle 180 --seconds 5
```

不需要说话；180°是示例绝对目标，必须在已确认的机械范围内。目标限位不代表当前位置反馈，首次移动可能有较大行程。到时或Ctrl+C撤PWM；撤PWM不保证机构锁住。手动定角不受音量/筛选参数影响。

### 开启普通声音跟随

确认配置正确、无动作定位正常后：

```sh
sudo sh soundsight.sh run normal --horizontal-motion
```

这是显式开启水平转台；只有合格方向通过筛选后才更新。**目前会跟随合格声音，尚未按声纹选择本人。**

关闭：Ctrl+C停止，等提示符返回。之后想只看角度，重新运行不带 `--horizontal-motion` 的normal。没有永久“开启转台”开关，动作许可只对本次运行有效。

## 7. 四麦录音

结束其他模式，再检查接口：

```sh
sudo sh soundsight.sh pcm-check
```

预期 `PCM_INTERFACE_OK=1 NO_CAPTURE=1 SERVO=OFF`。

录约2.73秒：

```sh
sudo sh soundsight.sh pcm --blocks 256
```

或录约10.92秒：

```sh
sudo sh soundsight.sh pcm --blocks 1024
```

每次生成独立 `logs/pcm-*`，保存 `four_mic.wav`、`packets.bin` 和 `result.json`。这是不带动作的有限录音，不是在线声纹跟随；不要同时开normal/旧Servo或测速占用资源。`pcm_epoch.local.json`是会话计数文件，保留。

## 8. 停止、排查与关机

运行中先发送Ctrl+C控制字符；若串口工具以十六进制发送，则是 `03`。等提示符回来，再查看状态：

```sh
sudo sh soundsight.sh status
```

只有提示旧帧/旧槽需要排空时，保存排空结果：

```sh
sudo sh soundsight.sh drain
```

不要用反复清故障或重新下载位流绕过异常。普通STOP产生的 `fault=64`（0x40）由既有入口处理；其他故障保留完整输出。出现 `DMA_NOT_HALTED` 时按原PCM说明处理，不能强杀后直接继续采集。

旧 `python3.8` 探测可能先显示 `ModuleNotFoundError`，随后自动选择 `/usr/local/share/pynq-venv/bin/python3`。最终有 `PYNQ_IMPORT_OK=1` 才表示导入成功；不需要因前面那条探测信息重装PYNQ。

结束程序、保存日志后关机：

```sh
sudo poweroff
```

等待关机完成再断电取卡。不删除Linux目录内的个人设置、会话计数或尚未备份的日志。

## 9. 下一步与核对依据

现在先完成第3节，把实板测速结果发回。根据实际耗时/内存，再接完整音频预处理和身份判断，最后把身份判断与同一时刻的方向、动作许可连接起来。

本说明的PCM命令已对照当前发布ZIP内启动器和参数解析源码；启动器、手动控制、正常运行、板端工具、PCM入口五份文件与仓库一致。CAM++命令对应新独立测速包；原PCM和ECAPA包未覆盖。此前Servo ZIP按用户指定用SD版本覆盖，备份见第2节。本次没有操作硬件或改变板端参数。

- [CAM++核心包详细说明](../software/ps/speaker_core/CAMPPLUS.md)
- [手动标定与筛选细节](ps-manual-calibration.md)（旧文的安装目录为Servo；本轮日常目录以本文PCM CDC为准）
- [当前进度和验证边界](current-status.md)
