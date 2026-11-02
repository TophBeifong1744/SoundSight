# S3 基本控制面板

本版一次接齐既有运行时的基本操作：普通声音跟随 / 声纹跟随、水平 / 垂直 / 双轴选择、开始 / 停止、方向和声纹许可显示、用户切换、门限与滤波设置。S2 显示/触摸/位流保持原版本，原三维与声纹算法不修改。

## 启动

S2 已在本次开机 prepare 和 I2C apply 成功时：

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-panel.sh 2>&1 | tee -a screen-s3-panel.log
echo PANEL_EXIT=${PIPESTATUS[0]}
```

默认持续显示；运行默认持续采集，点 STOP 才结束（硬件故障也会终止）。启动面板不会自动开始采集或开轴，初始选择为 off。需要运动时在首页明确选轴再按 START。原标定、角度范围与声纹门限仍由运行时校验；缺配置时不会猜测填写。

如果是重新开机，先执行一次：

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh prepare
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen-i2c.sh apply
```

两步成功后再启动面板。不要在面板运行期间 prepare 或重新加载位流。保持原 `soundsight-screen.sh --seconds 60` 自检入口；本版没有增加开机自启动。

## 屏幕操作

- HOME：Change mode 切换 SOUND（普通声音）/ SPEAKER（声纹许可）。Select axes 循环 off / horizontal / vertical / both。切模式、停止或会话结束后轴选择恢复 off。
- START：按当前模式和轴启动；启动模型期间显示 STARTING，收到运行报告后显示 RUNNING。状态不是机械到位证明。
- STOP：请求原运行时停止，等待进程退出及设备空闲读回。VERIFYING 表示正在核查，不允许再次启动；确认后显示 IDLE。
- USERS：Next user 浏览已存用户，SELECT user 调用原校验/选择入口。选择用户会清除旧声纹门限，需重新明确设置，不能把旧门限沿用给新用户。
- SETTINGS：Next field 选择音量门限 level、窗口 window、最少有效 minimum、声纹门限 threshold、许可秒数 ttl；+/- 编辑，APPLY 保存当前字段，下次 START 生效。DISABLE speaker gate 清除门限，使声纹模式不授予运动许可，不会切到普通模式绕过声纹。
- DIAGNOSTICS：Read status 读取硬件，Recheck / reload 重载配置或重查停止状态，EXIT panel 停止后台后退出屏幕。所有页面底部均有 STOP。

运行中禁止修改模式、轴和配置，可以切换查看页面、STOP 或 EXIT。原运行日志仍在 logs；终端新增 PANEL_COMMAND、PANEL_RUNTIME、PANEL_STOP_CHECK，便于回收一次联合测试的证据，不逐帧转存到 SD。

## 状态的含义

首页显示运行时报告的当前角度、音量及 motion 原因。历史 LAST_GROUP 不当作当前方向；没有新报告超过 2 秒、NO_OUTPUT 或停止时撤掉当前角度。RX age 是界面收到报告后的年龄，不是采样时间或端到端时延。

声纹首页显示最后已完成分数、分数年龄、运行时许可和剩余 TTL。保留 A 的 score_ttl_v2：通过的最近声纹结果允许跟随当前声音方向；新低分不必立即撤销仍有效的旧许可。界面直接显示运行时许可，不按分数自己重算；TTL 仅本地递减，报告陈旧则显示 UNKNOWN。没有增加严格身份与空间声源绑定；门限未标定、识别质量与长稳限制保持原工程说明。

STOP 后只在运行入口退出 0、读取到唯一完整有效的 DEVICE_STATE、采集/PWM活动位均消失且无非0x40故障时回到可启动状态。状态读回不代替原运行时的音频DMA清理，仍要求原运行入口成功退出。若会话非零退出，本次面板锁定 ERROR：保留日志、退出面板并排查；Recheck 不清除失败记录，不清硬件故障。STOP UNCONFIRMED 时不强杀或自动重启。

## 一轮联合板测

不再重复之前显示/触摸两轮测试。启动本版后，在同一次面板会话中依次完成：

1. SOUND 模式明确选 both，START 后从不同方位发声，观察方向和双轴；STOP 后等待 IDLE。
2. 切 SPEAKER，重新选 both，START 后由已登记目标讲话，观察分数、许可、方向和运动；STOP 后等待 IDLE。阈值为空则只显示分数，不自动设阈值。
3. 空闲时查看用户和参数，按需保存实际要用的设置；涉及用户选择会清门限，不为测试而强制改当前用户。
4. DIAGNOSTICS → EXIT panel。回传 screen-s3-panel.log，并说明两种模式的实际响应。失败则针对失败点复测，不把所有步骤重新跑一遍。

这是联合功能验证，不把两人短对照当完整声纹识别率验收。新声纹录入、开机自启动、关机按钮不属于本版基本功能范围。
