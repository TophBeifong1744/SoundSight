# SKL-002：D1/D2/D3 修复回交（2026-09-14）

作者修复与自检通过，等待 B 固定新远端 SHA 复核；没有批准 SHA，没有合入 main。
旧候选 `55039cf8bfab2bd6112192c8bd646d427a52a642`；分支 `codex/toph/skl002-pynq-validation-20260914`。
B 反馈固定为 `0ef0355642ea8719d5e4cdde0a38c531550218d4`；本提交准确身份由 Git HEAD 和直接远端核对提供，不在文件内自引用。

## 逐项结果

| 问题 | 修复位置 / 判据 | 相同 B 输入前后 |
| --- | --- | --- |
| D1 合同 IP 不在 HWH 仍 PASS | `scripts/validate_profile.py` 的 MODULE inventory、`validate_overlay`；绑定两个实际合同实例，不只 required_ip。忽略端口/参数名/IP类型；层级实例用 FULLNAME 完整路径 | `missing-dma-ip.json`、`missing-control-ip.json`：旧 CLI 0/PASS → 新 CLI 1/FAIL，`HWH_CONTRACT_IP` |
| D2 重复 ID 覆盖失败 | `validate_run_evidence` 逐条校验，任何重复 ID 报 `DMA_RUN_DUPLICATE`，不覆盖原条目；同时拒绝不合法记录/ID | B `thermal/duplicate-evidence.json`：旧 CLI 0/PASS → 新 CLI 1/FAIL；单元测试覆盖坏→好、好→坏、好→好、坏→坏、好→坏→好 |
| D3 独立分发缺说明 | README 来源/许可/路径映射和项目规则入口；随包 `LICENSE.txt` 保留根 MIT 原署名/全文 | 文档及许可完整性核对，不把第三方软件/板厂资料归入本队 MIT |

全部测试：55 个测试方法、57 个 subtest，0 failure/error/skip；既有 50 项测试保留，新增 5 项方法。
两套 B 输入：thermal signed16/96 bytes 与 pixel uint32/128 bytes，外部数据逐项打包后与 B golden.bin 及哈希一致。
两套各运行正常、缓存陈旧、部分启动+停止失败、状态不可读、双超时、短包、释放失败，共 14 次 session；失败后的下一次执行不得产生新 adapter 操作，释放最多一次。
所要求的正常命令退出 0；timeout+abort-timeout 退出 1/FAIL，retained/session_blocked，未读 RX 或释放。board guard 退出 2，`BOARD_RUNNER_NOT_QUALIFIED`，未访问真实板卡。
既有大整数、容差、短输出、缓存、停止、重复释放/阻断等回归继续通过；具体测试名称见 `evidence/fix-r1/unit.json`。

## 原始证据、命令和完整性

全部新证据在 `evidence/fix-r1/`。`summary.json` 含实际 argv/cwd/退出码、源码输入来源、报告及 stdout/stderr 哈希；每条 CLI 的 command.json 和原始日志另存对应子目录。
`b-inputs` 是 B 原件的字节级复制，旧 checker 位于 `old-input`，只供前后复现，不是活动源。
未改 B 的 `reproduce.py` 或版本锁，没有修改原报告/清单来让哈希通过；新 `repair-manifest.json` 绑定本轮材料。

从 Skill 目录执行，实际用 Python 3.12.14；本次输出分别为 `evidence/fix-r1/unit.json`、`receive.json`、`timeout.json`：

```text
python -B scripts/run_offline_tests.py --output results/tests-new.json
python -B scripts/simulate_dma.py --contract references/example-session.json --output results/receive-new.json
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output results/timeout-new.json
python -B evidence/replay_d_fixes.py --output evidence/replay-new --validator <system-skill-creator/quick_validate.py> --validator-python <python-with-existing-pyyaml>
```

最后一条重放全部同输入对照、必跑命令、两套格式与结构/guard 检查；需本仓库对象库包含 B 准确提交。普通离线工具不依赖 Git 或 B 分支。
结构检查实际用已有 Python 3.14.6/PyYAML，通过；没有安装工具。原作者历史“未发布/未提交”字段保留，不代表本轮状态。

## 未测 / 发布边界

仅改 `skill/pynq-overlay-dma-validation/`，未改另一 Skill、根索引、生产 RTL/BD/XDC、Vitis、镜像或原始证据。当前真实工程仍为 simple S2MM-only；完整 profile 的 loopback/RO 身份要求不构成该工程可部署声明。
模拟时钟不是硬件吞吐或加速收益；PYNQ 镜像/驱动、Overlay、真实 DMA/TLAST、综合时序/CDC、板测、长稳、整机、10/1 总验收均 NOT_RUN。最终竞赛导出/安装演练也未执行；仅核对了提交映射、许可文本和核心离线依赖。
新修复进入原候选分支，B 复核通过前不合入 main、不删分支；共享 main 原混合改动未处理或覆盖。反馈已在仓库不等于 B 收到消息，由用户复制发布回报交接。
