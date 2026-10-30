# 音量版：SD卡搬运与板端准备

本包为PL+PS音量版，采用同一Linux/PYNQ的双进程和RAM队列；当前无舵机动作。用户已生成新bit；打包时确认bit/HWH与同次导出的XSA一致，compute和ps_link的LEVEL_ENABLE均为1，ACTUATOR_BOUND=0，寄存器地址0x40000000、范围4KB。

## 电脑上只复制一个ZIP

将`release/output/soundsight_pynq_volume.zip`复制到SD卡根目录。不要在Windows解压到SD卡，不覆盖BOOT.BIN、BOOT.SCR、IMAGE.UB、boot.py、REVISION，不必复制XSA、Vivado工程或旧增量ZIP。原来的软件包和板测备份保留。

安全弹出SD卡，在板子断电时插回，再启动。以下命令均在板子的串口Linux提示符执行，每次一整条，串口行尾使用LF。不是在电脑PowerShell中执行。

## 解压到独立的新文件夹

先确认文件：

```sh
ls -lh /boot/soundsight_pynq_volume.zip
```

如果已安装上一版音量包，请先在板端保留整个旧目录，再执行下面的解压命令（备份名已存在会报错，不覆盖）：

```sh
python3 -c "from pathlib import Path; p=Path('/home/xilinx/SoundSight_PYNQ_Volume'); b=p.with_name('SoundSight_PYNQ_Volume_before_filter'); assert p.is_dir() and not b.exists(),'检查原目录和备份目录'; p.rename(b)"
```

首次解压（已有同名目录时主动报错，不覆盖旧实验）：

```sh
python3 -c "from pathlib import Path; from zipfile import ZipFile; p=Path('/home/xilinx/SoundSight_PYNQ_Volume'); assert not p.exists(),'目录已存在，请保留原件并检查'; ZipFile('/boot/soundsight_pynq_volume.zip').extractall('/home/xilinx')"
```

进入目录：

```sh
cd /home/xilinx/SoundSight_PYNQ_Volume
```

旧`/home/xilinx/SoundSight_PYNQ`和其中的日志、C库、旧bit/HWH均保持原样。这个包自带所需C源码，不依赖从旧目录复制共享库。

## 加载前的软件检查

依次执行，每条成功再执行下一条：

```sh
python3 tools/pynq_preflight.py
```

预期READY_FOR_ARM_OFFLINE_TEST。此命令只检查环境，不下载bit、不读写硬件寄存器。

```sh
sh software/ps/build_solver.sh
```

```sh
python3 -B software/tests/test_volume_gate.py -v
```

```sh
python3 -B software/tests/test_buffered.py -v
```

新增在线筛选测试：

```sh
python3 -B software/tests/test_online_angle_filter.py -v
```

当前主机测试分别为15项、21项、19项；新目录里的ARM编译和这些板端测试仍需实际执行。需要数值对照时，包内保留原基准和测试入口：

```sh
python3 software/tests/test_solver_migration.py --library software/ps/libss_solver.so --golden document/evidence/ps-solver-migration-20261020/PC-RESULT.json --output software/build/solver-migration/ARM-RESULT.json
```

## 接下来才加载和测音量

软件检查通过后，从当前目录加载本包同名`soundsight.bit`与`soundsight.hwh`。不要直接套用普通Overlay自动下载命令：这张旧镜像曾出现sudo丢失XILINX_XRT及33.333333MHz参考被按50MHz计算的问题；加载仍需沿已验证的时钟流程确认，不能仅凭新文件存在就认定时钟正确。

当前这块板的加载命令如下（请先确认没有采集程序运行；会加载PL，由用户执行）：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pathlib import Path; from pynq import Overlay, Clocks, MMIO; ref=int.from_bytes(Path('/proc/device-tree/amba/slcr@f8000000/clkc@100/ps-clk-frequency').read_bytes(),'big')/1e6; m=MMIO(0xF8000000,0x300); assert abs(ref-33.333333)<0.001,'STOP: reference changed'; assert m.read(0x108)==0x30000,'STOP: PLL changed'; assert ((m.read(0x170)>>4)&3) in (0,1),'STOP: clock source changed'; Clocks._instance._ref_clk_mhz=ref; ol=Overlay('soundsight.bit',download=False); assert ol.ip_dict['ps_link']['parameters']['ACTUATOR_BOUND']=='0','STOP: actuator bound'; ol.clock_dict[0].update(enable=1,divisor0=4,divisor1=4); m.write(0x008,0xDF0D); print('DOWNLOAD_BEGIN',flush=True); ol.download(); print('LOADED=',ol.is_loaded()); print('FCLK0_CTRL=',hex(m.read(0x170))); print('FCLK0_MHz=',Clocks.fclk0_mhz); print('FPGA_RST_CTRL=',hex(m.read(0x240)))"
```

预期LOADED=True、FCLK0_CTRL=0x400400、FCLK0_MHz约100、FPGA_RST_CTRL=0x0。任一断言失败就停下，不删检查强行运行。再只读核对：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pynq import MMIO; m=MMIO(0x40000000,4096); print('ID=',hex(m.read(0))); print('ABI=',hex(m.read(0x6c))); print('STATUS=',hex(m.read(0x34))); print('FAULT=',hex(m.read(0x64))); print('DROPS=',m.read(0x68))"
```

新硬件预期ID为0x5a5a2026、ABI为0x00010001；旧ABI0x00010000不属于本音量版。完成加载/寄存器确认后，使用`software/ps/run_buffered.py`，必须显式带`--measure-level`（仅量测）或`--min-level 1000`（初始假设门限）。1000不是标定结论，需要比较安静与发声的真实幅度后调整。

在线多帧功能已加入：同时指定`--min-level 1000 --angle-filter`，按20帧、至少12个有效角、±10°与2/3一致筛选，再算圆周平均并应用3°死区。低音量清空窗口，STOP尾帧仅保存。最终结果读取`direction_output`；原始C结果保留在`result`，单帧门限结果在`frame_direction`。本包不驱动舵机，运行命令和日志解释见在线筛选说明（历史引用：`document/pynq-online-angle-filter.md`）（仓库位置为同级pynq-online-angle-filter.md）。

## 文件组成

- soundsight.bit / soundsight.hwh：本次实际实现产物，配套保存并同名。
- software/ps：双进程、RAM队列、音量门限、恢复工具、C桥和编译入口。
- software/common：冻结接口、S1 C求解器及必要依赖。
- software/tests与PC数值基准：离线检查；不自动访问板上寄存器。
- tools：只读环境检查及工具定位辅助。
- reports：此次实现时序和DRC报告。
- SOURCE.json：产物来源、当前软件工作树状态及未测边界；不以Git提交号冒充未提交软件的版本。

文件打包和主机自测不代表本次音量版已通过ARM或实板验证。
