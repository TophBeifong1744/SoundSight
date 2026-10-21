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

当前主机测试分别为15项、19项；新目录里的ARM编译和这些板端测试仍需实际执行。需要数值对照时，包内保留原基准和测试入口：

```sh
python3 software/tests/test_solver_migration.py --library software/ps/libss_solver.so --golden document/evidence/ps-solver-migration-20261020/PC-RESULT.json --output software/build/solver-migration/ARM-RESULT.json
```

## 接下来才加载和测音量

把软件检查结果回传后，再按当前板状态加载本目录同名`soundsight.bit`与`soundsight.hwh`。不要直接套用普通Overlay自动下载命令：这张旧镜像曾出现sudo丢失XILINX_XRT及33.333333MHz参考被按50MHz计算的问题；加载仍需沿已验证的时钟流程确认，不能仅凭新文件存在就认定时钟正确。

新硬件预期ID为0x5a5a2026、ABI为0x00010001；旧ABI0x00010000不属于本音量版。完成加载/寄存器确认后，使用`software/ps/run_buffered.py`，必须显式带`--measure-level`（仅量测）或`--min-level 1000`（初始假设门限）。1000不是标定结论，需要比较安静与发声的真实幅度后调整。

应用使用`direction_output`作为音量筛选后的结果；`result`是保留的原始求解结果。多帧筛选和3°死区目前仍是离线回放成果，未接入在线运行，本包不驱动舵机。

## 文件组成

- soundsight.bit / soundsight.hwh：本次实际实现产物，配套保存并同名。
- software/ps：双进程、RAM队列、音量门限、恢复工具、C桥和编译入口。
- software/common：冻结接口、S1 C求解器及必要依赖。
- software/tests与PC数值基准：离线检查；不自动访问板上寄存器。
- tools：只读环境检查及工具定位辅助。
- reports：此次实现时序和DRC报告。
- SOURCE.json：产物来源、当前软件工作树状态及未测边界；不以Git提交号冒充未提交软件的版本。

文件打包和主机自测不代表本次音量版已通过ARM或实板验证。
