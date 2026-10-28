# 2026-10-28 远端 RTL / 三维 / 舵机同步

从远端 main `cd0cf53` 创建隔离分支 `codex/rtl-3d-servo-sync`。当前主工作目录仍保留原分支及所有声纹在途修改；不通过 reset/stash/clean 清工作区。声纹引擎、模型、私人模板/录音、私有 SD 包均不提交，远端已存在的声纹报告材料保持原 Git 对象。

## 真实检查

- `tests.json` 记录 23 组 Python 测试共 294 项，以及两组 C 数值检查的首次命令结果。Windows 其中 270 项通过，RAM 队列 24 项中的慢盘并发一项出现 WinError 5；完整 24 项随后在 WSL Debian/Linux 通过，见 `linux-buffered-tail.json`。这是主机假 MMIO 测试，非板测。没有为了 Windows 文件删除共享语义更改 Linux 产品队列。
- 三维 C：154 组数值对照、155 组 PS 能力位兼容、28 个桥接负例、15 个几何用例通过；原 C 断言 2110/2378/92270 见 `numeric_3d.log`，结果 `numeric-3d.json`。
- 二维 C：4705 断言、157 对照、6 个桥接负例通过，见 `numeric-2d.json`。首次误把三维测试的 `--cc` 参数传给二维脚本，CLI 在执行前拒绝；去掉不支持参数后用 PATH 中的本机 gcc 通过。原命令错误保留于 `numeric_2d.log`，不是产品失败。
- 公开 Python 源码按 Python 3.8 解析，源清单的32个条目存在。公共 RTL 与本地当前候选相同；没有重跑 XSim/综合/实现，复用 `../ps-dual-axis-20261028` 的原始证据和独立复核。
- 打包脚本实际生成临时三维软件增量，并核对 ZIP 内保护修复文件与正式源码字节一致，见 `increment-payload.json`。没有更新用户 SD 卡或私有完整包。

## 独立复核修复

只读上下文 `/root/remote_scope_review` 发现旧二维自动水平跟随入口可接受新双轴 HWH，从而绕过新三维入口的声纹许可。修复只在 PS：`run_capture.require_legacy_motion_hwh` 在旧自动入口启动 worker/MMIO 前拒绝 `DUAL_AXIS_ENABLE!=0`。`horizontal_motion.check_hwh` 默认执行同一检查；共用的 prepare/status/manual 元数据检查明确只核配置，不启动自动跟随，因此不受限制。

旧双核/直接采集共用 `prepare_args` 也执行检查；旧单轴 HWH 字段缺省或0仍可用。三维 `run --axes` 仍进入声纹许可路径，缺少 B 依赖直接失败，不降级到无门控动作。手动标定保持独立。新增双轴拒绝、旧单轴兼容、通用 readiness 通过的断言。

修复后的水平28、manual8、normal17、smp17、board15、SD batch6及安装包5项定向回归通过；不是新增不同测试总数，不能与294相加。原始结果见 `entry-guard-tests.json`、`guard-readiness-tests.json`。增量打包清单一并加入 `run_capture.py`、`horizontal_motion.py`、`board_tools.py` 和 A 侧 `speaker_permission.py`，避免更新旧目录时漏修。

## 可复现命令

在候选仓库根，用本机 Python / gcc / Git Bash；安装路径通过 PATH 或本地环境提供：

```text
python -B software/tetra3d/tests/test_online_3d.py
python -B software/tetra3d/tests/test_solver_3d_migration.py --cc <gcc> --output <结果JSON>
python -B software/tests/test_solver_migration.py --output <结果JSON>
python -B software/tests/test_horizontal_motion.py -v
python -B software/tests/test_manual_servo.py -v
python -B software/tests/test_buffered.py -v
python -B software/tests/test_dual_axis_tcl.py -v
python -B software/tests/test_dual_axis_report_tcl.py -v
python -B tools/package_three_d_update.py
```

Windows shell 测试需将本进程 `SOUNDSIGHT_TEST_SH` 指向可用 Bash；RAM 并发验证以 Linux 为目标。工具本机路径仅出现在原始执行证据，不是公共默认配置。

## 范围

不合并或关闭历史 PR #20/#21，不覆盖 B 的声纹分支。当前同步包含其中已接收的三维算法来源及后续 A 实现，以本次 PR 的最终文件为集成结果。

ARM 三维/联合并发、实际 CH 排列、机械双轴与声纹阈值均未新增板测。此次不改 RTL 功能或 ABI；公开包保留的许可是软件应用边界，并非不可绕过的硬件身份安全边界。

隔离 worktree 及其可再生成测试/ZIP输出只用于本轮发布；合并核验后移除。原本所有未归档声纹与工程成果保留；codex_out未创建。
