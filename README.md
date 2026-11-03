# SoundSight

基于Zynq-7020 PL+PS/PYNQ的RGB触屏、四麦三维定位、声纹验证与双轴指向系统。阵列为40 mm正四面体；支持明确选择的纯声音跟随与声纹许可跟随，开机默认关轴。

- [当前状态](document/current-status.md)与[架构/接口](document/main-architecture.md)
- [完整运行包使用](document/pynq-final-runtime.md)、[触屏操作](document/screen-product.md)
- [最新实测和照片](document/evidence/final-board-20261103/README.md)
- [技术报告、设计报告、双语海报统一入口](document/handoff/report-update-20261103/README.md)
- [七类实体提交文件](submit/README.md)、[整理规则](document/requirements/competition-maintenance.md)
- [实际S2工程交接](handoff/README.md)与[实现报告](report/screen_s2_20261103/README.md)

源码在project/rtl、software；硬件配方以project/screen_s2/source-map.json为准。当前水平J3-2/M15、垂直J3-3/J14。硬件生成由操作者运行；本轮维护未执行综合、实现或板卡动作。

公共软件更新包为release/output/soundsight_screen_product_p1.zip。含原始私人模型/模板的soundsight_pynq_3d_speaker.zip单独交付，不上传公共仓库；更新保留个人配置、用户档案与日志。submit可独立恢复公共源码与匹配硬件资料，不是完整SD系统镜像。
