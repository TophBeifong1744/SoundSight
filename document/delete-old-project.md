# 删除旧项目之前

新项目应独立保存在`E:/Users/Toph Beifong/Documents/GitHub/SoundSight`，与旧`Competition_fpga`为同级目录。不要把新目录移回旧仓库里面。

## 删除前看什么

1. 看migration-report.md的最终迁移检查结论，确认新路径的原生工程可打开、必要仿真/PC检查已有真实结果。
2. 从新路径打开你要使用的工程，核模块和BD；确认自己新增的DDR/MIO/PYNQ配置也已保存在新项目。不要只保存在即将删除的旧工程数据库。
3. 新源码和必要资料已有Git基线；`local_archive`、模型权重、原生工程输出属于本地保留内容，不随普通Git推送。需要这些原件长期保留时，应另有自己的备份。
4. 确认旧工程和旧目录没有正在写入的Vivado、编辑器或其他成员任务；退出旧项目后再由你操作删除。

## 路径界限

- **新项目，保留**：`E:/Users/Toph Beifong/Documents/GitHub/SoundSight`。
- **计划由你删除的旧仓库**：`E:/Users/Toph Beifong/Documents/GitHub/Competition_fpga`。
- **旧Vivado项目**：`F:/AMD/p/i17_live_loop`与旧仓库是不同目录。本任务不删除，也不把删除仓库等同于删除它。
- **工具安装，继续需要**：例如`F:/AMD/2025.2/Vivado`、Python、GCC、Keil、PYNQ镜像/SD卡。不要把工具链当旧工程一起清理。

本任务不会执行本地删除、GitHub仓库删除或创建新远端。你决定删除后再建立新的GitHub空仓库，并把SoundSight的main推送过去。

需要清掉哪些额外旧副本，必须按具体路径核对；“除了新目录之外全部删除”不能解释成删除GitHub父目录、F盘工具安装或其他课程/项目文件。
