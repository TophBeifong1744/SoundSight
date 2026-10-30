# 从当前Vivado工程导出可搬移的复现资料

正式脚本：`project/script/export_portable_handoff.tcl`。同一脚本可以复制到个人方便的位置，作为本机通用导出入口；脚本自身不含个人目录或工具安装路径。

## 怎样导出

1. 打开本次实际生成位流的工程，等所有运行结束。
2. 在Vivado Tcl Console中 `source` 这个脚本。
3. 成功时出现 `EXPORT_COMPLETE`、`PORTABLE_PATHS_CHECKED=1` 和 `SOURCE_DEPENDENCIES_COPIED=1`。
4. 交接**当前工程目录下整个 `handoff/latest` 文件夹**。不要只交Tcl。

导出不启动综合、实现、下载或转台动作。BD会保存当前配置以便导出一致；不会改RTL、约束、PS参数或重新连接BD。原latest若存在，会保留为同级`previous_*`；失败留下`.pending_*`供诊断，旧latest不被替换。

## 导出的内容

| 位置 | 内容 |
|---|---|
| `project.tcl` | 完整工程重建入口，按脚本自身位置寻找资料，与启动时的工作目录无关 |
| `recipe.tcl` | Vivado生成的工程、文件属性、运行策略等配置；不启动运行 |
| `payload/` | 实际登记RTL、XDC、初始化数据、BD、顶层XCI及必要头文件/HDL包装文件，保留相对层级 |
| `bd/*.tcl` | 单独的BD、PS与内部IP配方，供阅读/维护；无需在完整重建后再重复执行 |
| `source_files.txt` | 相对于交接文件夹的源码清单，没有本机盘符 |
| `PORTABILITY.txt` | 路径扫描和文件收齐结果，明确实际重建未执行 |

完整重建时，在同版本Vivado的空会话中source `project.tcl`。默认在交接目录下创建`recreated_project`；若已存在则停止，避免覆盖。建议接收者先把整个交接包复制到自己的工作目录再执行。Windows应使用Vivado/IP支持的短英文工程输出目录。

本次导出**不包含bit/HWH/XSA**，这些是同候选部署产物，需要另行交接。也不携带DCP缓存、运行数据库和完整厂商生成文件。导出成功不等于重建、STA或板测通过；本次没有增加“用户必须再完整重建一次才能交接”的流程。

## 如何避免旧路径问题

旧脚本的`-paths_relative_to`只改变一部分引用，不会收齐源码；BD模块引用的后备导入语句仍可能写入绝对路径。新版使用BD源文件的完整工程配方，同时把独立BD脚本中的模块导入改成根据交接目录构造的Tcl路径列表，支持空格。

新版复制实际依赖后扫描源码、BD/XCI和导出配方；发现未处理的本机路径就停止，不简单把路径删空。目录外引用要求先用Vivado的“Copy File into Project”收进当前工程；自定义IP仓库、作为源输入的DCP/EDIF/XCIX等需单独处理，不能假称通用脚本已打包它们。头文件字面量include会收集，找不到时停止。动态生成或宏拼接的任意文件依赖仍需要工程作者显式登记，不能靠扫描推断。

命令依据：[AMD write_project_tcl说明](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_project_tcl)，使用`-no_copy_sources -use_bd_files`保持BD源输入，；不使用本机不支持的`-ignore_utils`。导出后仅移除已识别的utils_1缓存段和对应依赖，并关闭导出配方对旧增量检查点的引用；原工程属性不修改，格式无法识别时停止。

## 本次验证

2026-10-30：11项Tcl离线测试通过（包含真实归档工程Tcl的utils缓存剔除检查），覆盖中文/空格路径、搬移后定位、原目录删除后的输入解析、完整备份、绝对路径/缺件拒绝、外部源/自定义IP拒绝、头文件收集和额外wrapper依赖。另用仓库归档的真实W16 BD导出转换验证：Tcl语法完整、无本机路径，207条原登记路径用于核对模块引用。

复现命令：`python software/tests/test_portable_export.py -v`。没有打开用户工程或运行实际Vivado导出/重建；用户下一次导出的文件仍需读取确认。先前W16归档保持原文，不篡改历史证据。

### 兼容性返修记录

用户实际导出报`Common 17-170 Unknown option -ignore_utils`。上一版离线命令模型错误地允许该参数，现已改为明确拒绝并补真实归档配方测试。沙箱中另行启动的无工程Vivado帮助查询遇到Tcl Store目录损坏提示，命令未注册，未获得有效帮助；没有重置用户Tcl Store或将该查询算作验证通过。实际新导出仍待用户重试。

2026-10-30再次修正：BD JSON中的`ip\\模块\\模块.xci`是相对路径，旧扫描误判为UNC。现要求UNC出现在路径起始位置，真正的盘符/UNC仍拦截。11项回归通过，并读取用户本轮pending配方，对其40份实际BD/XCI/RTL/XDC/MEM等输入及导出Tcl逐项扫描通过；未改原件、未启动重建。
