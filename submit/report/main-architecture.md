# 当前主方案：Zynq-7020 PL＋PS

2026-10-29按拓芙决定，**STM32路线已弃用，唯一主方案是Zynq-7020上的PL＋PS/PYNQ**。当前使用同一个双核Linux/PYNQ系统，由Python调用C算法并管理采集、识别和控制，不采用一核裸机、一核Linux的分工。

## 当前分工

| 部分 | 负责内容 | 维护入口 |
|---|---|---|
| Zynq PL | 四麦采集、FFT/PHAT/IFFT、六对相关特征、快照、连续PCM导出、双轴PWM与停止/超时保护 | `project/rtl`、`project/bd`、`project/sdc/ps` |
| Zynq PS | 三维C求解、音量门限、多帧方向筛选、声纹评分和许可、模式控制、双轴配置/提交及有界记录 | `software/ps`、`software/tetra3d` |
| PYNQ/Linux | 加载匹配bit/HWH，提供驱动、共享库、进程调度和操作入口 | `soundsight.sh`、`soundsight-3d.sh` |

器件为`xc7z020clg400-2`，Vivado 2025.2。PS时钟经Clocking Wizard分配100MHz计算/AXI域和61.44MHz采集/控制域，使用官方复位IP。DDR/MIO/PYNQ由用户按实际板卡配置。麦克风固定，水平舵机T15、垂直W16；软件安装方向、限位和零位可配置。

当前目标是四麦40mm正四面体三维定位、连续处理、双轴控制及可选声纹许可。二维和公共S1保留作基础对照；六麦研究不作为当前完成条件。

## 实际使用哪份工程与说明

- 当前三维硬件由用户在外部Vivado工作副本生成，继承PCM/声纹工程并加入双轴。源码唯一维护于仓库；实际BD导出在`project/bd/ps_3d_export.tcl`，匹配实现和W16证据见[当前实现](../build/reports/ps_3d/w16/readme.md)。该BD导出由[完整重建入口](vivado-ps-3d-rebuild.md)调用，入口补齐源码、FFT配置、约束和初始化数据。
- 三维更新与连接：[双轴工程及PYNQ说明](../board/instructions/pynq-three-d-dual-axis.md)；安装和复测：[W16更新说明](../board/instructions/pynq-w16-update.md)；联合运行：[三维＋声纹说明](../board/instructions/pynq-speaker-3d.md)。
- `project/script/run.bat prepare ps`仍是早期PS音量版基础配方，不能单独代表最新PCM、三维和双轴候选。`variants/pl_ps`保留现有目录名，主方案变更不要求搬动文件或重新生成位流。
- 无参数`run.bat`已切到最新三维双轴准备，默认`project/par`；推荐`rebuild_ps_3d.bat --output "..\My SoundSight Work"`在仓库外建工作副本。显式历史路由仍保留，不恢复STM32任务。
- `follow-sound`明确选择纯声源跟随；`speaker`及`run --axes`需要声纹许可。默认不开轴，手动标定独立于声音/身份；STOP、限位、租约及默认关闭不因路线决定取消。

## 历史材料如何处理

`software/stm32`、`software/vitis/stm32`、`project/sdc/stm32`、旧STM32配方及报告继续保留作技术历史，不再作为待接续成果、备选验收或项目阻断项。旧跨板SPI失败不倒改为通过，也不再要求为完成主方案先修复它。

`software/common`的S1、六对顺序、数值约定及同帧/停止保护仍被有效路径复用；文件名包含`stm32`不等于可以删除。公共冻结头、SPI协议和历史二进制不因文档更新而改写。旧迁移说明、TXT/Word基础设计、历史ZIP与原始实验中的主次称呼按当时日期理解；当前决定以本页、AGENTS和README为准。

## 尚未完成的事情

用户已确认T15/W16双轴手动可转。双轴纯声音跟随开始时可转动，但长稳期间出现整板重启，原因尚未确定，关轴对照待回传。真实三维精度、完整标定、声纹门限与身份方向关联、DAS实麦效果及稳定闭环仍需相应实测；见[验收范围](requirements/acceptance.md)。此次是路线和资料统一，不产生新的板测通过结论。
