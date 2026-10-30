# 比赛 Skills

这两个目录是 SoundSight 的比赛 Skill 正式维护入口。当前批次是 2026-10-18 新仓库适配；历史限定批准与本次迁移验证分开。通用 fpga-team-workflow/run-fpga-workflow 是开发辅助工具，不计作本队原创 Skill。

| Skill | 能做什么 | 能力边界 |
|---|---|---|
| [fpga-module-verification](fpga-module-verification/readme.md) | 模块合同、RTL/TB、真实 XSim、错误定位与复测 | 单模块仿真，不代表综合、时序、CDC 或上板 |
| [pynq-overlay-dma-validation](pynq-overlay-dma-validation/readme.md) | Overlay 配置与数据检查、DMA 生命周期和故障模拟 | static/mock；真实 PYNQ 适配器及实板仍待办 |

每个 Skill 自带代码、测试、说明和许可证，可以脱离仓库运行。工具路径由使用者提供，无旧仓库、旧工程或历史 Git 对象依赖。

迁移结果、准确命令、交付包及可见纠错记录见[本次交付说明](../report/competition-skills-delivery.md)。历史批准只绑定当时版本，不能自动批准迁移版；历史审查原件见 document/evidence/competition-skills-20261018/history（仓库根目录下）。
