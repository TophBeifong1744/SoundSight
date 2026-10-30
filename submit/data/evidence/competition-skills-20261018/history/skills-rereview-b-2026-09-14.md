# B 修复候选独立复核（2026-09-14）

本记录由 B 独立运行后签署，批准只绑定下列准确 Git SHA 和目录。作者自检与历史代理评估没有直接转为批准；旧反馈仍固定在 `review/member-b-skills-20260914` 的 `0ef0355642ea8719d5e4cdde0a38c531550218d4`，原文、源码快照和日志均保留。

## SKL-002：PASS（限定离线实现）

- 准确批准 SHA：`3ac597d1d16982e0a5c5a114202ca8568dc28d8f`；仅 `skill/pynq-overlay-dma-validation/`。审批的是 static/mock 工具、文档及证据，真实 PYNQ 尚未准入。
- 原候选 `55039cf8bfab2bd6112192c8bd646d427a52a642` 的 D1/D2/D3 均关闭。本次没有修改作者实现；合入后该目录须与候选逐 Git blob 相同。
- 独立工作树 `F:/NUEC/review-worktrees/b-skl002-3ac597d`，起始干净 detached HEAD；本机 Windows，Python `D:/Python/python.exe` 3.13.0。测试输出新建，未覆盖作者 evidence。
- 证据唯一发布入口：本轮证据（历史引用：`../../results/skill-review/b-rereview-20260914/`），SHA-256/字节清单 `manifest-skl002.json`；原始 CLI 命令、cwd、退出码与 stdout/stderr 分别保存在每次运行子目录。

| 原问题 | 独立结论与证据 |
| --- | --- |
| D1 HWH 合同实例绑定 | 复用 B 原 thermal/missing-dma-ip.json、missing-control-ip.json 原字节，经新 CLI 均退出 1、FAIL、HWH_CONTRACT_IP。端口 NAME、参数 NAME、MODULENAME、完整层级的尾段不能冒充 MODULE 实例；合法完整层级路径及带前导斜线路径通过。变体 HWH 与 manifest 重新配套哈希，避免用哈希错误代替实例检查。见 d-independent/ 相应输入、command.json、result.json 与日志。 |
| D2 同 ID 覆盖失败 | 原 duplicate-evidence.json 经新 CLI 退出 1、FAIL、DMA_RUN_DUPLICATE。坏→好、好→坏、好→好、坏→坏、好→坏→好均失败；合法唯一 ID 正常证据通过。逐条拒绝重复，不允许后条覆写掩盖失败。 |
| D3 独立分发说明 | README 明示原创/第三方来源、MIT 边界、路径大小写映射及项目导出规则链接；LICENSE.txt 与仓库根 MIT 署名及全文逐字节一致。不替 AMD/IP、板厂、PYNQ 等授权；仅批准导出方案说明，未验收最终竞赛导出包。 |

实际命令（前三条 cwd 为准确候选的 Skill 目录）：

```text
D:/Python/python.exe -B scripts/run_offline_tests.py --output results/b-rereview-tests-new.json
D:/Python/python.exe -B scripts/simulate_dma.py --contract references/example-session.json --output results/b-rereview-receive-new.json
D:/Python/python.exe -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output results/b-rereview-timeout-new.json
D:/Python/python.exe -B F:/NUEC/review-evidence/skills-b-rereview-20260914/independent_d.py F:/NUEC/review-worktrees/b-skl002-3ac597d/skill/pynq-overlay-dma-validation
F:/STUDY/IT/Anaconda3/python.exe -X utf8 -B C:/Users/BryanZheng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/pynq-overlay-dma-validation
```

独立运行结果：55 个测试方法、57 个 subtest，0 failure/error/skip；正常模拟退出 0，96 bytes 与 golden 精确一致。双超时退出 1、FAIL、retained、session_blocked，trace 无 rx.read/rx.release，属于预期负例，不是回归失败。`independent_d.py` 的 60 项检查全部通过（包含原输入字节核对，不能说成 60 个新测试方法）；thermal signed16/96 bytes、pixel uint32/128 bytes 各 7 个会话，共 14 次，同一核心复用。

会话包含正常、缓存陈旧、部分启动后停止失败、状态读取失败、双超时、短输出、释放失败；失败后再次调用不增加 adapter 操作，未确认静止时不读/不释放，释放异常不重复释放。独立检查 2**120 的一整数差、明确容差、浮点溢出边界及短输出。board guard 退出 2、BOARD_RUNNER_NOT_QUALIFIED，未创建报告或接触板卡。现有测试同时覆盖失效状态、缓存所有权、停止/重复释放和下一轮阻断。

结构验证使用已有 Python 3.7.0/PyYAML 3.13，quick_validate 返回 Skill is valid；Python 3.13 环境缺 PyYAML，没有安装依赖。结构验证不替代行为测试。

`repair-manifest.json` 全部 105 项与准确提交 Git blob、工作树字节及字节数一致，旧 manifest 和旧日志没有改写。旧反馈输入亦逐字节复用。真实工程仍为 simple S2MM-only，无 MM2S/DRE，不因合成 loopback profile 的通过虚构身份寄存器、PYNQ 镜像或实板能力；模拟时钟数据不是硬件吞吐或加速收益。

## 共用未测边界与发布约束

真实 PYNQ/Overlay/物理 DMA、综合资源/时序、CDC、板测、整机、最终竞赛导出、10 月 1 日 Skill 总验收：全部 NOT_RUN。本次没有采购、烧板、修改生产 RTL/BD/XDC，也未改变 B 的 9 月 18 日算法主线或 H1/H2/H3，没有给 C 新增任务。限定实现批准不保证比赛固定加分。

候选分支在合入前再次直接核实准确 SHA；main 从执行时远端最新版本接入，不回退历史版本。维护入口及本复核记录由 B 随限定合入更新，作者实现和历史证据原字节保留。发布 SHA 和合入后验证在后续发布核对中补记。

A 共享 main 的 162 项旧候选混合差异位于 A 电脑，B 未处理、未代签清理或同步。A 需在本机先保留/比对独有材料，再安全同步 main、核对已修改/未跟踪/忽略项；不要求 reset 脏目录。仓库中有报告不等于成员已收到消息，本次未用工具通知 A/C。

SKL-002 合入后验证：在真实本地 main 工作树的活动 Skill 目录再次运行全部离线测试，55 方法/57 subtest、0 failure/error/skip；源码路径与候选 Git blob 一致。实际命令与日志见证据 skl002-postmerge-units/ 及 skl002-postmerge-tests.json。原脚本报告中的 AUTHOR_SELF_TEST_NOT_B_ACCEPTANCE 为固定模板字段，B 本次批准仅由本签署记录给出，未改原始报告。

## SKL-001：PASS（限定模块开发与实际仿真）

准确批准 SHA：`a7e1ea976da91ba735af5c0a79fffdc7d10c121f`；批准范围仅 `skill/fpga-module-verification/` 和 `task-packages/PKG-A-SKILLS/`。这是 0.3.0 的 S1 修复，原候选 `c562466805aff08201cd457cc2e6ee7464a3566f` 的旧批准不能覆盖新提交。B 没有修改作者实现，批准的源码和原始证据按候选字节进入 main。

独立 clean detached 工作树：`F:/NUEC/review-worktrees/b-skl001-a7e1ea9`。Windows / Python `D:/Python/python.exe` 3.13.0；使用明确路径 `D:/AMD/2025.2/Vivado/bin` 的实际 XSim 2025.2。SW Build 6299465 沿用同一安装环境的原始版本记录；本轮每次 xvlog --version 均实际返回 Vivado Simulator v2025.2，没有借 PATH 选旧工具。

### S1 关闭与实际执行

```text
D:/Python/python.exe -B -m unittest discover -s skill/fpga-module-verification/tests -v
D:/Python/python.exe -B skill/fpga-module-verification/scripts/run_examples.py --vivado-bin D:/AMD/2025.2/Vivado/bin --output F:/NUEC/review-evidence/skills-b-rereview-20260914/xsim-examples
D:/Python/python.exe -B F:/NUEC/review-evidence/skills-b-rereview-20260914/independent_s.py
F:/STUDY/IT/Anaconda3/python.exe -X utf8 -B C:/Users/BryanZheng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/fpga-module-verification
```

前两条从新候选仓库根执行。每次实际 argv/cwd/退出码和完整日志在对应 command.json/stdout.log/stderr.log；XSim 每阶段日志、源输入快照、合同/case 及 result.json 随证据保存。

| 独立执行 | 实际结果 / 证据 |
| --- | --- |
| 运行器单元测试 | 7 项通过；skl001-units/。涵盖工具/阶段/超时错误分类、缺失/多重 PASS、晚 fatal、零检查及拒绝覆盖旧输出。 |
| 正确 PCM | 792 次比较通过；xsim-examples/pcm4/。符号扩展，宽度 2/24/32。 |
| 正确及恢复 elastic | 各 13800 次实际检查通过；每个宽度 1/8/16 均 sent177 = consumed176 + discarded1 + pending0；xsim-examples/elastic/、restored/。 |
| 数据、ready、两级错误 | 全部编译/展开成功，在仿真阶段被检出；xsim-examples/bad_data/、bad_ready/、two_stage/。两级首错 cycle=2、after_edge=1，expected valid=1 / actual=0。 |
| B 原始两级副本配新 TB | DUT 复用旧反馈原件，只把 TB 换为准确新候选；同样 cycle=2、after_edge=1 检出 one_edge_valid；s-independent/b-two-stage-new-tb/。 |
| B 独立延迟见证 | 正确源通过 2 项；同一两级副本在首个接收边沿后 valid=0/data=00，预期 1/5a，仿真失败；s-independent/b-witness-correct/、b-witness-two-stage/。 |
| 合法复位 ready 变体 | 只在复位期间拉低 ready，原激励/新 TB 仍通过 13800 项；s-independent/reset-ready-low/。没有增加合同外复位 ready 限制。 |
| 容量与未知态变体 | 满槽仍 ready 被 slot_ready 检出；payload X、payload Z、valid X 各在仿真阶段被检出；s-independent/ 下同名目录。 |

共执行示例 6 次和独立针对性 XSim 8 次，14 次均符合预期。所有预期负例要求 version/compile/elaborate 返回 0 且未超时，stage=simulate、FAIL_SIMULATION、退出 1；不以编译或工具启动失败充当故障检出。计数按实际日志记录，13800 不是人为凑数门槛。

代码审阅与同输入实测相互印证：`check_slot(0)` 在正边沿 NBA 前检查旧槽，`check_slot(1)` 在 #1 后检查新槽。占用由接收/消费的独立队列计算，严格 0/1，valid 必须对应占用，有效数据用四态全等比较；正常 ready 必须等于空槽或下游 ready。故两级到达延迟和两槽容量不能仅靠末端事务顺序蒙混通过。

负边沿驱动、正边沿握手和 NBA 后观察没有竞争；同步低有效复位优先，丢弃在途事务计入 discarded，复位数据清零；背压期间保持 valid/data、空槽接收、每拍启动、同拍消费/替换均保留。固定种子、原合同和激励未放宽，原四拍排空未缩短。计数每拍核对 sent=consumed+discarded+pending，最终 pending0。r1 的 13806 属于作者早期错误约束记录，本轮最终依据 r2，不要求恢复那条限制。

### 版本、历史复用与文档

repair-manifest 的 504 项全部与新提交 Git blob、检出文件原字节及字节数一致；作者 fix-r2/examples-r2/regressions-r2 对应最终源码，旧 r1/旧日志/旧清单保留其历史身份。B 对 14 次新运行核对了 191 条日志、快照、工具阶段、源码和计数关联；见 skl001-result-audit-r2.json。

首次辅助审计将 PCM 工作树字节直接等同于 Git blob，报告 1 项不一致（skl001-result-audit/ 与原脚本/JSON 保留）。原因是该仓库外部引用的生产 PCM 文件在 Windows 检出时由 LF 转 CRLF；实际仿真输入快照与工作树逐字节相同，git hash-object --path 清理过滤得到的 a300f74c48fe68eb34247d7a6f1cf97a28778f58 与候选 blob 完全一致，差异只为 CRLF。新增 r2 审计分别记录精确字节、检出转换和 Git 身份，191 项通过；没有改原始源码、日志或哈希清单掩盖差异。

旧版 B 陌生 signed8 饱和加法评测本轮 NOT_RUN，明确复用 `c562466805aff08201cd457cc2e6ee7464a3566f` 上的历史结果：隔离执行方只获 Skill、需求和必要输入；未知 -128+-1 故障定位后，同激励修复复测 66343 笔、337372 检查，B 自算全部 65536 组 golden 与实测零差异。旧原始失败、修复源码、结果及 golden 均保存在[固定反馈提交](https://github.com/TophBeifong1744/Competition_fpga/tree/0ef0355642ea8719d5e4cdde0a38c531550218d4/results/skill-review/b-20260914)。本次未修改旧 reproduce.py 版本锁，也未冒称陌生评测在新 SHA 重跑；按用户指定只复用原独立延迟见证并补针对性变体。核心 SKILL.md、run_xsim.py 相对旧候选保持原字节。

README 对场景、调用、失效条件、效果、C 的 PCM 来源/MIT 归属、独立导出规则及可见 AI 纠错说明足够；结构验证通过。PCM 示例需仓库已有的单个维护源或带归属导出；独立 elastic 可脱离声学工程使用。旧工程协作 Skill 保持退役，例子未接入生产 RTL。

## 分项发布进展

SKL-002 已先行独立合入并非强制发布：`357265f3744c343355bb646e2b0e56ed352bf0e7`（父提交 57c50e6 与准确候选 3ac597d）。发布后实际本地 main 工作树 `F:/NUEC/review-worktrees/member-b-to-a-pkg-b-alg` 的 main、origin/main 及直接 gh API 查询远端均为该 SHA，0/0，工作树干净；Skill 范围与批准候选逐 blob 一致。SKL-001 不作为该次发布的前提。

SKL-001 合入后验证：从实际本地 main 仓库根再次执行同一 7 项单元测试及 run_examples.py，使用新的 xsim-postmerge 输出目录。PCM792、elastic/restored 各13800、三种故障均在仿真阶段检出，6 次全部符合预期。命令和日志见 skl001-postmerge-units/、skl001-postmerge-examples/、xsim-postmerge/。合并索引中的两个批准目录与 a7e1ea9 无差异。

## 发布后核对与本批收尾（B 本机）

| 项目 | 实际结果 |
| --- | --- |
| 分项 main 合入 | SKL-002：`357265f3744c343355bb646e2b0e56ed352bf0e7`；SKL-001：`d2cff38c19e06238bed9d4a195f72640527a1c12`。各自合并提交的第二父提交为准确批准候选，历史完整可恢复。 |
| 推送方法 | Git HTTPS 网络路径不可用，使用已有 gh Git Data API 上传新对象；返回 blob/tree/commit SHA 均与本地对象相同，更新 main 使用 force=false，发布前再次检查远端没有并发变化。未强推。 |
| 主线核对 | 2026-09-14T11:05:56.610706+00:00，实际 main 工作树 main、origin/main、直接远端 main 均为 d2cff38，0/0；从脏 develop 查询的 main/origin/main 也相同，未切换其当前分支。主线工作树干净。此收尾记录补交后再核对，最终 SHA 由用户回报给出，避免文件自引用。 |
| 提交内容验证 | 从已合入 Git 提交读取 B 证据清单621项及作者清单504+105项，共1230条，字节/长度/哈希全部匹配；两项批准目录与准确候选无 blob 差异；rtl/tb/sim/ps/vivado/hardware/deliverables 未改。活动入口及新报告本地链接可达。 |
| 本批有用材料 | 所有新源码输入、命令、原始失败/修复后日志、单元/结构/负例结果、合入后测试、哈希与清理核对已纳入本轮证据。检查已修改、暂存、未跟踪和忽略项；候选工作树中6份额外结果均已逐字节入库。本批新增未保存或未说明材料为0。 |
| 保留的既有工作 | F:/NUEC/develop 仍在 feature/member-b-algorithm，HEAD 57b86e043410c43aeca8d7421e0afe4ada3a8788，原有198项差异保留。其中9项旧 PYNQ 文件经 CRLF 规范化与历史 main 57c50e6 匹配，属于此前基线副本，已经可从Git恢复，没有夹入新候选或为了清零而删除。它们不作为本轮活动源码。其他长期/算法工作树均保留。 |
| 分支清理 | 删除两条已完整批准且无后续提交的远端短期候选分支 codex/toph/skl001-module-verification-20260914、codex/toph/skl002-pynq-validation-20260914；直接查询均404。B 本地不存在同名 heads/远端跟踪引用，未虚报本地删除。准确候选仍可由 main 合并父链恢复。 |
| 复核副本清理 | 删除 b-skl001-a7e1ea9、b-skl002-3ac597d、b-skl001-c562466、b-skl002-55039cf 四个已结束工作树。清理18个重复运行目录前逐字节核对599份已发布文件；可重建 simulator 缓存按路径/字节数/哈希登记后删除，日志/输入/结果均保留。 |
| 历史保留 | 旧反馈远端仍为0ef0355642ea8719d5e4cdde0a38c531550218d4；反馈分支和其只读证据工作树、旧陌生模块/golden、作者r1/r2证据及旧归档均保留。F:/NUEC/review-evidence/skills-b-rereview-20260914 保留Git API获取/发布控制缓存与辅助脚本；可复核结果唯一入口为已发布 results/skill-review/b-rereview-20260914，不保留另一个活动工程。 |
| A 设备边界 | 无法访问 A 电脑，未处理或代签其162项混合旧候选差异。A 本机仍需对照新 main 保存/分类独有材料并安全同步、检查已修改/未跟踪/忽略项；不得以 reset 脏目录方式强行清零。 |
| 最终状态 | 两项限定实现已独立批准并分别发布；B 本批材料收尾完成。A 设备核对由A完成，不阻塞已获准的离线/模块发布。本记录在仓库不等于其他成员已收到消息，本轮未向A/C发送工具消息。 |

原始发布响应与核对见 closeout/；manifest-closeout.json 单独绑定本次新增收尾资料，先前 manifest-all.json、manifest-skl002.json 及作者所有历史日志/清单保持原字节。
