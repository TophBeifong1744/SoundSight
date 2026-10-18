# 两个 Skills 迁移验证原件

- before-migration-unit.log / before-migration.json：迁移前真实缺 PCM 源文件失败，原命令和退出码保留。
- source-run/：当前仓库中的离线与六次 XSim 原件。每次仿真保存编译/展开/运行日志、输入快照和 result.json；三种故意错误应 FAIL，其余 PASS。work 仿真数据库未归档。
- export-run/：初次从 ZIP 解压到中文和空格目录后的复跑原件，范围同上；其 entry-archive.json 标明初版包。最终包只规范两份许可证行尾及来源清单，未改变代码/激励。
- final-export-run/：最终准确 ZIP 再次独立解压后的完整复跑原件；package-check.json 以本次结果为最终依据。
- package-check.json：准确 ZIP、来源对应、解压验证及范围；包内源码未因验证而改变。
- history/：2026-09-14 B 限定复核与 S1 修复交接原文。旧链接、日期和绝对路径保持原文，不作为新命令或当前状态。
- cleanup.json：本次新建仿真缓存和解压副本的清理范围；清理前逐字节确认所有必要原件已归档，未触碰用户外部工程。

历史 B 批准只覆盖 a7e1ea9 / 3ac597d 的限定范围。本次没有代 B/C 签字。模拟通过不等于 PYNQ 实板、整机、资源/时序或官方比赛验收。

日志中的绝对路径是实际执行环境记录；当前可搬移命令见 document/competition-skills-delivery.md 或交付 ZIP 根 readme.md。代码与仿真输入保留原字节，不为消除历史路径改写日志。
