# LAT1完整SD包：安装与关轴联合复测

2026-10-30，`soundsight_pynq_3d_speaker.zip`，应用目录仍为`SoundSight_PYNQ_3D_Speaker`。

本包已包含用户本轮新bit、匹配HWH、最新PYNQ程序和CP1/VF1资源。新结果到达且队列满时，FPGA替换最旧READY定位帧；LOCKED不覆盖，主动替换计DROPS但不因此触发FAULT 0x08。PS保留超时旧角度撤销、声纹静音撤许可，以及评分展示与许可分离。

三维、音量门限、可调窗口/合格帧数、圆周/空间筛选、死区、无声手动、纯声音跟随、声纹门控双轴、声纹录入与目标切换均保留。水平T15、垂直W16；加载不自动开轴。现有声纹目标、门限和舵机标定不在包内，不覆盖。

## 安装

先正常停止程序、关机，把新版ZIP覆盖SD启动分区中的同名文件。保留BOOT.BIN、IMAGE.UB、BOOT.SCR、boot.py、REVISION。插回板子启动后逐条执行：

```sh
cd /home/xilinx
sudo cp -a SoundSight_PYNQ_3D_Speaker SoundSight_PYNQ_3D_Speaker_backup_$(date +%Y%m%d_%H%M%S)
sudo python3 -m zipfile -e /boot/soundsight_pynq_3d_speaker.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh status
```

有报错则停止。不要删除原应用目录，不用重新录入toph、不用speaker-import，也不用安装先前的软件增量。解压更新程序与硬件文件，原个人配置、speaker-profiles和logs继续保留。

本次先重新开机再prepare，避免仍加载旧Overlay。确认LOADED=True、FCLK0约100MHz、复位释放。新硬件可以用下面的只读命令确认（仅在新包prepare成功后执行）：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pynq import MMIO; m=MMIO(0x40000000,4096); v=m.read(0x98); print('LATEST_RESULT_CAP=',hex(v)); assert v==0x4c415431, 'Unexpected hardware'"
```

## 先关轴复测

沿用当前已选目标人和门限，连续说话测试：

```sh
sudo sh soundsight-3d.sh speaker-check
sudo sh soundsight-3d.sh speaker --axes off --seconds 30
```

不驱动舵机。观察结束RESULT/error、DROPS及评分；主动淘汰时DROPS可以增加，不再要求帧号连续。序号跳过会清空角度累计窗口，下一组合格再输出。真正的FAULT、PCM或IPC错误仍会停止，不能靠“保新”忽略。

后续操作仍见`document/pynq-speaker-3d.md`和`document/pynq-three-d-dual-axis.md`。旧`pynq-w16-update.md`里的时序数值属于10月29日候选，本次以reports中的新记录为准。

## 已核对与未测

- XSA内bit/HWH与实际工程输出一致；40份导出输入与安装源一致，31份RTL及Hann数据逻辑与仓库一致。安装版bd_ps_link仅有一条历史注释写W15，实际IO与约束为W16；未回灌错误注释。
- 用户实现报告WNS +0.176ns、WHS +0.029ns、WPWS +2.208ns，受约束端点无时序失败。LUT18226、FF19753、BRAM32、DSP41。
- 报告仍有1个no_output_delay，导出未登记仓库的独立垂直输出预算XDC；本批未做新DCP补查，旧候选补查不能沿用。DRC/方法学警告保留。当前包先用于关轴声纹/定位复测，不宣称全部IO时序或联合转动长稳验收通过。
- 本轮位流实板尚未验证，未自动执行下载、复位或转动。

该ZIP包含私有声纹资源，只作私下交接，不公开上传。
