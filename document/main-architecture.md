2026-11-02：以[最终功能与组合说明](final-function-scope.md)为当前范围。下文按已归档S2硬件、S3屏幕及CF1A更新，不沿用旧W16工程作为当前候选。

# 当前主方案：Zynq-7020 PL＋PS

2026-10-29按拓芙决定，**STM32路线已弃用，唯一主方案是Zynq-7020上的PL＋PS/PYNQ**。当前使用同一个双核Linux/PYNQ系统，由Python调用C算法并管理采集、识别和控制，不采用一核裸机、一核Linux的分工。

## 当前分工

| 部分 | 负责内容 | 维护入口 |
|---|---|---|
| Zynq PL | 四麦采集、FFT/PHAT/IFFT、六对相关特征、快照、连续PCM导出、双轴PWM与停止/超时保护 | `project/rtl`、`project/bd`、`project/sdc/ps` |
| Zynq PS | 同一DMA接收者、CF1A同区间PCM前端、三维C求解、音量/多帧筛选、声纹评分与时限许可、双轴配置/提交、有界记录 | `software/ps`、`software/tetra3d/linux`、`software/tetra3d/core` |
| PYNQ/Linux | 加载匹配bit/HWH，提供驱动、共享库、进程调度和操作入口 | `soundsight.sh`、`soundsight-3d.sh` |
| RGB触屏 | S2 PS I2C0 EMIO触摸、RGB/VDMA/GPIO及S3面板，调用同一业务入口进行模式/轴/参数选择和启停 | `software/screen`、`soundsight-panel.sh` |

器件为`xc7z020clg400-2`，Vivado 2025.2。PS时钟经Clocking Wizard分配100MHz计算/AXI域和61.44MHz采集/控制域，使用官方复位IP。DDR/MIO/PYNQ由用户按实际板卡配置。麦克风固定，水平舵机J3-2/M15、垂直J3-3/J14；软件安装方向、限位和零位可配置。

当前四项核心功能为RGB触屏、四麦40mm正四面体三维定位、声纹验证和双轴指向；连续处理与运动保护贯穿全链。二维和公共S1保留作基础对照；六麦研究不作为当前完成条件。

## 实际使用哪份工程与说明

- 当前S2可搬移工程及工具见[handoff](../handoff/README.md)，只复制准备也可使用`tools/prepare_screen_s2.py`；匹配实现见[S2报告](../report/screen_s2_20261102/README.md)。公共源码仍在`project`；本机旧Vivado工程不覆盖它。
- 当前安装与联合运行：[完整程序包](pynq-final-runtime.md)；屏幕控制：[S3说明](screen-control.md)。旧W16更新和PR30复现只服务历史硬件，不能据此重新生成当前S2候选。
- `project/script/run.bat prepare ps`仍是早期PS音量版基础配方，不能单独代表最新PCM、三维和双轴候选。`variants/pl_ps`保留现有目录名，主方案变更不要求搬动文件或重新生成位流。
- `rebuild_ps_3d.bat`及其无参数BAT路由保留旧三维双轴准备，不包含S2屏幕硬件；本次只更新说明，不自动运行工程构建。
- `follow-sound`明确选择纯声源跟随；`speaker`及`run --axes`需要声纹许可。默认不开轴，手动标定独立于声音/身份；STOP、限位、租约及默认关闭不因路线决定取消。

## 历史材料如何处理

`software/stm32`、`software/vitis/stm32`、`project/sdc/stm32`、旧STM32配方及报告继续保留作技术历史，不再作为待接续成果、备选验收或项目阻断项。旧跨板SPI失败不倒改为通过，也不再要求为完成主方案先修复它。

`software/common`的S1、六对顺序、数值约定及同帧/停止保护仍被有效路径复用；文件名包含`stm32`不等于可以删除。公共冻结头、SPI协议和历史二进制不因文档更新而改写。旧迁移说明、TXT/Word基础设计、历史ZIP与原始实验中的主次称呼按当时日期理解；当前决定以本页、AGENTS和README为准。

## 当前验证边界

已有S2显示/触摸分项板测、声纹评分与TTL记录、双轴动作和CF1A摘要。用户另有持续跟随观察，但与30.016秒原生摘要不能直接合并成同一时长；已保存的缺口/drop事实仍保留。完整包16组离线检查通过，不代表全功能并发实板验收。

真实三维精度、机械标定/指向误差、独立声纹对照及当前组合联合长稳仍按[验收范围](requirements/acceptance.md)取得证据。整板重启旧记录保留；用户后来确认曾仅用电脑串口供电、恢复12V适配器后观察正常，不把它继续表述为当前每轮必现的软件故障。
