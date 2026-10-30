# 当前验证状态 — 2026-10-18

当前为 SoundSight 新仓库适配版。脚本与测试的数值、DMA 所有权和异常行为未改写；迁移版实际报告随交付包 evidence 提供，仓库原件位于 document/evidence/competition-skills-20261018。

历史 B 对准确版本 3ac597d 限定离线批准：55 个方法、57 个子测试、14 次模拟会话。该历史批准不自动覆盖迁移版，也不表示真实 PYNQ 已通过。

早期作者 50 项测试及独立前向试用见 [2026-09-13原记录](history/validation-status-20260913.md)；其中旧路径和旧日期属于历史，不是新命令。旧 D1/D2/D3 修复记录见 [repair-d1-d3.md](repair-d1-d3.md)。

新运行方式：在本 Skill 目录执行 python -B scripts/run_offline_tests.py --output <新的报告.json>。正常与超时模拟命令见 README.md。Python 标准库足够，不需要安装 PYNQ。

真实 PYNQ、Overlay 下载、物理 DMA、TLAST、板上性能、长稳和硬件故障恢复全部 NOT_RUN。软件模拟、配置检查、Git 合并和交付包不能替代这些结果。
