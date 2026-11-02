# P1：上电直接进入屏幕

适用：现有 S2（PS I2C0 EMIO）＋S3 屏幕＋CF1A 三维＋CP1/VF1 声纹工程。
用户已回报 C 的声纹、三维和屏幕功能测试通过；本次是在其基础上完成产品化代码。
本批板子不在线，新增的开机、触屏录入、关机及冷启动尚待本板验证。

## 一次安装，以后不需要串口启动

将 `soundsight_screen_product_p1.zip` 放到 SD 启动分区。先在旧面板按 STOP，等待停止确认，
再到 DIAGNOSTICS → EXIT panel。出现命令提示符后执行以下两条单行命令：

```sh
sudo python3 /boot/soundsight_screen_product_p1.zip
sudo reboot
```

安装成功标志为 `SCREEN_PRODUCT_P1_INSTALLED=`，其中 `autostart_enabled=true`、
`service_started=false`、`hardware_actions=0`。安装只更新文件并登记下一次开机的服务，
不会当场运行采集或驱动舵机。旧文件保存在应用目录的 `backup_screen_product_p1_*`。

保留板端声纹、选中目标、声纹门限/TTL、音量和筛选参数、两轴标定、日志、匹配的 bit/HWH。
如果提示 `BASELINE_MISMATCH` 或 `LOCAL_CHANGE_PRESERVED`，记录该文件名；安装没有覆盖未知版本。
这不是新的 SD 系统镜像，不需要重新复制旧更新包，也不需要改 Vivado 工程。

## 四项产品化内容

| 项目 | 本次实现 | 本板验收 |
|---|---|---|
| 开机自动准备与显示 | systemd 在 bootpy 完成后启动；验证安装、运行现有 prepare、配置 I2C、进入面板；阶段记录到文件 | 待上板 |
| 屏幕完成日常操作 | 两种模式、轴选择、目标切换、声纹录入、参数保存、启停、确认关机 | 待上板 |
| 启动与异常处理 | 单所有者；上电关轴；错误阻止开始；STOP 读回；有限次数恢复触摸；关机先停采集和显示 DMA | 离线故障测试通过，本板待验 |
| 断电重启验证 | 自动记录实际 boot_id、上次关机状态与配置摘要，提供检查/导出命令和下表 | 板子离线，尚未执行 |

系统准备和位流加载期间屏幕可能暂时无画面；视频通路就绪后显示触摸初始化状态。
能够正常输出视频时，触摸或运行错误保留在屏幕上。若位流、视频 DMA 或显示供电本身故障，
无法保证屏幕显示错误，此时保留系统日志，服务不循环重启或自动恢复跟随。

## 屏幕操作

### HOME

- Change mode：SOUND 是普通声源跟随；SPEAKER 要求当前声纹许可。模式选择会保存。
- Select axes：off / horizontal / vertical / both。每次开机及停止后回到 off，不保存动作许可。
- START：明确按下才开始当前模式；STOP 在所有页面固定可见。
- SPEAKER 显示当前目标、分数、许可与剩余 TTL；没有门限时不授予许可。

### USERS

- Next user → SELECT：切换已登记的目标。沿用原规则，切换时清除旧门限；随后在 SETTINGS 配置该目标的门限。
- NEW voice：自动分配尚未使用的 `userN`，原用户不覆盖。默认录 5 秒，可选 2～10 秒。
- RECORD 后显示 3、2、1 倒计时；看到 **SPEAK NOW** 后持续讲话，看到 Processing 后停止讲话。
- 保存后显示新用户编号；新录入不会自动切换目标或授予动作。选择该用户，再配置其门限即可使用。
- 录入失败或取消保留原目标和旧声纹；STOP 可取消录音/计算。出现错误后先到 DIAGNOSTICS → Recheck，确认设备空闲。

本次复用既有单段录入算法，不改评分模型、门限含义或声纹与空间方向的关联方式。

### SETTINGS

Next field 选择音量、窗口帧数、最少有效帧、声纹门限或 TTL；用 +/− 调整，再按 APPLY。
数值交给原程序校验和保存，在下一次 START 生效。`minimum` 不能大于 `window`。
切换用户后不要把原用户的门限自动沿用到新用户。现有已选择用户的设置在安装及开机时保留。

### DIAGNOSTICS 与关机

Read status 读取状态；Recheck 在错误解除且 STOP 读回正常后恢复待机，**不会自动开始跟随**。
触摸失效时立即请求停止；最多尝试 3 次初始化，恢复后仍需明确 Recheck 和 START。

SHUT DOWN → CONFIRM shutdown：先停止采集/推理并检查设备空闲，再停止显示 DMA，最后请求 Linux 关机。
STOP 未确认时不会请求关机；显示 DMA 不能停止时保留缓冲并阻止关机。关机命令被系统拒绝时尝试恢复错误界面。
关机时保持供电；屏幕熄灭后继续等约 15 秒，让 Linux 完成关机，再断电。
屏幕黑屏本身不是电源已经断开的反馈，PYNQ 仍需手动断开适配器。

## 一次完成的本板验收

测试从安装后的第一次重启开始，不需要再手动运行 prepare 或 panel。

| 步骤 | 操作 | 合格现象 | 实际填写 |
|---|---|---|---|
| 1 | 等待首次启动 | 自动出现可触摸的 HOME，axes off，未自行转动 | 待测 |
| 2 | SOUND，选已标定的轴，START，讲话，然后 STOP | 跟随声音，停止确认，轴选择回 off | 待测 |
| 3 | USERS 选原本人目标，确认门限，再进入 SPEAKER | 显示正确用户/评分/许可，沿用原 TTL；STOP 正常 | 待测 |
| 4 | NEW voice，录新测试用户 | 倒计时、发声提示、处理、保存可见；原用户仍在列表 | 待测 |
| 5 | 选择所需用户并保存参数、模式 | 屏幕显示保存结果，重进页面一致 | 待测 |
| 6 | SHUT DOWN，确认；等待系统关机后断电 | 停止完成，屏幕关闭，无自动重启 | 待测 |
| 7 | 重新接通电源，不输入命令 | 自动进入屏幕；用户/参数/模式保留；axes off、不自动跟随 | 待测 |
| 8 | 再做一次开始、STOP、屏幕关机、重新上电 | 第二轮冷启动同样可用，无重复采集/面板进程 | 待测 |

步骤 6～8 使用正常关机后的断电，验证日常产品冷启动；不把它描述成运行中强拔电的文件系统耐受测试。
测试完成后可仅提供上述观察。若需要原始证据，通过已有 SSH/串口执行：

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-product.sh check
sudo sh soundsight-product.sh export
```

`check` 不访问硬件，查看 `is-enabled=enabled`、`is-active=active`、`same_boot=true`、
`record.stage=READY`；完成屏幕关机再开机后还应有 `record.new_boot=true`、`record.settings_preserved=true`。
这些检查只证明启动/配置记录，跟随方向与触摸仍以现场操作为准。
导出为 `logs/product-check.zip`，包含启动记录、配置文件的摘要值和本次服务日志，不包含声纹向量或录音。

## 维护和回退入口

需要恢复手工启动时关闭下一次自动启动：

```sh
sudo python3 /boot/soundsight_screen_product_p1.zip --disable
```

它不会停止当前运行；仍可先在屏幕 STOP 后关机。之后手动方式仍为 `soundsight-3d.sh prepare`、
`soundsight-screen-i2c.sh apply`、`soundsight-panel.sh`。不能在自启面板仍运行时另开第二套面板或采集。

诊断命令（无硬件动作）：

```sh
sudo systemctl status soundsight-product.service --no-pager
sudo journalctl -u soundsight-product.service -b --no-pager -n 100
```

源码入口：`software/screen/product.py`、`backend.py`、`ui.py`；安装器 `tools/install_product.py`。
离线测试：`python -B software/tests/test_screen_product.py`。没有把模拟重启结果写成实际板测通过。
