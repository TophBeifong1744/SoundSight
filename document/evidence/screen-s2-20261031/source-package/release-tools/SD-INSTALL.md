# S2：PS I2C0/EMIO 上板

只复制新的`soundsight_screen_ps_i2c_s2.zip`即可，无需再次安装S1a/S1b。屏幕与舵机接线不变；本轮保持关轴。不使用ILA、JTAG编程或裸机ps7_init。

## 安装

退出屏幕/跟随/录音进程，正常关机后取SD卡，将新ZIP复制到启动分区。重新启动，执行：

```bash
ls -lh /boot/soundsight_screen_ps_i2c_s2.zip
sudo python3 /boot/soundsight_screen_ps_i2c_s2.zip
```

记下`BACKUP_DIR`。安装器接受已交付S1位流及S1/S1a/S1b驱动，不静默覆盖其他本地修改。保留用户配置、机械标定、声纹模型与账户资料。看到`SCREEN_PS_I2C_S2_INSTALLED=1`后：

```bash
sudo reboot
```

## 加载新硬件并启用内核I2C0

重启后逐条执行，某步报错则保留输出，先不执行后续屏幕启动：

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh prepare
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh status
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen-i2c.sh apply 2>&1 | tee -a screen-s2-setup.log
echo SETUP_EXIT=${PIPESTATUS[0]}
```

`apply`核对新硬件和真实设备树后，才向configfs加入包内DTBO；仅改变`/amba/i2c@e0004000`的status和clock-frequency。它不配置GPIO、复位触摸、发送IIC探测或改写PS寄存器。成功应有`SCREEN_I2C_SETUP`中的`success: true`和`SETUP_EXIT=0`。配置诊断还会存入运行目录的`logs`，不依赖板上日期准确性。

若报Cadence驱动或i2c-dev缺失，按包内`SCREEN-README.md`的本机模块检查步骤处理；不下载软件、不强制解绑已有设备。启用后若未就绪，保留报错和配置，不重复插入其他overlay。此动态配置重启后会消失，每次启动新硬件后再执行一次`apply`；已正确启用时会核对后直接返回。

## 60秒关轴测试

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen.sh --seconds 60 2>&1 | tee -a screen-s2-test.log
echo SCREEN_EXIT=${PIPESTATUS[0]}
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-3d.sh status
```

应看到`PS_I2C_READY`、`TOUCH=Goodix 911`和`SCREEN_READY=1 ... AXES=off CONTROL=0`。先静置10秒，再点击四角和切换页面。到60秒正常关背光，`SCREEN_EXIT=0`；不应出现IIC错误或提前黑屏。成功后原样再启动一次，检查重复启动与触摸。回传完整日志、点击是否响应及前后fault/drops。

UI运行期间不另行prepare、改设备树或重新编程FPGA。仅测试屏幕，不加`--control`或`--enable-motion`。

## 备份与回退边界

`backup_screen_ps_i2c_s2_*`含原文件和`restore.json`，列出原先存在与新增文件。不能只恢复bit而保留S2驱动，必须恢复匹配的整组文件。突发断电后的多文件安装不保证整体原子性；保留备份，勿绕过版本检查继续拼接。回退后须重启清除动态设备树，再prepare对应旧硬件。S1/S1b触摸问题仍存在，回退不代表故障修复。
