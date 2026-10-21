# 手工 PS BD 补齐脚本核查

本次只准备和验证 `project/bd/complete_manual_ps.tcl`。AI 没有打开或写入用户的外部 Vivado 工程，没有运行综合、实现、下载或硬件复位。

## 实际输入

- 只读工程：`F:/AMD/work/SoundSight_PS/SoundSight_PS.xpr`。
- 已保存 BD：`SoundSight_PS.srcs/sources_1/bd/soundsight_stm32_bd/soundsight_stm32_bd.bd`，读取时修改时间为 2026-10-20 20:40:51。
- BD 有 13 个单元；`ps_link` 引用 `bd_ps_link`；SPI 外部端口已移除；PWM 已连接；AXI 和特征握手尚未连接。
- 使用同一外部工程中实际复制的 RTL、Hann 数据和两个独立 FFT XCI。工程仍登记 STM32 两份 XDC，脚本负责换成仓库 PS 版。
- 器件 `xc7z020clg400-2`，Vivado 2025.2。

`before.bd`、`after.bd` 是本次输入/结果证据，不是用于直接打开的新工程入口。其原生相对生成路径保持原样。

## 执行与结果

测试工作目录为仓库的 `simulation/work/ps-bd-completion`；所有工程准备在该目录的隔离副本执行。`executed-check.tcl` 保存实际执行的检查程序。

实际命令：

```text
python simulation/work/ps-bd-completion/run_check.py
vivado -mode batch -notrace -source <测试工作目录>/check.tcl -log <测试工作目录>/vivado.log -journal <测试工作目录>/vivado.jou
```

原始检查程序中的相对路径按上述测试工作目录计算；归档文件只记录当次执行，不应直接在本证据目录 source。

最终结果：

- 原生 Validate 与 Wrapper 生成通过；同一脚本连续执行两次通过，均为 19 个 BD 单元。
- 386 项 PS DDR/MIO/外设使能及分组参数保持不变。
- 新脚本连接结果与既有 `document/design/ps/PS平台.txt` 的 37 行网络/接口表一致。外部 DDR/FIXED_IO 保留用户命名，没有强制添加 `_0`。
- 以故意连接 `ps_link/rst_n` 与 `aresetn` 为负例，脚本拒绝合并两个不同网络。
- 工程约束只登记 PS 两份 XDC；原 STM32 约束文件和备份保留。
- 工具本次分配地址 `0x40000000`、范围 4 KiB；该地址不是新冻结合同。
- 最终日志 ERROR=0、CRITICAL WARNING=0；退出码为 0，且有完整检查通过标记。
- Vivado 仍提示可迁移为 inline HDL 常量/拼接模块，这是 INFO。本次沿用已存在配方的官方 IP 类型，没有额外更换架构。

原文见 `vivado-final.log`，结构化结果见 `result.json`。

## 本次发现和修正

1. 初始隔离夹具将输入放在待创建工程的 `.srcs` 下；`create_project` 先拒绝已存在目录，而 `-force` 会清理夹具自己的该目录。已改为将输入放在独立 `inputs` 下。用户工程没有进入此操作。
2. 沙箱账号无法正常加载 TclStore/xsim 包。最终使用经审核的普通账户环境验证隔离副本；未重置用户 TclStore。夹具曾增加当前进程的 Tcl 包搜索路径，此环境处理没有进入交付脚本。
3. Module Reference 的 `REF_NAME` 不是所需的原 RTL 模块名称；交付脚本改为核对模块 VLNV。
4. Processor System Reset 的 `C_EXT_RESET_HIGH` 在 BD 中为只读推导参数。交付脚本取消设置，连接 FCLK_RESET0_N 后检查工具推导为低有效；最终无此警告。

这些是准备脚本/检查环境问题，不能记作 RTL 功能失败，也没有以忽略报错的方式通过。

## 验证边界与文件保留

没有运行 RTL 功能仿真、新目标综合、实现、STA、ARM/PYNQ 或板测；本次结果不证明这些项目通过。实际用户工程还需要执行交付脚本。

正式 Tcl 在 `project/bd`，操作说明在 `document/manual-ps-bd-completion.md`。没有创建 `codex_out`。本轮隔离检查输出仍在 `simulation/work/ps-bd-completion`，用于用户第一次执行失败时对照；不作为第二套维护工程，不进入 Git。必要结果和失败原因已经归档，本轮未删除用户文件。
