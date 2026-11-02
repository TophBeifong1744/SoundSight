# 2026-11-02 当前材料入口

**最终功能与报告口径：** [统一说明](document/final-function-scope.md)明确四项功能、PL/PS分工和当前组件组合；[报告/海报修改规则](document/requirements/final-report-scope.md)要求DAS彻底退出成品，包括正文、图表、公式、待办和展望。对应实现及专属材料从当前仓库删除；报告成品由各自聊天单独修改。原始模板与[制作总指导](document/requirements/report-poster-master-guide.md)也已归入仓库。

[接近最终版的完整运行包与操作说明](document/pynq-final-runtime.md)：S2/S3触屏、CF1A三维、声纹和双轴；DAS已取消。保留个人配置，使用一条安装命令更新。含私人基础声纹资产的完整ZIP只作本地交付，源码、打包工具和验证记录进入仓库。

**2026-11-02 USB单线调试已打通：** 领航者PYNQ的USB SLAVE已支持Windows RNDIS、SSH和WinSCP目录访问；v2加bootpy启动依赖补丁正常重启后由用户确认可重连，仓库v3内置相同依赖。保留DC供电和当前B版bit/HWH，未改启动镜像；VS Code旧版路线已取消。操作见[USB使用说明](document/pynq-usb-network.md)，验证范围见[板端结果](document/evidence/usb-network-preflight-20261102/board-success.md)。

[最新S2/S3/CF1A源码、证据及使用边界](document/release-20261102-submit.md)。当前硬件J3 M15/J14；S2准备入口为`python -B tools/prepare_screen_s2.py --output ../s2_work`，只复制文件。下方PR30/W16操作记录为历史，旧rebuild_ps_3d.bat不包含屏幕。比赛交付为[submit](submit/README.md)。

# SoundSight

最新更新：[2026-10-30集成与交付说明](document/release-20261030.md)。包含实际声纹双轴测试、10秒TTL依据、LAT1及累计统计，和同候选实现报告的限制。

## 比赛提交目录

完整可提交文件夹为 [submit](submit/README.md)，内部是实际的`src/sim/build/board/data/skill/report`文件，不再使用根目录导航占位。整体复制或压缩`submit/`即可交付现有源码与材料；离线复现只需要该目录，步骤见其README。

`submit/build/prepare_workspace.py`从包内文件准备独立工作目录，保留PR #30源码/脚本的路径契约。原开发工程继续维护在`project/software/simulation`；`submit`是用户明确要求的固定交付副本，由`tools/export_submit.py`统一生成。缺失实测、照片/视频、签署与最终定稿仍在包内列明，不把资料整理当成整机验收。

当前程序维护：[最新SD包源码补齐与91项离线验证](document/evidence/sd-program-source-sync-20261029/README.md)；比赛材料：[B的10月29日报告补充](document/evidence/b-report-supplement-20261029/README.md)。双轴手动已确认可转，长稳重启仍在排查。


SoundSight 当前唯一主方案是 **Zynq-7020（PL＋PS/PYNQ）**：四麦三维声音定位、连续测量、水平/垂直双轴控制及可选声纹许可。二维功能保留用于基础验证。

- PL负责四麦采集、FFT/PHAT/IFFT、六对特征、PCM导出，以及双轴PWM、停止和超时保护。
- PS运行同一双核Linux/PYNQ，Python调用C求解器，负责三维计算、音量/多帧筛选、声纹评分与许可、模式控制和必要记录。
- **STM32路线已弃用**，不再作为主方案、备选验收路线或当前缺件；代码和实验只作历史参考。

当前器件 `xc7z020clg400-2`，Vivado `2025.2`；计算/AXI为100MHz，采集/控制为61.44MHz。唯一公共RTL仍在 `project/rtl`，现有 `variants/pl_ps` 路径保留，不因主次调整搬动工程。详见[当前架构与资料边界](document/main-architecture.md)。

## 先读这些

1. [目录怎么用](document/directory-guide.md)
2. [迁移了什么、还缺什么](document/migration-report.md)
3. [实际操作入口](document/run-guide.md)
4. [当前状态和下一步](document/current-status.md)
5. [全部RTL文件的模块与端口](document/modules/RTL-INTERFACES.html)
6. [这次RTL和BD改动总结](document/rtl-bd-changes.md)
7. [Git与日常协作](document/git-workflow.md)
8. [删除旧项目之前](document/delete-old-project.md)
9. [历史STM32工程配方与交接清单](document/stm32-handoff.md)
10. [历史STM32配套Vitis裸机交接](software/vitis/stm32/README.md)
11. [两个比赛Skills的交付包与复现](document/competition-skills-delivery.md)
12. [PYNQ双核上传包与第一次运行](document/pynq-first-run.md)
13. [PL+PS音量版基础配方与交接](document/ps-handoff.md)
14. [PYNQ三种模式完整操作命令](document/ps-manual-calibration.md)
16. [三维测角与双轴跟随候选：Vivado副本更新、PYNQ操作](document/pynq-three-d-dual-axis.md)
17. [三维完整SD包：安装与首次运行](document/pynq-three-d-sd.md)
18. [三维＋声纹许可：安装、评分门限和双轴跟随](document/pynq-speaker-3d.md)
19. [板端单段短录入、多用户保存/切换、评分与声纹双轴跟随](document/pynq-speaker-enrollment.md)

## 当前操作入口

板端联合包与日常命令见[三维＋声纹说明](document/pynq-speaker-3d.md)和[W16更新说明](document/pynq-w16-update.md)。`follow-sound`是显式纯声源模式，`speaker`及`run --axes`要求声纹许可；默认不开轴，手动标定不要求声音。

用户自建Vivado工作副本继续使用最新三维配方/导出及匹配产物，见[架构入口](document/main-architecture.md)。仓库早期PS音量版基础配方使用显式目标：

```powershell
.\project\script\run.bat prepare ps
# 已存在该基础工程时才使用 open ps；不覆盖当前三维外部工程。
```

最新完整重建入口是 `project/script/rebuild_ps_3d.bat --output "..\My SoundSight Work"`；无参数 `run.bat` 同样准备最新三维双轴，默认 `project/par`。源码复制进新工程，旧工程不覆盖。见[完整复现说明](document/vivado-ps-3d-rebuild.md)。综合、实现及硬件操作仍由用户执行。

源代码、模型、约束、IP/BD配方、测试与小型必要结果进入Git。生成工程、仿真数据库、模型权重和旧技术原件本地档案按用途保留，默认不随 `git add .` 推送。

原仓库许可证保留在 [LICENSE](LICENSE)；厂商和外部资料的原许可证/声明继续有效，见 [第三方资料说明](THIRD_PARTY.md)。

当前 RTL、三维、舵机与声纹由 A 全面维护，见 [维护入口](document/rtl-3d-maintenance.md)。

2026-10-29 总工程由 A 全面接手：[当前模式与垂直轴问题](document/total-handoff-20261029.md)。
