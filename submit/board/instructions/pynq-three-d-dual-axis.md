# 三维测角与双轴转台：本批操作入口

> 2026-10-29 W16新位流已收件并更新联合SD包。水平T15、垂直W16；安装及复测见 [W16更新说明](pynq-w16-update.md)。旧10月28日报告仅属旧候选。

> 2026-10-28 维护说明：当前 `run --axes` 已进入声纹许可路径，需要 B 的配套运行程序和资产；纯测角与无声手动标定独立可用。公开仓库与私有联合包的边界见 `document/rtl-3d-maintenance.md`。以下早期构建/测试记录按当时范围保留。

本批把三维测角、水平T15（0～360°）和垂直W16（0～220°）接成一个PL+PS候选。两轴按用户确认均为20ms周期、500～2500µs脉宽。PYNQ决定是否转动，默认只测角；手动标定与声音跟随分别运行。

**2026-10-28用户已生成3D位流：** 当前完整SD包与首次安装见[三维SD操作入口](pynq-three-d-sd.md)，不必再从旧PCM目录拼装软件依赖。原位流、HWH、工程和routed DCP未修改；只读补查已覆盖垂直输出20ns最大路径预算，余量+12.608ns，全局WNS+0.311ns、WHS+0.036ns。完整报告在`project/reports/ps_3d`；本节后面的新建工程步骤保留供后续重建使用，不要求为这次补查重新运行更新脚本或生成bit。

**明确工程基线：使用用户做声纹时的 `SoundSight_PS_Reliaze`。** 它包含四麦PCM、S2MM DMA、DDR通路和已修正的CDC控制。此前“PCM/Servo工程”的笼统称呼由本条替代，不从旧的 `SoundSight_PS_Servo` 或Volume工程退回重搭。实际XPR/BD/源文件只读核对记录见[Reliaze基线](../../data/evidence/ps-dual-axis-20261028/reliaze-base.json)。

## 这次改什么

- PL保留四麦采集、六对特征、音量与PCM/DMA通路；新增双轴原子配置/目标提交和独立输出保护。不在PL重做三维求解。
- PS使用独立三维C求解器，输出方位角、俯仰角和空间方向向量。不会把二维角度字段冒充俯仰角。
- 多帧筛选沿用20帧、至少12帧合格、10°一致性范围、至少2/3共识和3°死区的思路，但对三维单位向量计算，处理±180°和近天顶/地底的情况。正上/下方的水平方位不可观测，不能给水平轴编一个角度。
- 正常模式算完释放硬件槽，每0.5秒打印英文状态，只保留有界统计和最后必要诊断。调试模式显式限定1～1000帧，暂存RAM，停止后保存；断电可能丢失未保存数据。
- 声纹仍由B继续，现有声纹/PCM源码和入口保留。此入口与声纹采集共用设备所有权锁，不能同时运行两个采集程序；身份与三维实时融合尚未实现。
- 双轴控制寄存器、停止和复位语义见[接口合同](../../report/ps-dual-axis-interface.md)。

## 先更新你自己创建的Vivado副本

1. 自己复制 **`SoundSight_PS_Reliaze`** 工程（具备AUDIO_ENABLE=1、LEVEL_ENABLE=1、ACTUATOR_BOUND=1），例如命名为`SoundSight_PS_3D`，放在仓库外。确认当前打开的是这个副本。原Reliaze保留给声纹；复制与改名由用户完成，脚本不会代做。
2. 在Vivado Tcl Console执行下面命令，把路径换成你本机仓库位置：

```tcl
source {你的SoundSight仓库/project/bd/update_ps_dual_axis.tcl}
```

脚本不创建工程副本，也不启动综合、实现、下载。它先检查项目/引脚/源文件，再备份到工作工程内部，将所需手写源、约束与初始化文件复制进副本，更新ps_link引用、启用双轴、Validate BD并生成输出。T15/W16不变，不另加DMA、不重配PS或DDR。

已核对Reliaze的计算/采集/音频源码与当前候选兼容：本次只对PS接合层的三份现有RTL作功能更新，增加双轴控制器；其余沿用副本现有内容。PCM→DMA→HP0/DDR、音量、采样时间元数据与两根修正后的音频控制线保留。原工程有一份禁用的旧SPI ILA约束仍引用Servo目录，更新脚本会复制进新工程并保留禁用属性。无需先执行旧`update_ps_reliaze.tcl`或Servo更新脚本。

3. 出现`DUAL_AXIS_PREPARED`后，手动点击综合、实现；检查实现setup/hold、资源、DRC，再生成bit。已有旧版时序不能代替这一版。
4. 导出同一次候选的bit/HWH（如需也导出XSA及BD配方）。还没有这一步的实际产物时，不能把旧Servo/PCM bit当成双轴位流。

## PYNQ软件更新包

`release/output/soundsight_3d_software_update.zip`是增量软件包，**不含新bit/HWH**。它保留当前语音模型、录音、阈值和个人标定文件，不修改SD启动分区配置。安装器先备份同名文件，不自动编译、刷FPGA或转动。

先退出采集、声纹和转台程序。把ZIP放到SD可见分区，板端逐行执行；安装器持有同一设备锁，运行中不会热替换：

```sh
python3 -m zipfile -e /boot/soundsight_3d_software_update.zip /home/xilinx
sudo python3 /home/xilinx/soundsight_3d_software_update/install.py --destination /home/xilinx/你的当前PCM程序目录
cd /home/xilinx/你的当前PCM程序目录
```

新bit/HWH准备好后，把原文件备份，再将同候选文件分别放成该目录的`soundsight.bit`、`soundsight.hwh`。当前已加载其他候选时，按现有冷启动流程重新开始，不热覆盖正在运行的采集。后面的`prepare`由你显式执行：

```sh
sudo sh soundsight-3d.sh check
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh status
```

短入口自动寻找可用PYNQ Python，并处理旧环境变量；不改Linux自动启动。check在当前ARM编译三维与恢复用旧求解库并运行离线测试。prepare复用已有板端时钟、复位和位流准备流程，还核对双轴HWH/寄存器。成功不等于机械或声学验收。

## 先测角，完全不驱动转台

```sh
sudo sh soundsight-3d.sh level 7000
sudo sh soundsight-3d.sh filter 20 12
sudo sh soundsight-3d.sh run --frames 100
sudo sh soundsight-3d.sh run
```

7000只是此前调试值，按现场安静/发声level调整。filter两个数分别是每组总帧数、至少合格且属于一致方向的帧数；不需要凑满20个“有效帧”才结束一组。默认AXES=off。Ctrl+C停止并排尾，汇总在logs/three-d-*.json。每轮一个有界汇总文件，轮次多仍需用户管理旧文件。

短时保留所有帧：

```sh
sudo sh soundsight-3d.sh run --frames 100 --debug
```

输出AZIMUTH/ELEVATION为当前完成组的方位/俯仰角；收集中显示WINDOW=n/N、VALID、LAST_GROUP（历史）和最近清窗原因。音量不足、帧错误或组不合格没有当前有效输出。硬件故障停止，不把缺角度显示为0°。

## 单独无声标定

配置保存在`servo3d.local.json`，不会自动开启PWM。以下只是**操作示例，不是已标定结果**；请按安装方向调整。先用小范围：

```sh
sudo sh soundsight-3d.sh servo-config horizontal 180 1 170 190
sudo sh soundsight-3d.sh servo-config vertical 110 1 100 120
sudo sh soundsight-3d.sh manual --horizontal 185 --seconds 3
sudo sh soundsight-3d.sh manual --vertical 115 --seconds 3
sudo sh soundsight-3d.sh manual --horizontal 180 --vertical 110 --seconds 3
```

每轴四个配置值为“阵列前方/水平面对应舵机角度、方向±1、机械最小、机械最大”。水平以前方为零方位，垂直以水平面为零俯仰。手动命令直接给舵机角度，不要求声音合格，不启动采集。运行结束或Ctrl+C撤输出许可，当前高脉冲完整结束；没有机械到位反馈。

标定后可改更大范围，例如horizontal 180 1 0 360、vertical 110 1 0 220。360°位置舵机不是无限连续旋转机构；后方跨±180°时目标可能从一端跳到另一端，本批没有路径规划，初次跟随保持合适限位。

## 开启声音跟随

先退出测角或手动程序，再显式选择轴：

```sh
sudo sh soundsight-3d.sh run --axes horizontal
sudo sh soundsight-3d.sh run --axes vertical
sudo sh soundsight-3d.sh run --axes both
```

再次只测角，运行`sudo sh soundsight-3d.sh run`即可。不会保存“下次自动启动转台”的开关。

只有新合格三维组建立目标；之后必须继续有合格当前声帧才能续约。低音量、失败/序号断裂、750ms内未被新合格组更新的过期目标会撤许可；硬件750ms没有合法提交也会停止并报超时，不能自动吞错重启。窗口设得太大、组输出间隔超过750ms时，组间可能撤输出，不能靠重复旧角度续命。双轴目标整组提交，越界不夹成极限角度；显示拒绝原因，保留原始计算结果。

若出现历史快照阻挡启动，先检查故障并保存，再用`sudo sh soundsight-3d.sh drain`排空旧槽。该恢复入口沿用原始帧保存器，其中旧二维计算结果不作为三维证据。除正常STOP留下的0x40外，不自动清其他故障。

## 阵列和云台的相对位置

坐标：+X前、+Y左、+Z上。四麦不随云台转动。默认只按远场方向瞄准；仅知道方位/俯仰无法从音量猜距离。

可保存转轴相对阵列中心XYZ厘米：

```sh
sudo sh soundsight-3d.sh servo-geometry 0 0 0
```

若另有真实声源距离测量，可加`--source-range-cm 100`做几何平移修正；没有距离时XYZ只记录配置，不声称已补偿近场偏差。

默认`software/tetra3d/core/tetra40-nominal.json`是40mm正四面体标称布置：CH0前下，CH1左后下，CH2右后下，CH3顶。实际声孔与CH0～CH3还需核对。可复制JSON，保持格式、按实物调整通道与坐标，通过`run --geometry 文件.json`选择；只确认布局不等于已经测量坐标误差。

## 验证边界

本批的离线数值、策略、寄存器、STOP/PWM定向结果及复核见[证据](../../data/evidence/ps-dual-axis-20261028/readme.md)。用户已完成3D副本综合、实现和位流；助手从同一routed DCP离线补查，没有重复构建。尚未执行真实ARM连续三维、阵列通道确认、双轴机械标定或跟随；历史IP复位与CDC Warning保留，不能宣称整机验收或全部RDC风险关闭。
