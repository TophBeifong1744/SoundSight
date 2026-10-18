# B 复核说明：PYNQ Skill 离线收口

## 待复核范围

仅 `skill/pynq-overlay-dma-validation/`。本次是作者工作区自检交付，
未提交 Git、未发布、未连接板卡。当前没有可用于正式复核的本批提交 SHA；
后续由 A 的工作执行任务按批准范围整理并提供准确 SHA，B 再绑定该版本复核。
不要把整个共享工作区或其他任务未提交修改一起纳入。

重点文件：

- `scripts/dma_session.py`、`scripts/simulate_dma.py`、
  `tests/test_dma_session.py`：异常处理、缓存和所有权的实际代码/故障注入。
- `scripts/validate_profile.py`、`tests/test_validate_profile.py`：
  保留既有门禁，分离地址对齐与传输长度粒度。
- `scripts/compare_golden.py`：保留 JSON 大整数精度、避免容差溢出导致零差异误判；
  三项新回归来自独立试用发现的实际误报。
- `scripts/pynq_probe.py`：只保留保护入口，不再留下可被误启用的旧原型。
- `scripts/run_offline_tests.py`及随附测试报告：逐测试状态和源码哈希。
- `SKILL.md`、`README.md`及 references：输入审计、合同、边界与板测清单。

既有 `compare_golden.py`等未提交整改仍保留在本目录；正式打包时需要与本批
一起按准确差异审查，不能把“之前已存在”当成 B 已通过。

## 独立复跑

以下从 Skill 目录执行，Python 3.14 是本次实测环境，运行脚本只需标准库：

```sh
python -B scripts/run_offline_tests.py --output results/b-review-tests.json
python -B scripts/simulate_dma.py --contract references/example-session.json --output results/b-receive.json
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output results/b-timeout.json
python -B scripts/pynq_probe.py --profile references/example-profile.json --download --output results/b-board.json
```

期望前两条退出 0；第三条退出 1 且 FAIL/retained；第四条必须非零退出、
提示 BOARD_RUNNER_NOT_QUALIFIED 且不创建硬件报告。不要删除保护执行实板。
输出使用全新文件名，保留 B 的独立记录，不覆盖作者报告。

然后运行系统 skill-creator 的 `scripts/quick_validate.py <Skill目录>`
（需 PyYAML）以及限定目录的 `git diff --check`，核对英文路径、相对引用。
比较报告中的源码哈希与待复核提交中的实际文件；哈希不同则报告不覆盖该版本。

## 判定重点

1. 实际 current_build/HWH 是单向 S2MM；不能凭示例假造 MM2S、身份寄存器或
   PYNQ 镜像。输入审计中的 -2 是构建声明，不是新物理芯片鉴定。
2. RX arm 之前即进入“可能活动”状态；RX 已启动后 TX 抛异常或 Ctrl-C，
   不会先释放。状态读取失败不能被当成 idle/无错误。
3. 正常完成需 fresh transaction、完成标志、整体静止、实际包长；不能只看
   buffer 容量、单一 idle 或旧一次的完成位。
4. 缓存动作有真实字节模型检验；RX 初始化产生的 dirty 数据先处理，DMA 活动
   时无 CPU 读写；coherent 策略需分配器确认。
5. timeout/error/golden mismatch 均阻断下一次测试；abort 有单独授权和期限。
   未证明静止就保留；release 抛错不能盲目重试。保留 Python 引用不等于
   真实进程退出安全，实际硬件仍受保护。
6. mock 计时、TLAST=null、资源 NOT_RUN 必须清楚；不得把自检、静态 HWH
   或手填 hardware JSON 作为板上通过。完整 profile 与 lifecycle 报告不混用。

本次验收结论最多为“离线 Skill 实现及回归通过/不通过”；不包括 PYNQ 移植、
实板 DMA、系统验收、比赛加分批准。上板剩余项按 hardware-runbook.md 单独安排，
不向 C 追加任务。B 正式复核/合入遵从主流程，本说明不授予额外 Git 或板卡操作权限。

## 本轮文件清单

相对本轮开始，新增 10 个文件：

- scripts/dma_session.py
- scripts/simulate_dma.py
- scripts/run_offline_tests.py
- tests/test_dma_session.py
- references/example-session.json
- references/input-audit.md
- references/lifecycle-contract.md
- references/review-handoff.md
- evidence/offline-2026-09-13.json
- evidence/forward-test-2026-09-13.json

续改已有 10 个文件（其中 validation-status.md 在本轮开始时已未跟踪）：

- SKILL.md
- README.md
- scripts/compare_golden.py
- scripts/pynq_probe.py
- scripts/validate_profile.py
- tests/test_validate_profile.py
- references/example-profile.json
- references/hardware-runbook.md
- references/profile-contract.md
- references/validation-status.md

实际结果：作者与独立子代理各自复跑 50 项测试、39 个 subtest 均通过；
quick_validate、英文路径、引用、Python 3.8 语法与限定目录 whitespace 检查通过。
Python 3.14 是实测运行环境；没有把语法检查称为 Python 3.8 运行通过。
两份 evidence 中记录的脚本/测试/示例哈希均已与最终文件复核一致。
