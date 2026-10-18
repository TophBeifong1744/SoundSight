# SKL-001：S1 修复回交（2026-09-14）

状态：作者修复与自检通过，等待 B 固定新远端 SHA 复核；无批准 SHA，不合入 main。
旧候选 `c562466805aff08201cd457cc2e6ee7464a3566f`；分支 `codex/toph/skl001-module-verification-20260914`。
B 反馈 `0ef0355642ea8719d5e4cdde0a38c531550218d4`，不修改其报告、脚本或任何原始证据。
本提交准确身份以 Git HEAD/直接远端核对和发布回报为准，避免在提交内写自引用 SHA。

## 修复与同输入对照

`skill/fpga-module-verification/examples/elastic/tb_elastic.sv` 保持一槽、一沿延迟合同及原激励不变。
在上升沿 NBA 前检查旧槽，在 NBA 后检查刚接收的事务已经呈现在输出；有效性和数据必须匹配 accepted 队列。
队列容量限 0/1，空槽和占用状态的 ready 必须符合合同；复位优先丢弃 pending，计数恒等式为 sent=consumed+discarded+pending。
保留 `!==` 的 X/Z 拒绝、负边沿驱动、stall hold、固定种子、32 拍全速、400 拍随机、watchdog 和原四拍排空，未靠缩短 drain 或放宽合同规避。

| 检查 | 实际结果 | 新证据 |
| --- | --- | --- |
| B 原两级 DUT + 原 TB/case/contract | 1149 checks，复现旧误 PASS | `evidence/fix-r2/old-tb/` |
| 同一 B DUT/case/contract + 修复 TB | 编译/展开成功，仿真 FAIL：cycle=2, after_edge=1, expected valid=1, actual=0 | `evidence/fix-r2/new-tb/` |
| B 独立最小延迟 TB + 正确/两级 DUT | 正确通过 2 checks；两级在仿真阶段失败 | `evidence/fix-r2/b-good/`、`b-bad/` |
| 正确 PCM，width 2/24/32 | 792 比较通过 | `evidence/examples-r2/pcm4/` |
| 正确/恢复 elastic，width 1/8/16 | 各 13800 checks；每宽 sent177=consumed176+discarded1，pending0 | `evidence/examples-r2/elastic/`、`restored/` |
| 数据错误、ready 错误、两级错误 | 均编译/展开成功，在仿真阶段 FAIL | `evidence/examples-r2/bad_data/`、`bad_ready/`、`two_stage/` |
| X、Z 有效载荷及满槽仍 ready 的故障副本 | 均在仿真阶段检出；前两者为 one_edge_data，后者为 slot_ready | `evidence/regressions-r2/` |
| runner 单元测试、结构检查 | 7 项单元测试通过，结构检查通过 | `evidence/regressions-r2/unit/`、`structure/` |

上述数字是实际断言执行数，不是独立场景数或准确率。三种内置故障在 `run_examples.py` 生成临时副本，生产 RTL 没有修改。
通用 TB 指南补充“排队比对不能替代逐拍延迟/容量验证”，未扩展为 CDC 或整机验证。

`*-r1` 为本轮早期自检原件，13806 checks 包含复位期间 ready 的多余断言。
审读发现原合同仅定义复位 valid/data，没有规定复位 ready，因此去掉该额外限制后完整复跑到 `*-r2`。
最终源码对应 r2 的 13800 checks；r1 原始输入、日志、结果未覆盖。不是放宽一沿/一槽合同。

## 复现与环境

在该候选仓库根运行；所有 output 必须全新。

```text
python -B -m unittest discover -s skill/fpga-module-verification/tests -v
python -B skill/fpga-module-verification/scripts/run_examples.py --vivado-bin F:/AMD/2025.2/Vivado/bin --output task-packages/PKG-A-SKILLS/evidence/examples-new
python -B task-packages/PKG-A-SKILLS/replay_s1.py --vivado-bin F:/AMD/2025.2/Vivado/bin --output task-packages/PKG-A-SKILLS/evidence/replay-new
python -B task-packages/PKG-A-SKILLS/check_s1_regressions.py --vivado-bin F:/AMD/2025.2/Vivado/bin --output task-packages/PKG-A-SKILLS/evidence/regressions-new --validator <system-skill-creator/quick_validate.py> --validator-python <python-with-existing-pyyaml>
```

实际 Python 3.12.14；Vivado/XSim 2025.2，SW Build 6299465；结构验证用已有 Python 3.14.6/PyYAML，未安装依赖。
`replay_s1.py` 只从 B 准确提交提取指定原始输入，不运行或改写 B 锁定旧版本的 `reproduce.py`。
`b-inputs.json` 绑定复制件与 B Git 路径/哈希。每个 XSim result 绑定输入快照、合同、命令及原始日志。
新 `repair-manifest.json` 仅绑定本轮交付，不改旧 `manifest.json`；后者只能用于原候选历史，不能要求新源码匹配旧哈希。

## 交付、公开边界与未测项

仅更改此 Skill 及 `task-packages/PKG-A-SKILLS/`。保留一份活动源；`inputs`/B 副本为取证快照，不是第二套开发工程。
可重建 XSim `work/` 缓存不随提交，原始日志、源码快照、result 和合同保留。没有删除历史失败或旧包。
自有及 B 测试材料沿仓库 MIT；PCM 保留 C-RTL-003 来源。按 Skill README 与最新 main `docs/skills-delivery-plan.md` 的映射导出，不恢复退役协作 Skill。
本轮未执行最终竞赛压缩包导出/安装演练；不是 10/1 Skill 总验收。
综合、资源、STA、CDC、真实 PYNQ、板测、长稳、整机实时全部 NOT_RUN。B 既有陌生模块评测引用原反馈，本轮不冒称重新独立盲测。
共享 main 的旧混合差异保持不动；新修复只在隔离候选树。正式复核通过后再按 team-workflow 限定合入、验证及清理。
