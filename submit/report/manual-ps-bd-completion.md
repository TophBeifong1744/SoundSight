# 手工 PS 工程：补齐 BD

本入口用于在 STM32 工程副本上继续搭建 PL+PS 版。两个 ARM 核运行同一个 Linux/PYNQ 系统，Python 调用 C 求解器；BD 只使用一个 PS7。

## 适用的起点

- 打开的工程名为 `SoundSight_PS`，器件为 `xc7z020clg400-2`。
- 已在 Sources 中换入 PS 版四份 RTL，并在 BD 添加 `bd_ps_link`，实例名为 `ps_link`。
- 原 `link` 单元和外部 SPI/IRQ 端口已移除。
- 原 `compute`、PS7、100/61.44 MHz 时钟、冷复位和麦克风连接保留。
- 可以保留复制过来的 `soundsight_stm32_bd` 名字；名称不决定它是否使用 STM32。

脚本对应上述已有 BD，不是新建工程脚本，也不是 `project/bd/ps.tcl` 的替代配方。不要在 STM32 原工程执行。

## 执行

在 Vivado 中打开工程副本及其 BD，确认没有正在运行的综合/实现。将以下路径替换为自己克隆的仓库位置，在 Tcl Console 执行：

```tcl
source {<SoundSight仓库>/project/bd/complete_manual_ps.tcl}
```

脚本完成：

1. 保存当前 BD，备份到工作工程的 `handoff/before_ps_bd_<时间>_<唯一编号>`。
2. 保留 PS7 的 DDR/MIO 等板级配置，启用 GP0、PL 中断和两个复位输出。
3. 补齐 `control_bus`、`control_cdc`、`bus_reset`、`bus_io_reset`、`irq_concat`、`irq_zero`。
4. 连接特征、握手、两域 AXI、复位、中断和 PWM；AXI 地址由 Vivado 分配。
5. 执行 Validate 并保存 BD。
6. 将仓库 PS 版两份 XDC 复制到工作工程的 `ps_constraints`，替换原同名约束的工程引用；旧文件仍保留在磁盘和备份中。
7. 重新生成 HDL Wrapper，更新顶层与编译顺序。

已有正确连线会复用。发现不同网络之间的冲突会停止，不会强行短接。若中途失败，不要忽略错误继续综合；保留 Console 的具体报错和备份。脚本不是事务回滚工具，失败前已经完成的步骤可能仍留在工作 BD 中。

## 完成标记与下一步

成功时输出：

```text
PS_BD_COMPLETE: ...; 19 cells; Validate completed.
PS_BD_NO_BUILD: no synthesis, implementation, bitstream or hardware action.
```

然后由用户在 GUI 执行 Generate Output Products，查看 Messages。综合、实现和下载仍由用户决定并操作。复制过来的旧实现报告不代表新 PS 目标通过。

时钟仍为计算/PS AXI 100 MHz、采集/快照/寄存器/PWM 61.44 MHz。`FCLK_RESET0_N` 只接普通总线复位；`FCLK_RESET1_N` 保留冷复位用途。`ps_link/rst_n` 与 `aresetn` 分开，普通总线复位不能顺手清掉已保存的帧。

`ACTUATOR_BOUND` 设置为 0；软件调用 C、PYNQ 镜像启动、真实采集及机械闭环不属于本脚本的验证范围。既有 IRQ 连线也不代表 Linux 中断驱动已经完成。

逐线说明见 [PS平台.txt](design/ps/ps-platform.txt)，本次核查记录见 [验证记录](../data/evidence/ps-bd-completion-20261020/readme.md)。
