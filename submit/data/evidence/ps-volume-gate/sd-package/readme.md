# 本次音量版SD交付

2026-10-21：用户完成外部SoundSight_PS_Volume工程的综合、实现和bit生成，反馈无报错。本轮只读接收实际产物，没有启动EDA或板上动作。

核对bit及HWH与同目录pl_ps_volume.xsa中的对应文件逐字节一致。compute和ps_link均启用LEVEL_ENABLE，动作绑定为0；10份更新源与仓库逐字节一致。原始实现时序报告为WNS +0.265 ns、WHS +0.021 ns，setup/hold失败端点为0。报告原件在本目录；这个结论只覆盖报告中的约束，不把打包称为板测或声学验收。

复用并扩展`tools/package_pynq.py --volume`，生成36文件的`release/output/soundsight_pynq_volume.zip`，大小683059字节。根目录只有`SoundSight_PYNQ_Volume`，包括匹配bit/HWH、完整PS与S1源码、测试/数值基准、报告和操作说明。没有Windows编译产物或预制ARM库，板端自行编译；不覆盖旧板端SoundSight_PYNQ。未向H盘写文件。

打包命令（路径是本次输入记录）：

```text
python -B -X utf8 tools/package_pynq.py --volume --hardware-project F:/AMD/work/SoundSight_PS_Volume --xsa F:/AMD/work/SoundSight_PS_Volume/pl_ps_volume.xsa
```

验证：检查ZIP CRC、成员路径安全、包内文件与来源逐字节一致；在临时目录解压后实际执行`software/tests/test_volume_gate.py -v`、`software/tests/test_buffered.py -v`，分别15和19项通过；全部Python文件按3.8语法解析通过。原文在同目录两个测试log，详细来源与边界在SOURCE.json、RESULT.json，完整清单files.txt。解压验证临时目录已清理，不创建codex_out。

新候选ARM编译、板上BIST、真实音量与门限尚未验证。多帧筛选/3°死区仍未接入在线入口，本包不启用舵机。后续先完成SD搬运和软件准备，再根据板状态加载、检查新ABI并调门限。
