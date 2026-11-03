# AF1：无声纹三维跟随

> A收件补充（2026-10-29）：B已完成板端安装、原21项与新7项离线测试；未完成实际跟随。垂直手动命令接受但未观察到动作，先按[接管说明](total-handoff-20261029.md)定位。以下安装器仅适用于B所列原始基线，已装AF1无需重装；不用于覆盖后续A侧保护修复。

仅新增显式`follow-sound`入口，复用现有三维快照、空间筛选及双轴控制。
不启动声纹或PCM DMA进程；不区分说话人，任何满足方向/音量条件的声源均可能被跟随。
默认仍为axes off。机械配置缺失或不合法时拒绝开轴；STOP、失效撤销、限位及硬件租约保持原实现。

| 入口 | 行为 |
|---|---|
| `run` | 只测角，轴关闭 |
| `run --axes both` / `speaker --axes both` | 保持原声纹门控 |
| `follow-sound` | 无声纹测角，轴默认关闭 |
| `follow-sound --axes both` | 显式无声纹双轴跟随 |
| `manual` | 保持原手动标定功能 |

## 安装

把soundsight_follow_sound_af1.zip复制到SD的Windows可见分区；停止当前采集后执行：

```sh
sudo python3 /boot/soundsight_follow_sound_af1.zip
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo sh soundsight-3d.sh check
sudo sh soundsight-3d.sh follow-sound --help
sudo sh soundsight-3d.sh servo-config horizontal
sudo sh soundsight-3d.sh servo-config vertical
```

安装会核对原版本、备份后替换一个入口文件，并添加测试和本说明；重复安装不重复修改。
不写模板、模型、个人配置、位流、HWH或库，不启动采集和舵机。check不加载FPGA。
若因取SD而重启，首次实际采集前按原流程prepare/status。

## 运行

先用无动作短测核对方向、通道和门限：

```sh
sudo env PYTHONUNBUFFERED=1 sh soundsight-3d.sh follow-sound --axes off --frames 100 --debug
```

确认两轴零位、方向、实测机械限位和阵列方向后，才执行：

```sh
sudo env PYTHONUNBUFFERED=1 sh soundsight-3d.sh follow-sound --axes both --frames 300
```

300是定位帧数，不是秒。省略frames为持续运行，Ctrl+C停止。
输出`FOLLOW_SOUND=AF1 SPEAKER=DISABLED IDENTITY_GATE=OFF`说明选中了新入口。
停止后查看`THREE_D_STOPPED SUMMARY=... ERROR=...`并保留JSON。
`speaker-config --disable`不是无声纹开关，它仍只会禁止声纹许可。
旧文档的`run --axes`示例在接合版仍指向声纹，纯声学测试使用本页新命令。

## 回退

停止采集，使用安装输出的BACKUP_DIR，将其中的
`software/tetra3d/linux/board_3d.py`复制回工程同一路径。
新增测试和说明可留在原处，不会被旧入口调用；无需更改任何配置/模型或重新烧录。
若BACKUP_DIR对应重复补全安装且没有该旧文件，应使用首次成功安装的备份。

## 验证边界

PC路由/客户端和原三维软件模型回归通过；后续B交接记录已确认板端安装、两份C库构建及21+7项离线测试通过。尚无真实AF1采集或机械跟随实测。
本更新不提供未经实测的零位/限位示例。原声纹进度保持。
