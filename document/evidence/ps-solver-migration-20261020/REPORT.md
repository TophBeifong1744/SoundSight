# B 第二步：二维 S1 到 Python/C 桥的离线迁移自测

基线：SoundSight main `ade821b`。任务分支：`codex/ps-solver-selftest`。
本机为 Windows x86_64；这不是 ARM/PYNQ 实板结果。

## 完成内容

复用唯一的 S1 和生产桥，没有修改产品算法、公共协议、Python客户或FPGA。
新增一个测试用直接S1适配器和一个跨Windows/Linux的Python标准库测试入口。
同一语义输入分别：

1. 逐字段构造 `doa_frame_input_t`，直接调用S1；
2. 编成冻结的30字输入，通过现有 `ps_client.Solver` / ctypes / 生产桥调用S1。

逐项比较12个正式整数输出及返回码。固定期望来自既有双BIST及方向测试；
另外保存当前PC结果供ARM逐项复算。直接路径不复用生产桥的解包实现。
直接路径与桥接路径仍共享同一个求解器，因此这证明接合一致性，不是独立
数学证明；原S1的4705项固定/边界断言提供另外的已有数值验证。

## 实测

| 检查 | 结果 |
|---|---|
| 原S1完整测试 | 4705断言，0失败 |
| 既有桥接/客户检查 | 9项通过，使用已有AXI仿真导出双BIST夹具 |
| 直接S1与Python/C桥 | 157组全部一致 |
| 桥接非法输入 | 6组全部按预期拒绝 |
| 产品算法与STM32 V3对比 | `software/common/s1` 相对e6f1a2d无差异 |
| ARM Linux编译、运行、耗时 | 未测，待C目标环境 |

157组包括双BIST、±45°/±90°/-180°及非轴向、mask11/12/79/80、
S6边界及越界、S25边界及越界、有效对不足、帧取消、关闭映射、
六组精确RNE半整数输入，以及128组固定种子的合成输入。
6组桥接拒绝：零帧号、状态保留位、未锁帧、pair回显、FEATURE_0保留位、
负机械下限。负返回值后的out不是有效结果，不参与数值解释。

| 输入 | 固定预期 | 本机实测 |
|---|---|---|
| BIST_REJECT | ux46831，uy-171729，valid0/reason3 | 一致，servo_cmd_valid0 |
| BIST_ZERO | ux749295，uy0，angle_q8=0，valid1 | 一致，servo_cmd_valid0 |
| +45° / -45° | angle_q8=11520 / -11520 | 一致 |
| +90° / -90° | angle_q8=23040 / -23040 | 一致 |
| mask_count=11 / 有效对2 | valid0/reason1 | 一致 |

这些是标准/合成输入，不是实际声学精度测试；示例舵机参数不是实物标定。

## 复现与交接

PC在仓库根执行：

```sh
python software/tests/test_software.py
python software/tests/test_solver_migration.py
```

编译器沿用仓库工具发现规则；C99、O2、Wall/Wextra/Wconversion/Wshadow、
Werror/pedantic。测试临时产物位于software/build并自动清理。
`PC-RESULT.json`保留实际输入、全部正式输出和运行平台；`S1-OUTPUT.txt`
保留原测试数值。测试脚本可在目标ARM使用现有.so并与PC基准比较。

交给C的实际步骤见 `software/common/s1/PS-MIGRATION.md`。
阶段状态：B第二步PC自测完成；第三步目标ARM库/调用/耗时待验证。
本次不做硬件操作、独立验证派单、动作提交或main合并。
