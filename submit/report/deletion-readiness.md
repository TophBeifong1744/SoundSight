# 删除旧目录前的复核 — 2026-10-17

结论：就当前迁移工程的继续开发、重新建工程和既有测试复现而言，可以弃用并由用户删除 `E:/Users/Toph Beifong/Documents/GitHub/Competition_fpga` 与 `F:/AMD/p/i17_live_loop`。本次没有执行删除，没有启动Vivado或任何综合、实现、下载。

## 本次重新检查的结果

- 新项目静态结构检查通过；STM32源清单26项、PS源清单26项、仿真清单33项均可解析。
- 806条迁移映射目标全部存在，映射的旧输入在迁移后没有修改；两份最新产品目录检查范围内没有遗漏源码、约束、测试数据或模块说明文件。
- 直接解析当前两份XPR，每份32个注册文件均存在，解析路径都位于SoundSight内。
- 扫描454个工程/代码/配置文本，没有发现活动入口对旧仓库或旧F盘工程的依赖，也未发现检查范围内的符号链接/目录联接。
- 参考XCI仍保留旧gen_directory/OUTPUTDIR原文字段，但不注册到新工程；新工程由project/ip/create_fft_ip.tcl在自身par下生成IP。另有检查脚本中的旧路径禁用词。这些不构成读取旧目录的依赖。
- legacy-technical.zip的11,418项重新完成CRC检查，并逐项与旧目录当前文件比较，全部一致。migration-input-originals.zip的79项CRC检查通过。
- 为覆盖用户新提出的弃用F盘工程范围，补存398份旧F盘工程源文件、XPR/BD/XCI/约束、相关配置和报告到local_archive/f-project-originals-20261017.zip；CRC与原文件逐字节比较均通过。旧XPR注册的非数据库文件没有缺件。

原件：[复核结果](../data/evidence/migration/deletion-readiness/result.json)、[F盘原件归档结果](../data/evidence/migration/deletion-readiness/f-project-result.json)。同目录的两个 .py.txt 文件保留当时检查和一次性归档的原始步骤，仅供审阅；它们使用当时临时目录布局，不是可执行的工程入口。

## 结论边界

这不是旧仓库/旧Vivado工程每一个历史对象的完整镜像。旧Git提交图、EDA运行数据库、大波形等未整体搬迁；F盘档案不保证能直接恢复全部旧run。保存它是为了查原始源码和报告，不让新项目继续依赖旧结构。

本次未重跑RTL仿真：产品代码没有修改，复用同日新目录内已经执行的定向仿真及Git纯文件导出PC测试。综合、实现、真实PS7/DDR配置、STM32 S2和上板仍是后续工程事项，不属于迁移遗漏。

## 新建工程从哪里取材料

- 源码：project/rtl；源清单：project/script/src_list.txt、document/build/ps-src-list.txt。
- BD配方：project/bd；IP配方：project/ip/*.tcl；约束：project/sdc。
- 模块与连线说明：document/modules/RTL-INTERFACES.html、document/design；操作入口：document/run-guide.md。
- 本地已经准备了project/par/SoundSight.xpr和variants/pl_ps/project/par/SoundSight_PS.xpr。脚本不会覆盖已有工程；用户若决定在Vivado重新手工建立，继续使用这一份共享源码，不从旧F盘工程Import。
- 工具安装F:/AMD/2025.2/Vivado、Python、GCC、Keil等仍需保留，与待弃用的F:/AMD/p/i17_live_loop不同。

删除前关闭旧项目及使用旧目录的编辑/终端窗口；保留整个SoundSight目录。local_archive不会进入普通Git推送，后续上传源码并不等于备份了这些本地原件。
