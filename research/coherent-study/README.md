# 相位一致性研究原件与依赖

本目录保存2026-11-01研究脚本及阶段报告；生产代码在software/tetra3d/linux/coherent_frontend.py，不在此另行维护。报告中的成员A/B/C是匿名录音场景标记，不能直接当成代码作者署名。

脚本的兄弟目录结构保留，但以下外部输入不公开：各实验raw/four_mic.wav、raw/packets.bin、raw/result.json、rows.json/raw-replay-rows.json，以及旧reference下的C库、求解模块、Hann和测试音频。study.py依赖study_candidates.py、study_weighting.py、analyze_ab.py；依赖Python、NumPy、SciPy，历史Windows solver.dll须按目标系统重新编译。CF1A历史validate_replay.py还依赖旧CF1代码与五份私有录音；S2/S3历史安装器测试依赖旧完整A运行包。原日志和报告保持当时路径，不把这些路径作为比赛包的可运行承诺。

本包提供公开聚合结果、方法与边界；未加入私人音频、模板或嵌入，不声明可独立复跑这些历史私有输入实验。可独立运行的合成PCM/逻辑回归见tools/check_current_software.py，使用正式源码新编译C库，无硬件操作。
