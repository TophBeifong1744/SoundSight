# SoundSight 屏幕基本控制 S3

2026-10-31 首次实板补充：安装/prepare/I2C/CONTROL=1面板启动成功。一次SOUND关轴会话返回KeyboardInterrupt/runtime_code=1，设备停止读回正常、fault/drops=0，VDMA停止确认；正常运行后STOP及双轴/声纹联合仍未闭合。详见 BOARD-FIRST-RESULT.md。后续由C按 ../ss-c-board-test-20261031/START_HERE.md 接手，产品候选保持不变。

用户在 S2 两轮显示/触摸通过后要求一次完成基本功能，再集中联合验收。本批为软件增量；已验证 S2 工程与源目录保留，没有改位流、I2C、三维算法、声纹算法、用户资料或机械标定。

交付入口：`delivery/soundsight_screen_control_s3.zip`（可由板端 Python 直接执行）。包中含安装器和全部本次修改源码。实现：`runtime/software/screen/backend.py`、`runtime/software/screen/ui.py`、`runtime/soundsight-panel.sh`。使用与一轮验收步骤见 `runtime/SCREEN-CONTROL.md`。

功能范围：持续普通声音/声纹跟随、明确选轴、开始/停止及设备空闲读回、当前角度/声纹许可/TTL显示、已有用户选择、参数保存、退出面板。默认关轴、无自动采集。已有用户选择沿用清门限规则；保留 score_ttl_v2 的试验识别状态。新声纹录入、自动启动及关机按钮未增加。

## 安装和启动

1. 把 ZIP 放到 SD 启动分区；回板开机后安装：

```bash
sudo python3 /boot/soundsight_screen_control_s3.zip
```

安装器要求已有匹配 S2 及 A 的运行入口，自动备份，拒绝覆盖未知修改，更新软件校验记录；软件安装本身不需再次重启。私有资料不打包、不改写。

2. 若此次刚开机，加载原 S2 并启用 I2C（每步成功再继续）：

```bash
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 XILINX_XRT=/usr sh soundsight-3d.sh prepare
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-screen-i2c.sh apply
```

如果本次开机已经完成这两步，不重复执行。

3. 打开完整基本面板：

```bash
sudo env PYNQ_PYTHON=/usr/local/share/pynq-venv/bin/python3 sh soundsight-panel.sh 2>&1 | tee -a screen-s3-panel.log
echo PANEL_EXIT=${PIPESTATUS[0]}
```

首轮同时提供模式与轴选择；不要求先再跑关轴自检。用户按当前已标定机构情况明确选择 both 后 START，依次普通模式→STOP/IDLE→声纹模式→STOP/IDLE→查看设置→EXIT。一轮即可覆盖本批基本接入，是否需复测取决于实际结果。保留联合日志和原会话结果，不能把短测当成长期稳定性或完整声纹识别率验收。

## 证据

原 S2 实板证据：`../ss-screen-ps-i2c-release-s2/BOARD-RESULT.md`。

本批 Python 3.8 语法检查与离线画面生成通过。独立主机测试 19 项通过，含实际 A 纯格式化/参数解析函数、完整后台结束→status读回模拟、坏/缺/重复状态阻断，以及实际 ZIP 安装器的 6 个替换位置回滚、重复安装、未知修改拒绝和私有配置哨兵保留。报告位于 `verification/`；主作者另行阅读测试源码/原始日志，确认其有限范围，未将模拟 Linux 边界当作实板。本版屏幕与声音/声纹/双轴联合板测仍待用户执行。构建脚本及安装器测试使用本地既存 S2 和 A 包核对依赖，不是脱离这些基线即可运行；交付 ZIP 不含模型、录音、密码或新的硬件载荷。
