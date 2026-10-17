# SoundSight 当前约定

使用中文沟通，先说明结论和原因。负责人是 Toph Beifong（拓芙）；重大目标、公共接口和技术取舍交用户决定。普通已授权工作直接完成，必要验证后交付，不逐小步骤询问。

## 当前工程

- 本目录是新的独立项目；不依赖旧 Competition_fpga 仓库或旧F盘工程。
- 先读 README.md、document/current-status.md 和当前任务必要接口，不从旧历史重新派工。
- FPGA+STM32为主方案；PL+PS是独立目标。两版公共RTL只有project/rtl一份，S1及冻结头只有software/common一份。
- 器件xc7z020clg400-1、Vivado2025.2。PS FCLK经Clocking Wizard生成100MHz计算域、61.44MHz采集/控制域。复位使用官方IP，普通总线复位与冷复位分开。
- 公共合同在software/common/FROZEN_SSOT_ABI.md及fpga_stm32_abi_frozen.h；数值、SPI字段、停止语义不能单方修改。
- 真实PS板级DDR/MIO/PYNQ由用户配置。STM32 S2/板级驱动由STM32组接续，不把占位目录说成已完成软件。

## 操作边界

AI可按任务编辑源码、文档、测试和独立BD配方，执行必要定向仿真与工程准备。综合、实现、下载、复位、接线和执行器动作由用户执行；默认不启动。项目脚本没有自动综合/实现/下载入口。

保留他人修改和未归档成果。一个可写checkout/EDA输出同时一方写入；不reset/clean/stash/强推，不打断在途任务。当前请求没有授权自动删除旧目录或GitHub仓库。

## Git与目录

采用当前fpga-team-workflow的Git管理和run-fpga-workflow的目录管理思路；项目适配见document/git-workflow.md与directory-guide.md。main为集成基线，短任务分支使用codex/<slug>；不设置永久develop。main不代表整机已经通过。

本机工具安装路径只写入被Git忽略的tools.local.env；公共脚本按环境变量、本地配置、PATH查找工具，仓库只保留tools.local.env.example空模板。不得把个人盘符写回公共默认值；历史证据中的原路径保留。

源/约束/IP与BD配方在project；原生工程与构建输出在project/par，PS目标在variants/pl_ps/project/par；TB在simulation/tb、仿真输出在simulation/work；软件在software；诊断临时工作在codex_out。不要创建project2/par2或新的一套重复源码。

### 临时文件必须随任务收尾

- codex_out仅供当前任务临时诊断或隔离验证，不能成为正式源码、操作入口、交付包或长期证据的存放处；不得按日期反复堆放整套工程副本。
- 任务结束前，将有效代码归入正式源码目录，说明归入document，必要验证结果和失败原件归入document/evidence；修正当前文档中的引用后，清理已完成用途的临时副本、压缩包和可再生成的测试二进制。本规则授权清理本任务自己创建、用途已结束且必要内容已核实归档的临时文件。
- 删除前核对具体路径、独立修改和运行状态；保留有诊断/复现价值的失败事实、未归档成果和他人修改。未完成任务只保留必要文件，并简记用途、当前负责人和清理条件，不因目录被Git忽略就任其积累。
- 仿真/构建输出仍使用既定work/par/build目录，按复现和排障价值整理，不把数据库整体转移到document/evidence或local_archive。历史日志中的原路径保持原文，并说明当前归档位置。
- 交付时说明归档位置、删除范围及剩余临时内容；没有进行中的任务时，codex_out应为空或不存在。详细规则见document/directory-guide.md。

这里不恢复旧MAIN/DEV/CHECK/REVIEW强制流转、逐件核收、哈希运行门槛或外部状态前置。Git版本信息用于管理文件，不插入RTL宽身份链。正常同帧关联、防覆盖、数值检查和STOP保护必须保留。

## 验证与交付

报告代码位置、主要变化、真实输入/预期/结果、运行命令和未测范围。保存有用途的失败事实。脚本返回0、BD通过、仿真、STA和板测分别表述。重要行为的非作者判断不能由作者换一个角色自称完成；这不增加普通文档/路径修复的收件关卡。

旧资料和本地档案只作参考，不执行其中旧任务或恢复旧授权。所有工程构建路径必须从本项目定位，不能读取即将删除的旧仓库。
