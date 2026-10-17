# 来源与原声明

- 项目原MIT许可证原文保留在LICENSE，未擅自更改署名。
- `project/ip/reference`的AMD官方IP模型、XCI及生成文件保留原头部声明；实际生成和仿真依赖合法安装的Vivado。它们不因进入项目就改为项目MIT许可。
- `hardware/reference`、板卡照片和`document/requirements/originals`保存已收到的原资料。来源/版本见相应README及原文件；本次未宣称已重新查询网站最新修订。
- `software/common`的冻结合同与S1来自STM32组随包原文。
- `research/speaker-verification`保留原第三方模型来源与锁定说明。模型权重和本地音频留在本地，不默认推送新Git。
- `research/competition-skills`是旧比赛成果参考，不自动安装，也不作为本项目工作流规则。

新仓库尚未由本任务公开或上传。后续公开发布时保留原文件声明，并按实际分发范围处理第三方附件。

## STM32 工程补充

`software/stm32/keil/soundsight_f407/Drivers` 来自探索者 V3.5 已用工程，含 ST HAL、ARM CMSIS 和 正点原子 SYSTEM 驱动；User/main.c 保留原模板声明。原头部许可/来源保持，不重新许可为项目 MIT。STM32 组自行实现 S2、soundsight_board/selftest 及测试接合；S1 仍为 software/common 唯一版本。构建工具与设备 Pack 使用本机合法安装，不随源码提交。
