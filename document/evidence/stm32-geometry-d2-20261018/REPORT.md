# D2 几何配置与校验实际记录 — 2026-10-18

父提交 edb283ffd23e7bbeb5119777c11a5b5dd4ce1a82，任务分支 codex/stm32-geometry-d2。本批仅 STM32 本地三维配置、应用接合、测试和说明；未改 FPGA、冻结 ABI、二维求解器或时钟/动作门禁。

## 改动

新增 doa_geometry.h/.c：配置来源/版本、显式物理位置到线通道映射、全六对预检及测量误差窗口上界；ss_app 提供冷配置与本会话不可解锁限制。JSON 入口生成静态头前执行同一 C 校验器，应用初始化再次检查。三维 Keil 目标增加该源；二维目标源列表不变。

使用说明和输入/预期/结果表见 [GEOMETRY-D2.md](../../../software/stm32/GEOMETRY-D2.md)。

## 实际结果

- [geometry.log](geometry.log)：829 项，0 失败；8 组合成方向、配置负例、原子安装、无总线副作用和恢复不能换配置。
- import-*.log：18 个场景通过，包含正常/实测声明/特殊字符、坏 JSON、超窗、未知字段、禁止覆盖等。拒绝场景 EXIT_CODE=1 是预期结果。
- [selected.log](selected.log)：生成头路径实际 app_init，revision=1、valid=1。
- armcc-doa_geometry.log / armcc-ss_app.log：AC5 C99 strict warning-as-error 对象编译 exit0，含生成头选择路径；不是三维固件链接。
- [run_spatial_app_tests.log](run_spatial_app_tests.log)：D1 8072/0、160 个通信故障组合、四个三维主机流程模型通过，动作开启编译按预期拒绝。
- [run_app_tests.log](run_app_tests.log)：二维 P3 默认3070/模型开启3283，0失败。
- [run_host_tests.log](run_host_tests.log)：二维S1 4705/S2 15980，五主机自检/命令场景通过。
- [keil-planar.log](keil-planar.log)：二维Template完整重建0错误0警告，AXF/HEX生成，Code29326/RO1994/RW48/ZI10080；UV4进程返回0。未下载。

首次 compile-geometry-first-failure.log 是新测试复用 D1 测试文件时 main 宏重定义；修正测试入口选择宏，产品算法没有因该错误修改。最终 compile-geometry.log 通过，原错保留。

所有输出来自 PC/模型或工具编译。没有四面体实物测量、真实 SPI/声学或动作验证；MEASURED 测试值为测试夹具中的声明，不是新增实测成果。D1 的 MDK Lite L6047U 阻断保留，本批未反复尝试完整三维链接；D2映像大小未知。

源码、JSON和测试位于software正式目录；必要日志在本目录。临时导入夹具/可执行文件由TemporaryDirectory清理；没有新建codex_out或ZIP。software/stm32/build保留本批可再生成对象、测试程序和构建产物，不进入Git。

下一任务 D3；本批交付后暂停。
