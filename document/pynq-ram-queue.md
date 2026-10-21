# PYNQ：先接入RAM，再独立写SD

这次只增加无动作采集入口，不需要改RTL、重新生成bit、改HWH或重新编译C库。旧的 `run_smp.py` 保留，动作模式仍按“落盘成功才继续”的规则运行。

## 改了什么，为什么

旧路径：FPGA锁帧 → CPU1求解 → CPU0写SD并等待fsync → CPU1释放FPGA槽。

新路径：FPGA锁帧 → CPU1求解 → CPU0完整接收到RAM队列 → CPU1释放FPGA槽。CPU0上的独立线程按顺序写SD，每条仍执行flush/fsync。慢盘不再让每一帧直接占住FPGA的两个槽。

RAM队列用Linux `/dev/shm` 的tmpfs文件保存。它是内存存储，不是再写一次SD；同时比只存在Python对象里容易恢复。写盘报错、程序异常退出后，已接收而未落盘的完整记录仍留在启动时打印的 `RAM_RECOVERY_DIR` 中。**突然断电或重启会丢这些记录**，这是本次明确接受的取舍。无法保证内存故障、进程所在系统崩溃时仍能恢复。

启动前核对`/dev/shm`确为tmpfs，并打印实际`RAM_QUEUE_SWAP_ACTIVE`。tmpfs在内存压力下可能被系统换出，因此不承诺内存不足时的硬实时延迟；程序不擅自更改swap配置。

默认最多64条，每条序列化上限16KiB，记录内容上限合计1MiB，另有文件系统及Python开销。到48条立即发出停止新增工作的请求；一旦触发，即使队列随后下降也不自动重启。剩余16条为控制响应、尾帧和结束信息留余量。自定义参数必须至少预留4条，正在写盘的记录也占容量，不能靠取出待写项虚增空位。

高水位在CPU0设置停止请求，CPU1完成当前记录的接收/消费后执行现有STOP和排尾；硬件停止确认后最多读取双槽中两条尾帧。到达指定帧数也会STOP并自动排尾。尾帧可能是正常结果，也可能是取消结果，全部按原ABI记录。Linux调度、C库或驱动卡死仍可能让停止迟到；这不是硬实时零丢帧保证，也没有扩大既定服务预算。取帧/IPC确认/硬件排空仍各沿用250ms上界。

SD报错立即请求STOP；满盘时不丢弃已有RAM项，也不覆盖旧项。结束后默认最多等5秒写盘，超过则报错并保留RAM文件。这个5秒只用于停止采集后的文件排空，不延长采集服务预算。若算法进程卡死而被强制终止，明确报告硬件STOP未确认，不能把它当作正常停止。

## 从SD卡安装增量

以下命令均为板端串口命令，每条单独发送，行尾选择LF。不要把多条拼成一行。板上工作目录为 `~/SoundSight_PYNQ`。

1. 先保存这次板上原始日志。当前旧实验已经STOP并排出了37、38帧；不要再开采集。

```sh
cd ~/SoundSight_PYNQ
```

```sh
sudo /usr/local/share/pynq-venv/bin/python3 -c "from pathlib import Path; from zipfile import ZipFile,ZIP_DEFLATED; p=Path('.'); a=p/'software/build/solver-migration/ARM-RESULT.json'; fs=sorted(p.glob('*.jsonl'))+([a] if a.exists() else []); z=ZipFile('/boot/soundsight-board-evidence-001.zip','x',ZIP_DEFLATED); [z.write(f,f.as_posix()) for f in fs]; z.close(); print('ARCHIVED_FILES=',[str(f) for f in fs]); print('ARM_RESULT_PRESENT=',a.exists())"
```

同名包已存在时不要覆盖，换一个未用后缀。它是完整板端原件，区别于仓库已经保存的串口摘录。随后执行：

```sh
sudo shutdown -h now
```

等系统关机完成再断电取卡。在电脑保存卡中的 `soundsight-board-evidence-001.zip`，并把本次 `soundsight_ram_queue_update.zip` 复制到SD卡可见分区根目录。不要修改BOOT文件、镜像和旧日志。安全弹出，插回后上电。

2. 登录后解压到原目录的父目录。增量只新增三个运行文件、一个自测文件和这份说明；不包含bit/HWH/C库，不覆盖旧采集入口或实验日志。

```sh
python3 -m zipfile -e /boot/soundsight_ram_queue_update.zip /home/xilinx
```

```sh
cd ~/SoundSight_PYNQ
```

```sh
python3 -B software/tests/test_buffered.py -v
```

这一步是假硬件离线自测，不访问PL，不需要sudo。通过后才继续。

## 重启后的加载与首次复验

目前这张旧PYNQ镜像需要显式传 `XILINX_XRT=/usr`，并按已经实测的IO PLL把FCLK0分频设为4×4。不要直接使用默认 `Overlay('soundsight.bit')`，它会恢复不适合当前启动镜像的HWH分频。

下面是本板此前已执行成功的单行加载方式；它会加载位流，仅供用户在上述重启后执行。检查失败就停下，不能删断言强行运行，也不能拿它套其他板卡：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pathlib import Path; from pynq import Overlay, Clocks, MMIO; ref=int.from_bytes(Path('/proc/device-tree/amba/slcr@f8000000/clkc@100/ps-clk-frequency').read_bytes(),'big')/1e6; m=MMIO(0xF8000000,0x300); assert abs(ref-33.333333)<0.001,'STOP: reference changed'; assert m.read(0x108)==0x30000,'STOP: PLL changed'; assert ((m.read(0x170)>>4)&3) in (0,1),'STOP: clock source changed'; Clocks._instance._ref_clk_mhz=ref; ol=Overlay('soundsight.bit',download=False); assert ol.ip_dict['ps_link']['parameters']['ACTUATOR_BOUND']=='0','STOP: actuator bound'; ol.clock_dict[0].update(enable=1,divisor0=4,divisor1=4); m.write(0x008,0xDF0D); print('DOWNLOAD_BEGIN',flush=True); ol.download(); print('LOADED=',ol.is_loaded()); print('FCLK0_CTRL=',hex(m.read(0x170))); print('FCLK0_MHz=',Clocks.fclk0_mhz); print('FPGA_RST_CTRL=',hex(m.read(0x240)))"
```

预期 `LOADED=True`、`FCLK0_CTRL=0x400400`、约100MHz、`FPGA_RST_CTRL=0x0`。这只是寄存器/软件计算值，不冒充示波器实测。接着只读检查：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pynq import MMIO; m=MMIO(0x40000000,4096); print('ID=',hex(m.read(0))); print('ABI=',hex(m.read(0x6c))); print('STATUS=',hex(m.read(0x34))); print('FAULT=',hex(m.read(0x64))); print('DROPS=',m.read(0x68))"
```

ID应为0x5a5a2026、ABI为0x10000；无历史槽，FAULT仅允许已知STOP位0x40或0。不要用0x48去掩盖本次新发生的溢出。

3. 用新入口先跑一帧通过BIST：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_buffered.py --hwh soundsight.hwh --output ram-bist-pass-001.jsonl --mode bist-pass --clear-faults 0x40
```

预期方向有效、reason=0、angle_q8=0、ux_q20=749295、uy_q20=0；不运动。记录可用 `cat ram-bist-pass-001.jsonl` 查看。

4. BIST符合预期后，保持原来音乐和长条音响位置，复现同样的100帧负载：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 software/ps/run_buffered.py --hwh soundsight.hwh --output ram-real-100-001.jsonl --mode real --frames 100 --clear-faults 0x40
```

```sh
tail -n 3 ram-real-100-001.jsonl
```

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pynq import MMIO; m=MMIO(0x40000000,4096); print('STATUS=',hex(m.read(0x34))); print('FAULT=',hex(m.read(0x64))); print('DROPS=',m.read(0x68))"
```

检查点：`stats.consumed=100`，`host_stop_reason=null`，DROPS相比开始不增加，无新增溢出0x08。`stats.drained`是额外保存的STOP尾帧，因此 `DURABLE_FRAMES` 可以比100多一至两帧。停止留下的0x40按既定语义解释；它不等于又发生溢出。

如果 `host_stop_reason=queue_high_water`，说明程序按保记录策略提前停止，不能把它称为100帧通过。不要自动重试或清错掩盖原因。输出文件采用独占新建，重跑应换后缀，绝不覆盖本次结果。

`finished`日志先进入RAM队列，单独看到它不能证明全部fsync完成；正常进程结束时打印的 `DURABLE_FRAMES` 才来自成功写盘计数。若后面仍有写盘异常，以异常和RAM恢复目录为准。

## 写盘失败后的恢复

先保留供电。程序会打印未落盘文件的RAM目录，例如 `/dev/shm/soundsight-xxxx`。待采集进程退出、解决SD空间/写入问题后，把实际目录填入：

```sh
sudo /usr/local/share/pynq-venv/bin/python3 software/ps/recover_ram.py --directory /dev/shm/soundsight-xxxx --output ram-recovered-001.jsonl
```

恢复工具只复制完整记录并fsync，不删除RAM原件。`.partial`不是已接收记录，不自动补成完整帧。原SD日志在报错前可能已写入同一记录，合并时用 `ram_record.session + ticket` 识别重复；同一PL运行期间还需按帧号识别“已入队但未消费、随后排尾重读”的重复。不能跨冷复位只用帧号去重。

若程序报告未收到RAM确认，锁帧可能仍在PL；不要重新下载或复位。原 `run_smp.py --drain-existing` 仍可用于停机后恢复硬件槽，不会启动新采集。若底层驱动卡死或STOP未确认，先回传错误，不能假称全部已排出。

## 验证边界

PC自测采用真实spawn/IPC、写盘线程和假MMIO，覆盖慢盘、高水位、双槽排尾、RAM/SD写失败、恢复、超时、错误ACK和中断。未改RTL、ABI及C算法，不重复运行XSim/综合/实现。新RAM入口的ARM性能、100帧连续运行和高水位板测尚待上述复验，不能拿旧20帧成功冒充新版通过。
