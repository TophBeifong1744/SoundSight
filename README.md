# SoundSight

当前程序维护：[最新SD包源码补齐与91项离线验证](document/evidence/sd-program-source-sync-20261029/README.md)；比赛材料：[B的10月29日报告补充](document/evidence/b-report-supplement-20261029/README.md)。双轴手动已确认可转，长稳重启仍在排查。


四麦二维声音定位与转台控制。新项目独立管理，旧仓库不再是编译或运行依赖。

当前包含两种目标，共用一份 PL RTL 和 S1 算法：

- **STM32主方案**：PL采集、FFT/PHAT/IFFT、六对特征、双槽、SPI和PWM保护；STM32负责S1方向求解和动作提交。PS提供时钟、加载与必要平台初始化。
- **PL+PS实验版**：PS接替STM32，通过AXI寄存器读取同一类特征并调用S1，不使用跨板SPI。

两版分别生成自己的独立Vivado工程。当前器件 `xc7z020clg400-2`，Vivado `2025.2`；采集/公共控制61.44MHz，计算及PS侧AXI100MHz。

## 先读这些

1. [目录怎么用](document/directory-guide.md)
2. [迁移了什么、还缺什么](document/migration-report.md)
3. [实际操作入口](document/run-guide.md)
4. [当前状态和下一步](document/current-status.md)
5. [全部RTL文件的模块与端口](document/modules/RTL-INTERFACES.html)
6. [这次RTL和BD改动总结](document/rtl-bd-changes.md)
7. [Git与日常协作](document/git-workflow.md)
8. [删除旧项目之前](document/delete-old-project.md)
9. [实际STM32工程配方与完整交接清单](document/stm32-handoff.md)
10. [Vitis裸机平台与application交接](software/vitis/stm32/README.md)
11. [两个比赛Skills的交付包与复现](document/competition-skills-delivery.md)
12. [PYNQ双核上传包与第一次运行](document/pynq-first-run.md)
13. [最新PL+PS音量版工程复现与交接](document/ps-handoff.md)
14. [PYNQ三种模式完整操作命令](document/ps-manual-calibration.md)
16. [三维测角与双轴跟随候选：Vivado副本更新、PYNQ操作](document/pynq-three-d-dual-axis.md)
17. [三维完整SD包：安装与首次运行](document/pynq-three-d-sd.md)
18. [三维＋声纹许可：安装、评分门限和双轴跟随](document/pynq-speaker-3d.md)

2026-10-19已将外部STM32工程的SPI末沿检查修正接回唯一公共RTL，并核对最新BD/PS/IP/运行配置，详见[交接说明](document/stm32-handoff.md)。用户最新布线后报告为WNS +0.379 ns、WHS +0.036 ns；本次仅同步与静态核查，没有重新构建仓库配方。板测已发现CS短脉冲导致SPI_FORMAT，根因仍未解决；声学精度、机械闭环及独立PS目标仍未验收。STM32诊断固件属于B侧工作，本次未合入其软件分支。

## 三个常用入口

```powershell
# 在自己克隆的 SoundSight 根目录打开终端；工具配置见 document/run-guide.md。
.\project\script\run.bat prepare stm32
.\project\script\run.bat prepare ps
.\simulation\script\run.bat batch samplecdc
```

已存在工程时使用 `open stm32` 或 `open ps`。默认准备动作不会覆盖已有工程。PS板级DDR/MIO与PYNQ由A配置；综合和实现由A点击。详细说明见操作入口。

源代码、模型、约束、IP/BD配方、测试与小型必要结果进入Git。生成工程、仿真数据库、模型权重和旧技术原件本地档案按用途保留，默认不随 `git add .` 推送。

原仓库许可证保留在 [LICENSE](LICENSE)；厂商和外部资料的原许可证/声明继续有效，见 [第三方资料说明](THIRD_PARTY.md)。

当前 RTL、三维与舵机维护及 B 声纹分工见 [维护入口](document/rtl-3d-maintenance.md)。

2026-10-29 总工程由 A 全面接手：[当前模式与垂直轴问题](document/total-handoff-20261029.md)。
