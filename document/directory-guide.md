# 新项目目录

## 比赛推荐分类与命名

2026-10-29按用户提供的AMD指南§3.3.5.4，根目录已增加`src/sim/build/board/data/skill/report`七类阅读入口，完整映射见[根README](../README.md)。指南允许其他组织方式并要求映射；实际源码继续维护在`project/software`，仿真在`simulation`，原报告在`document`，分类入口不形成第二套源码或报告。

- 18个含中文、空格或非英文标点的归档文件名已改为小写英文；[旧新路径表](submission-path-map.json)登记原名、现名和原件校验值，文件内容不改。
- 历史日志、来源清单和ZIP内部原路径保持原文；查旧名时使用映射表。当前导航链接改用新路径。历史手册中的旧名也按映射查找，不改写已收件原件。
- 新普通目录/文件名采用小写英文、数字、下划线和连字符，扩展名用点分隔；`README.md`沿用官方示例。当前已有`AGENTS.md/SKILL.md/LICENSE`、历史结果文件和厂商文件仍保留大小写契约，不盲目更名以免破坏Linux引用或来源身份。因此本轮完成的是推荐分类映射和非ASCII/空格路径清理，并未声称整个开发仓库及嵌套历史包符合严格全小写提交检查；最终比赛导出须另核对这些保留项。独立比赛Skills包已有小写导出方式。
- PR #30的最新三维重建配方已合入，入口是`project/script/rebuild_ps_3d.bat`；详见[build](../build/README.md)。整理目录不运行EDA、固件或硬件，不新增实验编号/指标。

正式维护内容集中在SoundSight总目录；当前唯一主方案是Zynq-7020 PL+PS；STM32为已弃用历史路线，保留共用源码。当前用户在仓库外手工开发，验证后将源码与导出配置接回；下列par是仓库配方的重建输出位置，不限定外部工作目录。

```text
SoundSight/
  README.md, AGENTS.md, LICENSE
  tools.local.env.example  可提交的工具配置空模板
  tools.local.env          本机工具路径，被Git忽略
  project/
    rtl/                  唯一公共RTL、薄BD封装、Hann系数
    bd/                   PS基础/三维配方；stm32.tcl仅供历史参考
    ip/                   FFT/时钟配方；reference中是原官方配置与仿真模型
    sdc/stm32, ps/        当前PS约束；stm32为历史约束
    script/               run.bat、setting.bat、src_list.txt、vivado.tcl
    reports/stm32/       历史STM32实现报告（当前三维见reports/ps_3d）
    par/SoundSight.xpr    已弃用STM32原生入口；同级为其数据库和报告
  variants/pl_ps/
    project/par/SoundSight_PS.xpr  PS基础配方输出入口，不复制公共RTL
  simulation/
    tb/stm32, ps/         原定向测试、输入向量、预期结果
    models/               独立整数参考生成脚本
    script/               run.bat、src_list.txt、vsim.do
    work/                 编译/展开/仿真数据库及本次结果
  software/
    common/               冻结ABI、共享头、原S1求解器及原测试
    stm32/                已弃用STM32代码和历史板级交接
    ps/                   当前PS采集/控制、PYNQ应用与声纹程序
    vitis/stm32/          小型裸机XSA与platform/application交接包，不展开第二份main
    tetra3d/              当前三维C求解、筛选与双轴PS控制
    tests/                PC验证
    build/                软件测试/编译输出
  hardware/               板卡、麦克风、电气资料、照片、接线
  document/               当前说明、模块表、接口、验收与必要结果
    evidence/inherited/   迁移前的真实结果原文；不冒充本次执行
    evidence/migration/   新目录中实际重建/复现的记录
    history/              有用旧技术说明，日期和状态可能过时
  models/, data/          既有模型与夹具；旧模型单列适用范围
  research/               六麦与声纹研究/历史实验、比赛Skills；在线声纹代码在software/ps
  tools/                  入口复用的Python/Tcl助手
  release/output/         后续正式可搬移交付包
  local_archive/          旧录音/报告/源码等本地参考ZIP，不参与构建、不进新Git
  codex_out/              当前任务临时诊断；任务结束整理，空闲时为空或不存在
```

## 对工作流目录的适配

两个比赛Skills源码在research/competition-skills；统一复跑/打包入口在release，必要结果在document/evidence/competition-skills-20261018。用户授权的固定小型比赛包release/output/soundsight-competition-skills.zip随Git提交，其余release/output生成物继续忽略。更新同一入口，不堆日期副本；PYNQ实板仍为待办。

软件侧Vitis交接放在`software/vitis/stm32`，与`project`下Vivado源码、BD配方及实现报告分开。此处按用户授权提交固定入口的XSA和组件ZIP（vitis_components.zip，根目录仅两个组件，无Vitis外层），不把它们误放到被忽略的临时构建目录。ZIP内工程引用同样必须相对化；厂商需要的本机绝对路径仅在解压后的本地副本生成。原始二进制和必要构建状态保留，缓存/私有连接排除。详见该目录README和AGENTS的Vitis约定。

采用已安装fpga-team-workflow 0.3.1、run-fpga-workflow本地0.5.0中的Git/目录原则。当前项目已有有效XSim验证，因此继续使用XSim；`vsim.do`存放它接受的Tcl仿真命令，不声称运行了ModelSim/Questa。

用户明确综合/实现自己点击，所以项目BAT默认是准备工程，不采用通用模板的自动compile默认动作。当前PS目标沿用已有规范`project/par`，由同一个正式入口选择，不为两版复制一套公共源码。

当前没有配置独立HDL linter，不创建一个空壳“lint通过”。结构检查由`tools/check_project.py`明确报告自己的有限范围。

## 源码与历史的界限

- `project/rtl`是唯一正式维护的RTL；外部工程允许有本批工作副本，验证后对比接回。旧单域tile/clock参考文件仍在其中供原用例编译，正式两目标源清单明确排除。
- `project/ip/reference`是固定版本官方模型/配置参考，保留生成时的器件元数据，不手改厂商输出。当前目标统一为`xc7z020clg400-2`；不能把参考中的旧生成目录直接注册进新工程，准备脚本在新par内按当前目标正式重建IP。参考模型用于仿真不构成当前目标的IP生成或时序证据。
- `document/design`和Word使用当前SoundSight路径与操作入口；旧基础连接只供版本参考，STM32已弃用：`document/design/stm32/bd-connections.txt`和`document/design/ps/ps-platform.txt`。完整当前源码链接集中在`document/modules/RTL-INTERFACES.html`。历史原始日志仍保留原路径，不作为新操作入口。
- `software/common`只维护一份冻结合同与S1。两版同时引用，避免两边各自改出不同协议。
- `local_archive`保留历史原件，旧脚本不作为新运行入口。旧Git提交图没有搬入新Git。

## 临时目录如何收尾

`codex_out`是工作台，不是交付目录。`.gitignore`只控制是否上传，不能代替清理。

1. 核对每个临时目录是否仍有运行任务、独立修改或尚未归档成果，不按日期或文件大小直接删除。
2. 正式代码放回project/software等对应目录；可复用助手放tools；说明放document；有用途的测试结果和失败原件放document/evidence。保留复现输入、命令、实际结果及必要日志，避免复制整套源码和运行数据库。
3. 修正当前说明的文件链接；历史日志原路径不改写，另写一句归档位置及来源说明。
4. 确认归档文件与原件一致后，删除已完成用途的本任务临时副本、重复ZIP、可再生成的二进制。未归档或他人修改先保留；仍需留存时简记用途、负责人和清理条件。
5. 交付时报告清理范围和剩余内容。没有进行中的任务时，codex_out为空或不存在，不留每轮完整工程副本。

本规则不授权清空其他任务目录、正式源、历史档案或整个par/work/build；这些输出按实际复现、排障和交付用途另行整理。local_archive也不是临时垃圾的兜底目录。
