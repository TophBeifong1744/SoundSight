# 正常运行与调试模式（默认无舵机，2026-10-22）

新增水平轴接入候选见[pynq-horizontal.md](pynq-horizontal.md)。本文的无动作命令继续有效；带`--horizontal-motion`的显式动作入口必须使用新水平位流及PYNQ机械配置。调试模式仍无动作。

日常优先使用[板端一键准备和门限调整](pynq-board-helper.md)：`sudo sh soundsight.sh prepare`、`level 7000`、`run normal/debug`。下面保留完整底层命令供排障，不再需要逐条手动配置时钟/ABI。

最新更新包已修正短入口的Python探测：实际导入PYNQ成功才进入硬件命令，并显示`PYTHON_EXE`和`PYNQ_IMPORT_OK=1`；失效的旧`PYNQ_PYTHON`会自动忽略，不需要手动清除。旧入口报过找不到PYNQ的用户，需重新解压本次包并安装一次；以后仍用上述短命令。

新增`sudo sh soundsight.sh filter 20 12`保存窗口总帧数/最低有效数；默认规则不变。英文提示显示WINDOW、VALID、MIN、LAST_GROUP和LAST_CLEAR，详见上述使用说明。

串口消息现已统一为ASCII英文（包括状态、错误、参数帮助及安装提示），角度单位用`deg`。中文源码注释及本说明保留。

本次只更新PS Python软件；沿用正在测试的音量版bit/HWH与已编译C库，不用Vivado、不重装PYNQ。B的SD_BATCH_V1保留在调试入口。旧完整`soundsight_pynq_volume.zip`尚未包含本增量，不能用旧包覆盖刚更新的软件。

## 两种模式

|项目|normal 正常运行|debug 调试|
|---|---|---|
|持续时间|默认持续，Ctrl+C结束；可指定帧数|按指定帧数，原有流程|
|帧释放|取帧、C求解、音量门限及当前帧的窗口筛选处理完成后立即确认消费（不等收满一组才释放）|完整帧接收到RAM后确认消费，另线程批量写SD|
|数据保留|有界筛选窗口（默认20帧）、上一组结果/最近清空各一条、最近处理的一帧、一个最新状态快照及固定种类计数|详细JSONL、RAM恢复记录|
|串口|每0.5秒尝试显示一次，含无有效输出的原因|沿用原启动/结束/队列与存储统计|
|SD写入|运行中不逐帧写文件；停止后仅写一份小汇总JSON|每批写入并同步详细JSONL，高水位STOP|
|舵机|关闭，入口没有启用动作参数|沿用无动作run_buffered入口|

两者共用原单MMIO所有者锁。切换方法是先Ctrl+C，看到停止回报后再启动另一模式，不是边采集边热切换。程序重启时清空筛选窗口，不能把旧目标带进新会话。

正常模式不再保存每帧六对特征用于事后回放，计算/统计完成后即可丢弃。统计在停止后才落盘，因此突然断电会失去这次未写出的统计；最后一条故障与最近处理记录在异常退出时写入汇总。运行中无不断增长的日志或记录队列。操作系统调度、内存换页仍可能影响性能，不能宣称硬实时或已通过长稳。

## 1. 更新SD卡

电脑把`release/output/soundsight_normal_update.zip`复制到SD根目录。保留BOOT.BIN、boot.py、IMAGE.UB等启动文件和全部历史测试日志，不删除旧包。安全弹出，断电插卡后启动板子。

串口命令一条一条执行，行尾LF。出现sudo密码提示时只发送密码，不能把下一条命令当成密码。

```sh
python3 -m zipfile -e /boot/soundsight_normal_update.zip /home/xilinx
```

确保采集程序已停止，再安装。安装器使用同一运行锁，先备份待替换的旧源码，再原子替换；打印`BACKUP=`位置。日志、C库、bit/HWH都不改。

```sh
sudo python3 /home/xilinx/soundsight_normal_update/install.py --destination /home/xilinx/SoundSight_PYNQ_Volume
```

```sh
cd /home/xilinx/SoundSight_PYNQ_Volume
```

```sh
python3 -B software/tests/test_normal.py -v
```

```sh
python3 -B software/tests/test_sd_batch.py -v
```

英文输出检查：

```sh
python3 -B software/tests/test_serial_english.py -v
```

这些是离线软件自测，不加载bit、不读写真实寄存器。更新包不含新位流，也不含新的ARM共享库。

## 2. 启动前

如果板子刚重启，仍须按此前已验证的流程加载音量版overlay并修正PS时钟。不能直接把SD上的bit当成已加载。确认LOADED=True、FCLK0_CTRL=0x400400、参考时钟修正后FCLK0约100MHz、复位已释放，ID=0x5a5a2026、ABI=0x00010001。

已有旧槽先用调试模式`--drain-existing`保全；新增故障先排查。下面`--clear-faults 0x40`仅用于已确认的STOP取消标记，不能用扩大掩码掩盖其它故障。

## 3. 先做正常模式1000帧短测

7000沿用B近期试调值，不是标定结果。正常模式始终启用现有音量门限、20帧筛选、圆周平均及3°死区，不需另外加`--angle-filter`。

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_device.py --operation normal --hwh soundsight.hwh --output normal-1000-001.json --frames 1000 --min-level 7000 --clear-faults 0x40
```

```sh
cat normal-1000-001.json
```

预期`error:null`、`stats.consumed:1000`、`sequence_gaps:0`，核对`drops_first/drops_last`与最终`hardware.drops`没有新增。`hardware.fault=64`是STOP后的0x40，和正常采集中`stats.fault_or=0`分开看。`drained`是正常结束后额外处理的最多两条尾帧，不计入1000。

输出有三种情况：

- `ANGLE=... deg SERVO=OFF`：这一最新帧刚完成合格窗口。
- `NO_OUTPUT: COLLECTING WINDOW=n/N; LAST_VALID_WINDOW=... deg AGE=... s (HISTORY_ONLY)`：不冒充新结果。串口0.5秒显示一次，而窗口可能更频繁，显示会跳过中间结果；统计仍计数。
- `NO_OUTPUT`，附`LOW_VOLUME`（音量不足）、`INSUFFICIENT_VALID_ANGLES`、`INSUFFICIENT_CONSENSUS`、启动等待或过期原因：不会把无效结果打印为0°，不会一直拿旧角冒充。

串口通常每0.5秒显示一次；若串口/接收方堵塞，仅保留一条待发送行、跳过后续显示，计入`console_skipped`，不让终端阻塞计算。CPU0负责显示和监督，CPU1计算/消费；双方原750ms失联边界保留。它不是保证严格0.5秒的实时系统。

## 4. 持续运行与切换

短测正常后，不带`--frames`即可持续运行：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_device.py --operation normal --hwh soundsight.hwh --output normal-continuous-001.json --min-level 7000 --clear-faults 0x40
```

发送真正Ctrl+C控制字符（0x03），不要发送字面文字“Ctrl+C”。等`NORMAL_STOPPED`；SD上的汇总这时才写完。每轮换一个未使用的输出文件名，避免覆盖。

切到保留逐帧原件的调试模式：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_device.py --operation debug --hwh soundsight.hwh --output debug-1000-001.jsonl --mode real --frames 1000 --min-level 7000 --angle-filter --clear-faults 0x40
```

调试模式仍可能遇到SD积压，正常模式的新增不代表这个旧问题已经修好。必要时双BIST也继续使用原debug命令。正常模式仅用于算完释放，不在异常时悄悄清掉失败锁帧：如果退出报错并留槽，先用debug的`--drain-existing`保存，再决定下一轮。

## 代码与验证边界

- `software/ps/run_device.py`：选择normal/debug。
- `software/ps/run_normal.py`：常数空间统计、单快照跨进程、0.5秒非阻塞显示、STOP/故障处理、停止后汇总。
- `software/ps/run_buffered.py`、`ram_queue.py`：保持B SD_BATCH_V1的行为，只将提示文字改成英文。
- 音量、角度数学、C库、RTL、ABI及bit/HWH没有修改。
- 主机定向验证原件见`document/evidence/pynq-normal-mode-20261022`。主机假硬件/进程测试不代表ARM实板、声学精度或长期稳定已经通过。本次不安排Vivado或舵机动作。
