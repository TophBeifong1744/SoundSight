# 正四面体三维算法：Linux源码适配与PC验证

2026-10-21，基于main `76bcc15`。本批完成纯算法迁入、独立共享库桥接、Python3.8+调用和离线回放；尚未连接目标PYNQ，不宣称ARM二进制或板端测试已完成。

## 改了什么

- `software/tetra3d/core`：从旧STM32工作树HEAD `2e83d4b` 迁入8份原C/H，内容逐字节一致。包括三维解算、几何、编译选择、双轴数学映射；旧工作树及用户Keil修改保留。
- `software/tetra3d/linux/ss_solver_3d_bridge.c/h`：独立平坦数组ctypes接口，解包相同六对字，几何预检、逐对诊断及独立az/el有效性。原2D桥接、公共冻结ABI和RTL未改。
- `software/tetra3d/linux/solver_3d.py`、`build_solver_3d.sh`：显式几何配置、版本检查、范围校验、JSONL回放及Linux构建入口。没有MMIO、快照消费、清错或动作提交。Python输出servo_cmd_valid固定0。
- `software/tetra3d/tests`：复用两份原C测试，新增直接语义输入oracle及迁移测试。新增库输出加入gitignore；未打包Windows二进制冒充ARM库。

本批保留原三维算法的double LS/atan2与RNE规则，无阈值更改。仅远场方向，不计算声源距离。几何默认40mm标称四面体，未标为实测。双轴C软件映射保留并编译，但Python方向接口及现有硬件动作合同未接通双轴。

## 实际验证

平台Windows AMD64，MinGW GCC8.1.0，严格C99/O2/Wall/Wextra/Wconversion/Wshadow/Werror/pedantic，编译无警告。最终原文、完整输入输出及平台信息：[PC-RESULT.json](PC-RESULT.json)。结果中的golden_checked=true表示再次加载按生产源集合编译的已有PC库，成功对照前一次PC基准；不是ARM测试。

| 检查 | 实测 |
|---|---|
| 原二维选择/三维选择回归 | 2110 / 2378项，0失败 |
| 原双轴软件映射 | 92270项，0失败 |
| 三维直接C与实际Python/共享库对照 | 154组通过，含独立解析前向模型、双旧BIST拒绝、极点、源错误与64bit margin |
| 桥接/输入拒绝 | 17组通过 |
| 几何/来源/通道配置 | 15组通过，含共面/病态/超窗口/重复通道/误差上界与合法重排 |
| 实际JSONL CLI | 4类通过：正常及算法拒绝记录、阻止覆盖、API错保存后停止、空输入拒绝 |
| 原二维独立回归 | 原S1 4705项、157组接口数值对照、6组非法输入通过 |
| 原算法与测试复用核对 | 8份三维C/H、2份原测试与旧源逐字节一致；原二维算法一致 |

测试覆盖原整数插值/RNE、逐对margin64；例如peak=1/second=-16777216产生margin=549755846656，Python接收不截断为32位。参考函数直接赋语义结构体绕过FEATURE解码，用于定位桥接问题；独立物理前向模型和原C测试用于检查算法方向，二者用途不同。

| 合成输入方位/俯仰 | 输出方位/俯仰（度） | 有效性 |
|---|---|---|
| +45 / +30 | +45.000854 / +29.999487 | 两角有效 |
| -45 / -30 | -45.000050 / -29.999580 | 两角有效 |
| 0 / +90 | 方位不采用 / +90附近 | 方向与俯仰有效，方位无效 |
| 0 / -90 | 方位不采用 / -90附近 | 方向与俯仰有效，方位无效 |
| mask_count=11 | 不输出有效方向 | reason=1 |

以上是合成特征的数值结果，不是实录定位精度。末轮200次PC调用最小10.7μs、中位11.0μs、最大40.5μs，含Python/ctypes/几何预检/解算；不是Cortex-A9耗时，不是实时上界。

## 重现与未测

主机测试：`python software/tetra3d/tests/test_solver_3d_migration.py --cc gcc`。已有库/跨平台基准及回放命令见[交接入口](../../../software/tetra3d/PS-MIGRATION.md)。本机二维测试使用既有SS_GCC配置，命令为 `python software/tests/test_solver_migration.py`。

一次二维测试误加不支持的 `--cc` 参数，由argparse拒绝，按既有SS_GCC配置重跑通过，未改产品。一次检出因缺省网络无法获取部分克隆对象失败，经既有代理完成；代码状态核对无遗留。没有发现测试引起的算法失败。当前无可用WSL/Linux编译环境，未安装新环境或更改授权；Linux脚本只准备源和构建命令，目标编译/运行待PYNQ。

尚缺：目标ARM .so与实际Python调用/耗时、A确认真实通道/lag符号/窗口、实物四面体坐标及同步录音与独立参考角、C三维结果接入、双轴设备接口和机械闭环。当前任务无需改动二维系统或等待实物即可完成算法源码交接，但不能标记三维整机完成。

没有创建codex_out或新工程副本。编译可执行文件/测试DLL在TemporaryDirectory中用后清理；必要报告归本目录，既定software/build中保留本次测试JSON。无FPGA构建、下载、复位或硬件动作。

## 按用户要求集中隔离目录

后续确认要求不影响正在推进的二维。三维核心、Linux入口、测试全部集中在 `software/tetra3d/{core,linux,tests}`，文档入口同目录。二维 `software/common`、`software/ps`、`software/tests` 和 `tools` 相对基线76bcc15无差异；当前package_pynq.py不选择software/tetra3d，因此二维打包集合保持原样。公共类型及映射函数仅作为只读编译依赖。

目录迁移后重新运行三维原回归2110/2378/92270，154组跨接口及原PC基准对照、17组非法输入、15组几何及4类CLI检查全部通过；二维原S1 4705/接口157/非法6通过。Linux脚本bash -n通过。PC-RESULT.json保留首次生产源集合验证基准；迁移后结果与其对照通过，隔离重跑结果在既定software/build/tetra3d-migration/ISOLATED-RESULT.json。未修改算法数值或实际二维入口。
