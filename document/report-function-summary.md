# SoundSight 功能概述与系统关系

本页提供技术报告、设计报告和中英文海报共用的功能表述。具体性能数字应从同候选、同条件的真实实验引用。

## 中文概述

SoundSight是一套基于Zynq-7020异构计算平台的本地声源感知与双轴指向系统。系统通过正四面体四麦阵列获取同步声学信息，联合相位一致性前端、三维几何求解及多帧方向筛选，形成方位角、俯仰角和质量状态。声纹分支支持板端语音录入、模板保存与目标切换，并以相似度评分和可配置时限许可参与动作决策。水平与垂直执行轴支持手动标定、纯声音跟随和声纹许可跟随，分别保留范围约束、超时和停止保护。RGB触摸屏提供模式、目标、参数与运行状态的本地交互入口。

可编程逻辑承担同步采集、相关特征与连续PCM输出、双轴PWM及确定时序的运动保护；处理系统在同一双核Linux/PYNQ环境中完成数据调度、CF1A前端、C语言三维求解、声纹计算和界面控制。不同计算任务共享同一采集入口，依据音频区间进行关联，通过有界缓存、异步声纹计算与独立运动门控协调时延不同的任务。该分工支持方向更新与身份评分分别调度，并通过明确的运行模式控制执行器参与程度。

系统首先面向会议发言者指向和本地声学交互。在具备阵列和机构标定、合适声场及门限配置的条件下，设备可将声音方向和目标验证信息转换为双轴指向动作。进一步与视觉或机器人控制系统结合的应用属于扩展价值，不作为本项目已完成的部署成果。

## 英文概述

SoundSight is an on-device acoustic sensing and dual-axis pointing system built on the Zynq-7020 platform. A tetrahedral four-microphone array provides synchronized audio for a phase-coherent front end, three-dimensional geometric estimation, and multi-frame direction filtering. The system produces azimuth, elevation, and quality indicators. Its speaker-verification branch supports on-device enrollment, named profiles, target selection, similarity scoring, and configurable time-limited motion permission. Manual calibration, acoustic following, and speaker-gated following retain separate control semantics, with axis limits, timeouts, and stop protection. An RGB touchscreen provides local access to modes, targets, parameters, and runtime status.

The programmable logic handles synchronous acquisition, correlation features, continuous PCM output, PWM generation, and timing-critical motion protection. The processing system runs data scheduling, the CF1A front end, the C-based direction solver, speaker inference, and the user interface within one dual-core Linux/PYNQ system. A single acquisition owner supplies the processing branches; bounded buffers, audio-interval association, and asynchronous speaker inference coordinate tasks with different processing times.

## 框图与表述边界

框图展示“采集—三维估计—方向筛选—动作决策—双轴输出”，并从同一PCM分支接出“声纹计算—时限许可”。触屏连接模式/参数控制与状态显示，PWM及停止保护归PL，界面及声纹推理归PS。当前新版前端应注明CF1A，而非只画旧六对峰值直接送二维求解。

系统输出方向而非距离；声纹许可不等于多人场景中的身份与空间方位已严格绑定。触屏现有控制功能和终端录入能力分别说明。功能描述不能替代角度误差、机械指向误差、声纹独立对照或联合长稳的实验结论。
