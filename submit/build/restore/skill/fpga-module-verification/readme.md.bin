# FPGA 模块开发与仿真验证 Skill

把模块的接口要求变成 RTL、自检 testbench 和可复现的 XSim 验证。当前为 2026-10-18 新仓库适配版，两个示例均自包含，不需要 SoundSight 的生产工程。

## 如何使用

将本目录交给支持 Skills 的助手，说明模块要求、允许编辑范围、已有合同和实际仿真版本。入口为 [SKILL.md](SKILL.md)。如果只要求分析，Skill 不应自行改代码或执行硬件动作。

Python 3.10+、Vivado XSim 2025.2；Python 工具只用标准库。从本 Skill 目录运行：

```text
python -B -m unittest discover -s tests -v
python -B scripts/run_examples.py --vivado-bin "<本机Vivado安装目录>/bin" --output "<尚不存在的输出目录>"
```

也可单独运行 examples/elastic/case.json，命令见 [XSim说明](references/xsim-and-debug.md)。工具路径不是公共默认值；在 SoundSight 仓库中可参考本机被忽略的 tools.local.env。

## 示例、预期和失败判断

| 场景 | 预期 |
|---|---|
| PCM 符号扩展，位宽 2/24/32 | 792 次逐字比较通过 |
| 一槽 elastic，位宽 1/8/16 | 13800 次检查通过，覆盖每拍占用、valid/ready、背压、复位丢弃及计数守恒 |
| 故意翻转输出位 | 仿真阶段 FAIL，保留首个数据不匹配 |
| 故意拒绝空槽输入 | 仿真阶段 FAIL，检出接收/握手错误 |
| 故意改成两级流水 | 仿真阶段 FAIL，检出延迟和容量违约 |
| 恢复正确 elastic | 同样输入下 13800 次检查通过 |

退出 0 不能单独证明通过；runner 同时检查 fatal/error、唯一结束标记和非零检查次数。7 项 Python 单测还检查错版本、缺源、阶段失败、超时及拒绝覆盖旧结果。负例只修改临时 DUT 副本，不改正确示例或生产 RTL。

## 来源与当前验证状态

本队实现合同流程、runner、自检 TB 和故障演示；PCM 小模块原作者是 C（C-RTL-003）。[PCM合同](examples/pcm4/contract.md)和 provenance.json 说明原件来源。该模块已从历史真实仿真输入按原字节恢复，只作为教学/复用示例，不是当前生产 RTL 的第二份维护源。

历史 a7e1ea9 获 B 限定模块仿真批准，历史 PCM792、elastic13800 和错误检出结果有原报告。迁移版的实际结果以交付包 evidence 中本次报告为准；不把旧批准当成本次非作者批准。2026-09-23 的旧待审候选不是本次新仓库版本标识。

原始旧失败及审查材料仍保留于仓库归档；交付包附当前复跑的输入、命令、首错和结果。本次没有修改模块计算或 TB 判据，只修复依赖与交付说明。

## 限制与许可

只支持独立 Verilog/SystemVerilog 模块；不自动处理 include、厂商 IP 库、VHDL、完整 AXI、CDC、算法精度、综合实现或板测。elastic 的 ready 是组合逻辑，不能把示例称作寄存器隔离的生产方案。

[MIT许可证](LICENSE.txt)及原作者声明随包保留。skill-creator/xilinx-suite 只作制作辅助，不是本队成果或运行依赖。没有宣称 AI 效率提升百分比。比赛包把 SKILL.md/README.md/LICENSE.txt 映射为小写文件名；安装到要求 SKILL.md 的工具时恢复入口大小写即可，示例运行不依赖该名字。
