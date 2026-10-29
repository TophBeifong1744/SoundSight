# RTL、三维与转台维护入口

> 2026-10-29更新：拓芙（A）已全面接手，包括声纹；新增用户明确选择的纯声源follow-sound模式。以下2026-10-28分工是历史同步边界，当前入口见[总工程接管](total-handoff-20261029.md)。

2026-10-28：A 维护 FPGA RTL、BD/约束、三维求解、采集与转台 PS 控制；B 维护声纹识别。远端 main 是源码集成基线，不代表三维实阵列、身份识别或机械闭环已经验收。

## 到哪里修改

| 内容 | 位置 |
|---|---|
| 唯一公共 RTL | `project/rtl` |
| 用户自建副本的双轴更新与报告脚本 | `project/bd/update_ps_dual_axis.tcl`、`report_ps_dual_axis.tcl` |
| 实物引脚与双轴输出时序约束 | `project/sdc/ps`；水平 T15，垂直 W16 |
| 当前实现报告 | `project/reports/ps_3d` |
| 三维 C 求解器、几何及数值测试 | `software/tetra3d/core`、`software/tetra3d/tests` |
| 三维多帧筛选、双轴标定与提交 | `software/tetra3d/linux` |
| 公共采集、音量、正常/调试模式、手动水平标定 | `software/ps` |
| 当前短命令入口 | `soundsight-3d.sh`；旧二维入口 `soundsight.sh` 保留 |

40mm 正四面体通道坐标见 `software/tetra3d/core/tetra40-nominal.json`。实物 CH0～CH3、机械零位/正反和允许范围仍需核对。双轴手动标定不要求声音；正常测角默认不动。没有进行本批硬件操作，也不需要因这次 Git 同步重做 Vivado。

## 与 B 的边界

本次公开同步包含 A 侧声纹许可接收器 `speaker_permission.py` 和三维采集适配器 `speaker_capture_3d.py`、`speaker_runtime_3d.py`。它们只消费 B 的声纹状态/评分，不实现或替换识别引擎。评分事件协议见[给 B 的接口说明](b-speaker-3d-interface.md)。

B 维护 `speaker_process.py`、`speaker_scheduling.py`、`speaker_settings.py`、`speaker_targets.py`、`speaker_models.py`、`speaker_follow_setup.py`、`live_speaker*.py` 和 `speaker_core/` 的识别实现、运行包及模型/模板。此次不覆盖 B 的声纹分支，不发布私人录音、模板、模型或完整私有 SD 包。

**单独克隆 main 可以开发/测试三维算法、角度筛选和双轴控制，不能据此声称已经取得完整声纹运行环境。** `speaker`、`speaker-config/import/check` 以及 `run --axes ...` 需要 B 的配套声纹运行程序与资产。缺失时应停止，不通过关闭门控来继续跟随。联合运行使用已私下交付的完整包；B 后续按接口更新识别部分。旧二维 helper 中的声纹诊断命令也需要这套独立依赖。

许可仍采用用户确认的策略：下一轮推理期间保留未过期许可；失败、静音或故障撤销；完成发布后默认 3 秒，可调；初试门限 0.65，未配置不许可。`run` 不带轴选项只测角；带轴选项进入同一个声纹门控。手动标定独立于识别，保留限位、租约和 STOP。

## 验证口径

- 本次从远端最新 main 建立独立提交，保留既有声纹报告材料；重新验证公开源码内的三维、采集、正常模式和舵机测试及入口依赖。
- 复用已归档的双轴 XSim、独立复核及用户实现结果，见[双轴证据](evidence/ps-dual-axis-20261028/README.md)。实现 WNS +0.311ns、WHS +0.036ns；垂直输出约束补查的范围见该目录 `BOARD-RECEIPT.md`，不把补查冒充重实现。
- 完整声纹接合的 134 项离线测试属于此前私有组合候选；本次公开子集不冒充再次执行了该组合测试。最新公开同步检查见[同步记录](evidence/rtl-3d-remote-sync-20261028/README.md)。
- 新三维 ARM 实时负载、实际通道、双轴机械及目标本人/他人评分门限仍待板测。

旧操作说明中生成 ZIP 的命令只在依赖和配套硬件产物齐备时使用；main 不携带外部 Vivado 工作目录或最新完整 bit/HWH 包。源码同步不修改现有 SD 卡。
