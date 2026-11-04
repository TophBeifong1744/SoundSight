# SoundSight 最终提交材料 — 2026-11-04

最终范围：RGB触屏、40 mm正四面体四麦三维定位、声纹验证、双轴指向。组合为S2硬件、P1产品面板、CF1A前端、CP1/VF1声纹与score_ttl_v2许可。水平J3-2/M15、垂直J3-3/J14，默认关轴。

七类目录包含实际文件。当前软件含采集调度、方向窗口、旋转/触摸、确认删除用户和快速启动更新；公开[产品更新包](board/artifacts/soundsight_screen_product_p1.zip)可用于已有匹配板端。私人模型、模板和用户录音不在公共提交内。

[设计报告](report/design-report.docx)（第9章为复现步骤）、[测量/日志原件](data/evidence/final-board-20261103/readme.md)、[使用说明](report/pynq-final-runtime.md)、[触屏操作](report/screen-product.md)、[整理范围](report/submit-final-scope.md)。正式设计报告位于report/design-report.docx；requirements保留赛事模板与规则。

## 独立恢复与检查

在submit目录运行，输出须为空且在本目录之外：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

进入soundsight_work后：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
python -B tools/check_current_software.py --output ../software_check
python -B -m unittest discover -s software/tests -p test_current_runtime.py
```

恢复不依赖Git或原开发目录。S2配方49项，使用Vivado2025.2、xc7z020clg400-2；输出路径ASCII且最多78字节。准备脚本不运行EDA。软件检查需要Python、NumPy/Pillow及PATH中的gcc，使用合成输入进行主机逻辑回归。

匹配bit/HWH/XSA在board/artifacts/screen_s2；原生工程导出和实现报告在build/handoff、build/reports。完整私人运行包依赖既有匹配PYNQ系统，公共提交不是SD镜像。现场测试、用户实测表、程序日志与主机验证分别记录。
