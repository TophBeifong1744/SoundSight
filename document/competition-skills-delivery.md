# 两个比赛 Skills 的交付与复现

本次完成 SoundSight 新仓库适配。两个 Skill 的正式源码在 [research/competition-skills](../research/competition-skills/README.md)，独立比赛包在 [soundsight-competition-skills.zip](../release/output/soundsight-competition-skills.zip)。本包交付模块仿真和离线软件能力；真实 PYNQ 仍为待办，不安排上板。

## 改了什么

- PCM 示例改为引用同目录源码。源码从 C-RTL-003 的历史 examples-r2 仿真输入按原字节恢复，附来源和 MIT 许可；它是自包含示例，不另维护生产 RTL。
- 修复当前 README、XSim 命令、合同和状态说明中的旧仓库依赖；工具位置由命令行提供。
- 历史“待审”“已批准”和本次结果分开。旧验证原件、旧失败原文保留；历史 B 批准不自动覆盖本次迁移。
- PYNQ 的 DMA 核心、数值比较和原测试预期保持不变。旧 XSA/S2MM 案例明确标为历史，不描述当前 STM32 BD。
- 新增统一检查和打包工具；包内路径小写，完整包含依赖，不要求旧 Git 历史或另一个已安装 Skill。

## 本次实际验证

| 检查 | 仓库内实际结果 | 含空格和中文目录的独立导出包 |
|---|---|---|
| 迁移前 Python 测试 | 7 项中 1 项缺 PCM 源码而失败，已保存原错误 | 不适用 |
| 模块 runner 单测 | 7 项通过 | 7 项通过 |
| PYNQ 离线回归 | 55 个方法、57 个子测试，零失败/错误/跳过 | 同样通过，无跳过 |
| 正常接收 / 双超时 | 96 字节正确接收；双超时 FAIL、retained、session_blocked | 同样符合预期 |
| 板端入口 | 明确拒绝，无硬件报告产生 | 同样拒绝 |
| XSim 2025.2 | PCM792、elastic13800；数据/握手/延迟三种错误均检出；恢复后13800 | 六次全部符合相同期望 |

新证据、源码快照、准确命令、实际 Python/XSim 版本和首错见 [证据目录](evidence/competition-skills-20261018/README.md)。检查器与导出包的配套结果见 [package-check.json](evidence/competition-skills-20261018/package-check.json)。用例计数是检查次数，不能解读为覆盖所有 FPGA 场景。

## 如何重做包和检查

在仓库根目录运行，工具只用 Python 标准库：

```text
python -B release/pack_competition_skills.py --output <新的zip文件名>
python -B release/check_competition_skills.py --skills-root research/competition-skills --output <新的结果目录> --vivado-bin "<本机Vivado2025.2安装目录>/bin"
```

解压后进入包根目录，运行包内 check_competition_skills.py，--skills-root 改成 skills。省略 --vivado-bin 只跑离线测试，并把 XSim 标为 NOT_RUN。输出目录必须尚不存在；不覆盖历史证据。打包脚本不会运行仿真或硬件工具。

交付 ZIP 中的入口名是 skill.md；安装到要求 SKILL.md 的助手时恢复该文件名。不要把历史原件或开发工作流当作第三个本队原创 Skill。

## 比赛材料与范围

包内附使用说明、源码、测试、数值/接口合同、MIT 许可证、来源说明、当前失败及修复后结果、[可见 AI 纠错记录](competition-skills-ai-corrections.md)。导出文件来源由 source-map.json 说明，仅用于文件管理，不增加 RTL 身份链或运行哈希门槛。没有宣称 AI 效率提升百分比或比赛固定加分。

PYNQ 实板待办：真实板卡/镜像、Overlay 驱动、寄存器、DMA 完成/取消/缓存/中断/TLAST、失败恢复及实测性能。当前 FPGA＋STM32/SPI 主方案、PS 裸机初始化、综合实现或包验证均不替代这些工作。比赛提交平台及最新规则由参赛者最终核对；本次不代表已经向赛事提交。

原始仿真数据库只用于本次工作，必要输入/日志已归档；测试结束后清理本次可再生缓存与解压副本，保留正式源码、交付 ZIP 和证据。release/output 仅此固定比赛 ZIP 随 Git 提交，其余生成物继续忽略，不按日期堆包。
