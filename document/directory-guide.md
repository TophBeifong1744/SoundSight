# 新项目目录

所有维护内容集中在SoundSight总目录；两个FPGA目标共用源代码，分别保存原生工程输出。

```text
SoundSight/
  README.md, AGENTS.md, LICENSE
  project/
    rtl/                  唯一公共RTL、薄BD封装、Hann系数
    bd/                   stm32.tcl、ps.tcl连接配方
    ip/                   FFT/时钟配方；reference中是原官方配置与仿真模型
    sdc/stm32, ps/        两目标引脚与外部接口XDC
    script/               run.bat、setting.bat、src_list.txt、vivado.tcl
    par/SoundSight.xpr    STM32主方案原生入口；同级为其数据库和报告
  variants/pl_ps/
    project/par/SoundSight_PS.xpr  无STM32版原生入口，不复制公共RTL
  simulation/
    tb/stm32, ps/         原定向测试、输入向量、预期结果
    models/               独立整数参考生成脚本
    script/               run.bat、setting.txt、src_list.txt、vsim.do
    work/                 编译/展开/仿真数据库及本次结果
  software/
    common/               冻结ABI、共享头、原S1求解器及原测试
    stm32/                STM32板级交接和后续S2入口
    ps/                   AXI客户程序、PYNQ应用、C求解桥
    tests/                PC验证
    build/                软件测试/编译输出
  hardware/               板卡、麦克风、电气资料、照片、接线
  document/               当前说明、模块表、接口、验收与必要结果
    evidence/inherited/   迁移前的真实结果原文；不冒充本次执行
    evidence/migration/   新目录中实际重建/复现的记录
    history/              有用旧技术说明，日期和状态可能过时
  models/, data/          既有模型与夹具；旧模型单列适用范围
  research/               六麦、声纹、比赛Skills独立研究，不进入当前板顶
  tools/                  入口复用的Python/Tcl助手
  release/output/         后续正式可搬移交付包
  local_archive/          旧录音/报告/源码等本地参考ZIP，不参与构建、不进新Git
  codex_out/              当前任务临时诊断；任务结束整理，空闲时为空或不存在
```

## 对工作流目录的适配

采用已安装fpga-team-workflow 0.3.1、run-fpga-workflow本地0.5.0中的Git/目录原则。当前项目已有有效XSim验证，因此继续使用XSim；`vsim.do`存放它接受的Tcl仿真命令，不声称运行了ModelSim/Questa。

用户明确综合/实现自己点击，所以项目BAT默认是准备工程，不采用通用模板的自动compile默认动作。无STM32目标有自己的规范`project/par`，由同一个正式入口选择，不为两版复制一套公共源码。

当前没有配置独立HDL linter，不创建一个空壳“lint通过”。结构检查由`tools/check_project.py`明确报告自己的有限范围。

## 源码与历史的界限

- `project/rtl`是唯一需要日常修改的RTL。旧单域tile/clock参考文件仍在其中供原用例编译，正式两目标源清单明确排除。
- `project/ip/reference`是固定版本官方模型/配置参考，不能把其中旧生成目录直接注册进新工程；准备脚本在新par内正式重建IP。
- `document/design`和Word保留迁移时的设计说明，其中旧路径由新README和本目录表替代。完整当前源码链接集中在`document/modules/RTL-INTERFACES.html`。
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
