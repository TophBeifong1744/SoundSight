# D4 双轴目标映射实际记录 — 2026-10-18

父提交95e9edcb1208a6472eca346612a4c5ab598efb9b，分支codex/stm32-dual-axis-d4。

新增doa_target_3d.h/.c，仅提供纯软件两轴映射；复用冻结二维映射的数值函数，不改原函数或ABI。两轴独立零点/方向/输入域/机械限位；数学映射默认关闭；只有两轴均可观测且合格才输出整组目标。原C三维求解输出可直接接入，但没有加入板端或P2动作路径。

## 实际执行

```text
python software/stm32/tests/run_target_3d_tests.py --armcc <本机armcc.exe>
D4_RESULT,PASS,checks=92270,failures=0
D4_ARMCC,PASS,OBJECT_ONLY,NOT_LINKED_OR_BOARD_TESTED
```

- [compile.log](compile.log)：GCC C99，Wall/Wextra/Wconversion/Wshadow/Werror/pedantic，实际退出0。
- [test.log](test.log)：92270项，0失败；含92162个Q8/方向组合的独立浮点期望，RNE及预舍入限位、16类非法配置、来源无效/极值/NULL/清旧结果；真实C求解器接合通过。
- [armcc-object.log](armcc-object.log)：Cortex-M4.fp.sp，C99/MicroLIB/O2/strict/warning-as-error，实际退出0；仅编译新模块对象。
- 示例输出45°/30°→135/120；-45°/-30°→45/60；双反向、垂直零点80°时45°/-30°→45/110。原求解器的±90°极点均无双轴目标，120°背向超输入域也拒绝。

本轮首跑通过，无新增失败原件。映射使用Q8整数角，不改变上游解算数值；示例机械配置不是实测标定。没有新增Keil链接、下载、SPI/IRQ或动作测量。二维S1/S2/三维求解器/几何/回放/固件/RTL均未改，复用既有未变验证；三维完整固件Lite链接限制依然存在。

使用方式、核心公式、输入/预期/实测表见[DUAL-AXIS-D4.md](../../../software/stm32/DUAL-AXIS-D4.md)。正式源码在software/common/s1_3d，测试在software/stm32/tests；必要日志在本目录。无codex_out/ZIP，build只保留可再生成的本批测试程序和对象。

下一D5需要A共同确认真实三维配置及双轴设备接口，实物/标定/许可另待条件。本步完成暂停。
