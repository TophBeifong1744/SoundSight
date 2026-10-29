# 最新三维双轴源工程可搬移验证

日期：2026-10-29。主模式：BUILD_FLOW。未修改 RTL 行为、时钟、复位、CDC、寄存器、IRQ、DMA 地址或执行器语义。

## 成功候选

- Vivado 2025.2，SW Build 6299465，Windows；目标 xc7z020clg400-2。
- 从中文且含空格的解压目录执行交付 BAT，输出到独立英文且含空格的短目录。接收方工具位置通过进程环境提供；包中没有本机配置。
- 实际命令结构：`project\script\rebuild_ps_3d.bat --output "<new empty ASCII directory>"`。
- 真实退出码 0，`PS_3D_PREPARED` 已产生；BD Validate、两个 FFT 和所有 BD IP 的 HDL 输出、顶层 wrapper 生成完成。
- 注册文件全部位于新输出目录；31 RTL 加 Hann 初始化文件复制后与源字节一致。所有 run 均未运行；综合、实现、位流、下载、板测 **NOT RUN**。
- 两个 FFT 的全部 29 项用户参数值与最新实际工程 XCI 逐项一致。新 XCI 部分参数增加 `value_src=user` 元数据，不是参数值变化。
- 四份原 XDC 加垂直输出 20ns XDC；旧 SPI ILA XDC 仍 disabled。水平 T15，垂直 W16。旧 utils_1 增量 DCP 没有导入。

## 已知警告

- IP_Flow 19-5661 两条：module reference 的 clk/io_clk 无关联 bus interface。
- BD 41-702 一条：传播逻辑尝试把 DMA S2MM 用户设置 64 改成 32，被工具忽略，保留原配置。
- 成功候选无 ERROR 或 CRITICAL WARNING；上述普通警告未作为时序、带宽或整机通过证据。

## 离线检查

`python -B software/tests/test_vivado_portable.py -v`：3 tests，OK。

覆盖完整 31 RTL＋mem 依赖、50 文件源包无绝对路径、缺失依赖拒绝、故意注入绝对路径拒绝、无自动 run/硬件命令。打包 ZIP CRC PASS，根目录 `SoundSight_Vivado_PS_3D`，50 文件（包括原项目 LICENSE）另加 `FILES.txt`。

## 失败事实与修复

1. Vivado 在启动 cwd 创建 `.Xil`，最初撞到新空目录检查；启动 cwd 改到本机 `_launcher` 子目录。
2. 沙箱账户 TclStore 初始化失败，未改全局工具配置；同入口受控普通账户执行成功。
3. 过长输出路径触发 Windows 260 字节限制，最长 AXI protocol converter 文件生成失败。入口加入本配方保守的 78 字节输出路径上限。
4. 中文输出目录使官方 FFT Test Bench 生成器找不到刚生成的文件。明确拒绝非 ASCII 输出路径；中文源包路径仍经过实际验证。没有宣称支持厂商不支持的路径。
5. PV-01：本地 UTF-8 launcher 切到代码页 65001；PV-02：本次进程 PATH 内 canonical vivado.bat 必须解析到选定工具根。均进入成功候选。

原始成功/失败日志已归档到本目录的 `local/`，由 Git 忽略，不提交或加入公开交接 ZIP；本页只保留脱敏结论。本次可再生成的验证工程和解压副本已清理。当前包是源工程重建，不能用旧工程的时序报告替代接收方实际构建结果。
