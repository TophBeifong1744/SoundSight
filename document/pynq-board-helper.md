# 板端一键准备、音量调整与日常调试

日常按步骤操作请看[三种模式完整命令：调参、手动标定和声音跟随](ps-manual-calibration.md)。

以下命令在板子串口Linux提示符执行，行尾LF。全部程序提示为英文，下面的默认调试命令关闭舵机。本工具用于四麦二维PL+PS音量版，不用于STM32工程。

水平轴接入候选另见[水平舵机操作](pynq-horizontal.md)：只有配套新bit/HWH、PYNQ机械配置及显式`run normal --horizontal-motion`一起使用才请求动作。`servo-config`仅保存零位、方向和范围；普通`run normal`、`run debug`及`prepare`不会主动开转台。

无声手动标定使用 `sudo sh soundsight.sh servo-angle 180 --seconds 5`，需要新手动控制位流及已保存的限位；先停止采集并处理旧帧。该命令显式启动水平轴，默认5秒后停止，与声音跟随分开。见[手动标定更新和保护](ps-manual-calibration.md)。

2026-10-22启动入口修正：硬件命令现在先实际验证`from pynq import Overlay, MMIO, Clocks`，通过才启动准备/采集程序；打印`PYTHON_EXE=`和`PYNQ_IMPORT_OK=1`，便于确认选中了哪个环境。默认先试板上`/usr/local/share/pynq-venv/bin/python3`，不可用时再验证PATH里的`python3`，不再仅凭文件可执行就使用。只在当前进程清除干扰解释器的`PYTHONHOME/PYTHONPATH`，不修改系统配置。帮助及门限文件操作不要求安装PYNQ。若旧环境变量`PYNQ_PYTHON`指向不可用的解释器（例如本板的`python3.8`），入口自动忽略它并继续探测；成功后子进程只继承已验证的选择。无需手动unset，也不改系统登录配置。

## 第一次安装本更新

电脑把最新`soundsight_normal_update.zip`覆盖复制到SD根目录。板子先正常停采集、关机、断电再拔插SD，不改BOOT.BIN、IMAGE.UB、boot.py等启动文件。

板子开机进入`xilinx@pynq:~$`后，先解压：

```sh
python3 -m zipfile -e /boot/soundsight_normal_update.zip /home/xilinx
```

再执行一次“安装 + 自动准备”：

```sh
sudo python3 /home/xilinx/soundsight_normal_update/install.py --destination /home/xilinx/SoundSight_PYNQ_Volume --prepare
```

需要sudo密码时只发送`xilinx`，不要把下一条命令当密码。安装器先备份旧源码；保留现有bit/HWH、C库、历史日志及本地音量设置。`--prepare`明确要求在安装后运行硬件准备，单独install不带它仍不会操作硬件。

这条命令依次做：正常模式/音量/英文提示/启动工具离线自测、加载ARM C库、检查HWH中的音量能力和动作禁用、设置XRT进程环境、读取真实PS参考时钟、按已验证的4×4分频下载位流、检查100MHz/复位/ID/ABI/旧槽/故障。它加载PL，不重刷SD启动镜像或Flash，不启动采集和舵机。

最后出现：

```text
READY_FOR_DEBUG MIN_LEVEL=7000 SERVO=OFF
```

才表示可以运行下一步。值可能是你之前保存的门限。中途非零退出或`STOP:`不能当作完成；不需要把每个成功步骤逐条贴回聊天。

## 以后每次开机

已经安装的文件仍在Linux根分区，不需要每次重解压，也不需要每次安装。

```sh
cd /home/xilinx/SoundSight_PYNQ_Volume
```

```sh
sudo sh soundsight.sh prepare
```

看到`READY_FOR_DEBUG`后，直接选正常或调试模式。若同一位流已经加载且状态正确，prepare只检查，不再次下载、不清旧帧。PYNQ的“已加载”来自其元数据，不是对电路内容的独立物理鉴定；工具额外检查ABI/时钟及设备状态。不要在程序运行中替换bit/HWH。

## 自由调整音量门限

查看当前保存值，不需要sudo：

```sh
sh soundsight.sh level
```

保存新值，例如5000：

```sh
sudo sh soundsight.sh level 5000
```

门限范围1～16777215，单位为去直流PCM平均绝对幅度计数。**越大越难通过、越小越容易通过**，不是分贝，也不是语音识别。默认7000沿用B的试调值，没有自动标定含义。值写到本机`settings.local.json`，重启及软件更新后继续使用，不进入Git。

先Ctrl+C结束当前采集，再修改门限，再开始新一轮；不在窗口中途换标准。修改参数不需要prepare、不需要重新加载bit。

也可只对这一轮试用新值，不改保存值：

```sh
sudo sh soundsight.sh run normal --frames 1000 --min-level 6000
```

建议先观察安静时的`LEVEL`范围，再用固定位置/音量的持续声源观察。选择能挡住背景又能通过目标声源的值；其他筛选参数先不动，避免多项同时变化。低音量对应`NO_OUTPUT: LOW_VOLUME`；音量足够但`INSUFFICIENT_CONSENSUS`属于角度不一致，不靠降低音量门限强行解决。

## 调整一组多少帧、多少个有效角度

查看当前设置（无需sudo或加载FPGA）：

```sh
sh soundsight.sh filter
```

保存设置，例如每组10帧，最低6个有效角度：

```sh
sudo sh soundsight.sh filter 10 6
```

恢复默认值：

```sh
sudo sh soundsight.sh filter 20 12
```

第一个数是**一组总帧数**，不是有效帧数；第二个数同时是**最低有效角度数、剔除离群角度后的最低保留数**，这与原来12的两处用途一致。满足`1 <= 最低有效数 <= 总帧数 <= 100`才允许保存。默认20/12不变，仍用圆周中心±10°筛选、至少三分之二有效角度一致、圆周平均及3°死区；低音量/断序等清窗规则不变。窗口更短通常响应更快但统计更少；更长的窗口增加等待和计算量，新参数的板端效果需实际观察。

先停止运行再设置，下次run生效；正常/调试模式共用设置。写入已有`settings.local.json`，与音量门限互不覆盖，旧版只有min_level的文件自动使用20/12默认值。仅修改PS软件，不需要重新生成bit。

只对某一轮临时调整，不改保存值：

```sh
sudo sh soundsight.sh run normal --window-frames 10 --min-valid 6
```

注意：`--frames 1000`是整轮采集总数，`--window-frames 10`才是一组的大小。两者独立。

## 看懂每半秒的英文提示

示例（示意数据，不是本板实测）：

```text
FRAME=3139 LEVEL=2804 NO_OUTPUT: COLLECTING WINDOW=7/20 VALID=5 MIN=12; LAST_GROUP=INSUFFICIENT_CONSENSUS@3132 VALID=15 KEEP=8 AGE=0.1s; LAST_CLEAR=LOW_VOLUME@3000 AGE=1.5s
```

- `WINDOW=7/20`：当前这一组已积累7帧，共需20帧；`VALID=5 MIN=12`：其中5个有效角度，最低要求12个。
- `LAST_GROUP`：最近**收满的一组**的结果。`INSUFFICIENT_VALID_ANGLES`表示有效角度不够，`INSUFFICIENT_CONSENSUS`表示筛选后不够集中，`ACCEPTED_UPDATED`表示通过并更新目标，`ACCEPTED_HELD_3DEG`表示通过但在3°死区内保持原目标。
- `KEEP`是最近一组筛选后保留的角度数；若有效数本就不足，未进入一致性筛选，KEEP为0。`@3132`是该组结束帧号；`AGE`是这条历史结果距现在的时间。
- `LAST_CLEAR`：最近一次清空窗口的原因、发生帧号及距现在时间。如`LOW_VOLUME`是低音量，`SEQUENCE_GAP`是断序，`SOLVER_ERROR`是求解接口错误；`NONE`表示本轮还没出现过。
- 最近组通过时可显示`TARGET=...deg(HISTORY)`，它始终标为历史结果。即使后来声音消失也保留这条诊断；**不能当作当前新有效方向或舵机指令**。当前无效仍显示`NO_OUTPUT`。

上一组结果和最近清空原因各只保留一条，不再因为半秒刷新刚好错过窗口结束帧而消失；串口仍不逐帧保存到SD。LAST_CLEAR保留的是最近事件，不表示每次打印都又清了一次。当前没有收到数据时仍显示等待/过期，不能把旧状态当作活跃采集。

## 直接运行

持续正常运行：

```sh
sudo sh soundsight.sh run normal
```

正常模式1000帧短测（完成自动停）：

```sh
sudo sh soundsight.sh run normal --frames 1000
```

保留详细逐帧日志的1000帧调试（默认即1000）：

```sh
sudo sh soundsight.sh run debug
```

例如改成3000帧：

```sh
sudo sh soundsight.sh run debug --frames 3000
```

可选BIST，不拿合成音量作声学标定：

```sh
sudo sh soundsight.sh run debug --mode bist-pass
```

```sh
sudo sh soundsight.sh run debug --mode bist-reject
```

工具自动选定bit配套HWH、保存的门限、无动作在线筛选，只有已确认且无旧槽时允许原STOP位0x40在启动时清除；其他故障一律保留。每次自动生成`logs/normal-...json`或`logs/debug-...jsonl`，无需手动删上轮文件。串口打印`OUTPUT=`完整位置。

正常模式每0.5秒尝试显示角度或无效原因，计算完成及时释放，不逐帧写SD，停止后才保存汇总。调试模式仍保存详细数据，SD高水位保护仍会触发，不能把正常模式新增当作旧积压问题已经修好。正常模式突然断电可能丢本轮尚未写出的汇总。

停止：发送真正Ctrl+C控制字符0x03，等正常停止回报和Linux提示符。然后可直接换模式或门限再次运行，不需重载位流。串口工具的“发送文本Ctrl+C”不是控制字符。

## 遇到提示自己处理

|提示|含义及下一步|
|---|---|
|`READY_FOR_DEBUG`|准备完成，直接run|
|`OVERLAY_ALREADY_LOADED=1 DOWNLOAD_SKIPPED=1`|同一位流已加载，继续检查；最终仍看READY|
|`NOT_PREPARED`|先执行prepare，不需要重解压|
|`OLD_FRAMES`|执行下方drain保存旧槽；不要重载bit抹掉证据|
|`Another PS capture process`或`DEVICE_ACTIVE`|原程序仍在运行或硬件未停止；先回原终端Ctrl+C，不并行启动|
|`NO_OUTPUT: LOW_VOLUME`|正在采集但音量低于门限；看LEVEL、声音条件及门限，不是程序卡死|
|`COLLECTING WINDOW=n/N`|当前组进度；结合LAST_GROUP与LAST_CLEAR判断是否上一组被拒绝或中途清空|
|`DEVICE_FAULT`、时钟/复位/ABI错误|保存状态和报错，停止新实验；不要扩大清错掩码或删除检查|
|`Another overlay is registered`|当前登记了另一工程，工具没有覆盖它；先保全旧实验，再确认切换工程，不能把重试当成清故障|
|`PYTHON_PROBE_FAILED=...`|该候选环境不能导入PYNQ；自动候选会继续尝试下一项，以最终结果为准|
|`No usable Python environment`|所有候选均失败，尚未启动硬件准备；保存所选路径和导入错误，按下方指定已知可用解释器，不重装镜像|
|`IGNORING_STALE_PYNQ_PYTHON=... AUTO_DETECT=1`|旧环境变量失效，脚本已自动忽略并继续选择；无需手动清除，最终看READY_FOR_DEBUG|
|`No such file`指向`/boot/...zip`|执行`ls -lah /boot`核对实际文件名，再解压|

只读查看状态（不会下载或清错）：

```sh
sudo sh soundsight.sh status
```

保存遗留帧（不启动新采集，不清故障）：

```sh
sudo sh soundsight.sh drain
```

若排空后只剩正常STOP标记0x40，可直接run；若还有0x08等其它故障，先保留日志和status结果再分析，不能用重启代替故障定位。

仅在自动探测失败时，显式指定本板已验证的环境进行排查（正常使用不需要这条长命令）：

```sh
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight.sh prepare
```

`PYNQ_PYTHON`指定的是一个可执行文件路径，不是带参数的命令串；它现在是优先候选，不是强制锁定；验证失败会显示提示并自动回退。只有全部候选都失败才停止，且不会启动硬件准备。若改用其他镜像，用该镜像实际能导入PYNQ的解释器路径。`PYTHON_EXE`可能随Python虚拟环境布局而变化，最终必须同时看到`PYNQ_IMPORT_OK=1`及`READY_FOR_DEBUG`。

查看刚完成的结果：串口已给出`OUTPUT=`路径，使用`cat`读取该JSON；详细JSONL可用`tail -n 3`查看结束记录。输出均保留于当前安装目录的`logs`，正常运行不覆盖以前结果。

## 实现与已测范围

`soundsight.sh`选择板端解释器、设置进程环境；`software/ps/board_tools.py`负责上述操作，复用已有normal/debug入口及唯一硬件所有者锁。没有系统自启动服务，没有更改全局时钟默认值或启动文件。水平轴版增加了显式动作入口，默认仍关闭；`servo-config`标定零位/转向/限位，`servo-geometry`配置固定阵列与转轴位置及可选已知声源距离，配置命令不访问硬件、不启用动作，详见[pynq-horizontal.md](pynq-horizontal.md)。仅用户运行prepare或安装时明确加--prepare，才会触发下载。

加载细节核对了[PYNQ 2.7官方Overlay实现](https://github.com/Xilinx/PYNQ/blob/v2.7.0/pynq/overlay.py)：先用download=False读取配套元数据，调整clock_dict后再download；不把is_loaded当成物理验收。失配/活动状态的处理与真实下载仍需本板验证。

主机离线证据见`document/evidence/pynq-board-helper-20261022`及`document/evidence/pynq-launcher-fix-20261022`。用户已回传：旧短入口离线自测和ARM库加载通过，但导入PYNQ失败；直接指定PYNQ解释器执行同一个board_tools.py prepare成功。本次修复短入口已做真实shell与Python的模拟环境测试，尚待用户在板端验证；随后现场输出明确显示`PYNQ_PYTHON=python3.8`覆盖导致导入失败；自动忽略失效覆盖的修正版及测试见`document/evidence/pynq-launcher-fix-20261022/stale-override`，新修正版短入口仍待板端确认。不把这些离线测试说成实板长稳通过。
