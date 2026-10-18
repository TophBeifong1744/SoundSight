# STM32 主方案的 PS 裸机软件交接

本目录交接用户已经完成的 Vitis 平台与 application，不需要打开 Vivado。它为 FPGA+STM32 主方案提供 PS 侧启动基础，不是 `software/ps` 中的 PYNQ 定位业务程序。

## 发给别人哪些文件

整个本目录一起交接，共六个文件：

| 文件 | 用途 |
|---|---|
| `pl_stm32.xsa` | 已导出的硬件平台，内含 `pl_stm32.bit` 和 PS7 初始化资料 |
| `vitis_components.zip` | `pl_stm32_platform` 与 `first` 的组件交接包，含 BSP、平台导出、FSBL、现有 ELF、调试所用 bit 和 PS7 初始化文件 |
| `path-bases.json` | ZIP 外的相对路径清单，与解压工具放在一起，不放入目标工作区 |
| `unpack_local.py` | 只解压并填写接收方本机路径；不创建新工程、不编译、不运行工具 |
| `package-check.json` | 文件一致性、位流对应关系和相对路径检查结果 |
| `README.md` | 本说明 |

ZIP 约 7.75 MiB，包含 1554 个文件；大部分是平台自带的 BSP/驱动文件。没有把简单的 `main.c` 单独展开到仓库，它只在 application 包里维护。后续更新替换这一份包，不按日期堆积重复组件包。

ZIP 根目录只有以下两个组件，没有外层 `Vitis/`，也没有工作区级 `_ide/` 或 `.gitignore`。组件内部的 `_ide/` 调试资料仍保留。单独的 `pl_stm32.xsa` 不改动；组件自身依赖的 XSA 副本也保留在组件内。

```text
vitis_components.zip
├── first/                 application
└── pl_stm32_platform/     platform
```

## 当前内容到底做什么

- 工具版本：Vitis 2025.2；platform：`pl_stm32_platform`。
- application：`first`；处理器：`ps7_cortexa9_0`；系统：`standalone`。
- `main.c` 只打印一次 `PS application running.`，随后每秒休眠；它本身不做方向求解、SPI 控制或转台闭环。
- PS7 初始化由已有的 PS7 初始化文件/启动流程负责。包保留 `first/_ide/psinit/ps7_init.tcl`、FSBL 和已有调试配置，不把 main 中的打印当作 PS7 初始化代码。
- 现有 application ELF 为 `first/build/first.elf`；FSBL 为 `pl_stm32_platform/export/pl_stm32_platform/sw/boot/fsbl.elf`。
- 原调试配置会执行系统复位、下载位流和 ELF。这些动作由使用者操作，本次打包没有执行。

## 相对路径怎么处理

交付 ZIP 中的工程元数据已经去掉发送方的绝对路径。ZIP 外同目录的 `path-bases.json` 记录每条路径以“解压工作区”还是“接收方 Vitis 安装目录”为基准。

Vitis 2025.2 的部分生成 YAML 配置直接读取绝对路径，不能凭空假设它支持任意变量或相对路径。因此 `unpack_local.py` 只在接收方指定的新工作区中，把相对引用转换成本机可用的生成配置。仓库和原 ZIP 始终保留相对引用；不修改原工作区，不需要复制到发送方同样的盘符。

这不是工程重建脚本：不会调用 Vivado、Vitis、CMake、编译器或下载工具。它只解压已有组件并处理九个元数据文件、61 项路径。工具位置从命令行、本机 `VITIS_ROOT`/`XILINX_VITIS` 环境变量或 PATH 获取，不写入公共默认值。

## 接收方如何使用

1. 安装 Vitis 2025.2 和 Python 3，把这六个文件放在同一目录。
2. 选择一个**尚不存在**的新工作区目录，运行下列命令，把尖括号内容换成自己的实际目录：

```text
python unpack_local.py --workspace "<新的工作区目录>" --vitis-root "<本机Vitis安装目录>"
```

若本机已设置 `VITIS_ROOT`、`XILINX_VITIS` 或 PATH，可以省略 `--vitis-root`。目标工作区已经存在时会停止，不覆盖已有工程。

3. 打开 Vitis 2025.2，在欢迎页选择 **Set Workspace**，指定上一步生成的工作区目录，应查看到 `pl_stm32_platform` 和 `first`。本次没有启动 IDE 实测识别过程。
4. 核对平台硬件路径已指向工作区内的 `pl_stm32_platform/hw/pl_stm32.xsa`。需要重新编译时，由使用者在 Vitis 中操作；已有 `.elf`、`.bit`、FSBL 已保留。
5. 跨电脑的调试连接需要在本机重新选择。发送方的调试服务器身份、工作区锁和私有连接目录未带入；不要直接把旧 `Local` 连接当作接收方已经配置完成。

这里的 ZIP 是已整理的两个组件快照，**不是 Vitis GUI 的 File > Export 官方导出包**，不要把它直接交给 File > Import 当作已验证的官方格式。官方导入导出方式见 [AMD 2025.2 文档](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Project-Export-and-Import)；本包使用上述解压方式。

## 保留和排除了什么

保留两个组件的源码、链接脚本、CMake/BSP 配置、驱动源码、平台导出、硬件资料、现有 ARM ELF、BSP 库以及 application 调试所需文件。厂商源文件的原许可证/声明保持不变。

排除工作区级 `_ide/`、`.gitignore`、工作区锁、私有调试连接、IDE 日志、`.Xil`、`.rigel_lopper`、CMake/Ninja 缓存、编译对象、`compile_commands.json`、BSP `build_configs` 和可再生成的 linker map。保留原有 `.buildstatus` 作为已有构建记录，不执行带历史创建/删除命令的 workspace journal。

XSA、BIT、ELF、预编译 BSP 库及应用代码未改写。二进制中的调试信息可能仍含编译时历史路径，它们不作为当前工程定位依赖；不通过修改二进制字符串来假装重新构建。

## 本次核验结果与边界

- 用户原始 Vivado 导出 XSA、platform 内两份 XSA、这里单独提供的 XSA 内容一致。
- XSA 内 bit 与 platform、export、application 中的三份 bit 一致。
- application 和 FSBL 都是 ELF32、小端 ARM 文件；FSBL 构建与导出副本一致。
- 原有状态文件记录 platform `export=SUCCESS`（2026-10-18 20:00:34 CST）、application `hw=SUCCESS`（20:00:38 CST），不是本次重新执行的结果。
- 本次移除外层目录和工作区级文件，路径清单移到 ZIP 外；两个组件的全部文件与上一版相对路径包逐字节一致。
- 九个元数据文件只改路径；其余保留文件与原件逐字节一致，main 未改写。ZIP 完整性通过。
- 已在含空格与中文的新目录测试本地解压及路径填写，核对所有包内/工具依赖存在；已有工作区拒绝覆盖、不安全 ZIP 路径、旧外层目录及缺失组件拒绝写入的测试通过。临时验证目录已清理。
- 本次没有打开 Vitis/Vivado、重建/编译、下载、复位或做板测；不宣称已在另一台电脑启动成功，也不把此包等同完整系统功能通过。

FPGA 实现报告仍在 [project/reports/stm32](../../../project/reports/stm32/README.md)，Vivado 源码/BD 配方仍在 `project`。软件交接包在 `software/vitis` 独立归档，不与 Vivado 生成工程混放。
