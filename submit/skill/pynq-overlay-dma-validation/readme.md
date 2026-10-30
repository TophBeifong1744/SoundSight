# PYNQ Overlay 与 DMA 验证 Skill

当前为 2026-10-18 新仓库适配版：能运行的离线配置检查、golden 数据比较和 DMA 故障模拟工具。**没有真实 PYNQ 驱动适配器，本次不安排板测。**

## 如何使用

入口为 [SKILL.md](skill.md)。Python 运行工具只用标准库；从本 Skill 目录运行：

```text
python -B scripts/run_offline_tests.py --output <新的测试报告.json>
python -B scripts/simulate_dma.py --contract references/example-session.json --output <新的正常结果.json>
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output <新的超时结果.json>
python -B scripts/validate_profile.py --profile <实际profile.json> --mode offline --output <新的配置报告.json>
python -B scripts/compare_golden.py --expected <预期.bin> --actual <实际.bin> --format bytes --output <新的比较报告.json>
```

前两条应退出 0，双超时负例应退出 1、FAIL、保留缓冲区且阻断下次运行。所有输出使用新文件名。示例 session 可以直接跑；example-profile.json 中的硬件路径是待填模板，不是可下载工程。

[Profile合同](references/profile-contract.md)与[DMA生命周期合同](references/lifecycle-contract.md)是两种不同输入，不混用报告。full profile 当前要求 loopback 与 RO 身份合同；真实项目没有的 MM2S 或寄存器不能靠编造补齐。

## 实际代码与检查

- dma_session.py 管理缓冲区所有权、缓存、启动、完成、超时与释放；未证明整体静止不读、不释放。
- simulate_dma.py 使用 CPU/设备分离的字节模型，模拟缓存陈旧、短输出、部分启动、停止/状态/释放失败。
- validate_profile.py 检查 HWH 中真实实例名称、配置和证据结构，拒绝重复 ID 覆盖失败记录。
- compare_golden.py 保留 JSON 大整数精度；小数仍按 binary64 解析，不宣称任意精度十进制。
- pynq_probe.py 只有拒绝执行入口，不导入 PYNQ、不分配硬件缓冲、不做 MMIO 或下载。

历史 B 在 3ac597d 上限定批准离线实现：55 方法、57 子测试、14 个不同格式会话。当前版本的复跑结果、旧记录及未测范围见[验证状态](references/validation-status.md)。本次迁移不修改 DMA 核心和原测试预期。

## 与当前 SoundSight 的关系

旧输入审计中的单向 S2MM、XSA 和路径均是历史案例，**不是当前 FPGA＋STM32 BD 的描述**。当前工程采用 STM32/SPI，PS 裸机初始化并不代表 PYNQ 或 DMA 验证完成。此 Skill 可作为独立通用离线成果继续交付。

后续真实 PYNQ 适配器、Overlay/寄存器访问、DMA/TLAST/缓存/中断、超时恢复和性能测试保持待办，详见[板测待办](references/hardware-runbook.md)。不安排上板，不删除保护入口，不把模拟时间当作吞吐或延迟实测。

## 来源、失败和独立分发

本队原创部分是 profile 检查、精确 golden 比较、DMA 生命周期与模拟后端。历史 D1/D2/D3 和大整数误判的发现、修复与负例保存在 evidence；这些原日志保留旧日期和路径，只作历史证据，不是运行依赖。evidence/replay_d_fixes.py 属于旧 Git 取证脚本，依赖历史 Git 对象，不是当前入口，也不进入新交付包；当前重跑用 scripts 和 tests。

[MIT许可证](license.txt)保持原署名。PYNQ、AMD、Python及板厂资料不是本队原创；合成 bit/HWH 只是测试字节，不能烧录。提交包使用小写英文路径，保留源码、测试、合同、许可证和本次证据；不包含官方资料 PDF、真实板厂工程或个人工具路径依赖。安装 Skill 时按工具需要把 skill.md 恢复为 SKILL.md。
