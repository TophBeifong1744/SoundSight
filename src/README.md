# 设计源码入口

本目录按官方推荐分类提供导航，正式源码沿用下列唯一位置。根目录 [README](../README.md) 给出目录映射，下载完整仓库后相对链接即可使用。

| 内容 | 正式位置 | 归属与用途 |
|---|---|---|
| PL RTL、初始化数据 | [project/rtl](../project/rtl) | A维护的四麦采集、相关特征、PCM、控制和保护；厂商组件注明来源 |
| BD、PS7、IP、约束与源清单 | [project](../project)、[PR #30复现说明](../document/vivado-ps-3d-rebuild.md) | 最新Zynq三维双轴、T15/W16；31个RTL及Hann初始化 |
| PS/PYNQ与声纹 | [software/ps](../software/ps) | A当前维护；B历史迁移、优化与AF1入口见[B贡献](../document/evidence/speaker-report-materials/07-b-contribution-and-gaps-20261029.md) |
| 三维C/Python算法 | [software/tetra3d](../software/tetra3d) | 方向求解与软件接合；当前调用关系以实际源码为准 |
| 共享算法与历史STM32 | [software/common](../software/common)、[software/stm32](../software/stm32) | STM32路线已弃用，保留成果与失败，不作为当前硬件前置 |
| 研究与第三方模型适配 | [research](../research)、[第三方声明](../THIRD_PARTY.md) | CAM++、Silero等不记为团队原创模型；权重、个人模板不随资料发布 |

当前使用RTL与PS软件；没有单独交付的HLS主实现。工程复现见[build](../build/README.md)，不要从历史报告ZIP恢复源码覆盖当前产品。
