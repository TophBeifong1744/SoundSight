# 2026-10-19 STM32 无ILA工程接回

## 目标与输入

用户授权更新GitHub原工程入口，并将外部工作副本的有效修改维护到唯一公共`project/rtl`。正式工程不含ILA，不上传Vivado工作数据库，不新增一套长期产品源码。

输入为`F:/AMD/work/SoundSight_STM32/handoff/latest`、当前`.srcs`中的RTL/XDC、用户已有`impl_1`报告，以及此前保存的首次故障ILA与UART。代码基线为`b486b567db3cb20f1c56f98c89a7f081e265dc9b`。外部工程未被本批改写；本批未执行综合、实现、下载或硬件动作。

## 修改与配置比对

- 唯一实质RTL差异为`ss_spi_mode0.sv`在合法提交条件中增加`!fall`，并保留用户注释。`ss_pair_engine.sv`仅行尾空格不同，没有接入无效空白改动。
- 28份输入包括25份RTL、Hann数据和2份XDC，忽略行尾空格/换行后匹配。逐文件摘要在[static-result.json](static-result.json)。这些摘要只标识文件，不证明物理构建或板上加载身份。
- 最新BD的63项功能事件与正式配方一致；最新导出未含GUI布局命令，因此比较时只排除布局，继续保留仓库已有布局。
- 两份FFT XCI与[10月18日原件](../stm32-handoff-20261018/original/)相同，每个27项显式参数匹配；不重复保存XCI副本。
- 77项运行属性匹配现有配方；40项正式重建依赖存在，未发现个人工作区/工具路径依赖或ILA配置。系统命令解释器的`C:/Windows/System32/cmd.exe`兜底不视为个人路径。
- 最新原始`project.tcl`包含禁用的ILA XDC。正式入口不登记该XDC、ILA核或调试hub；原始导出仅作为历史证据，不作为运行入口。

[original/project.tcl](original/project.tcl)和[original/soundsight_stm32_bd.tcl](original/soundsight_stm32_bd.tcl)保留导出原文。复现工程使用`project/script/run.bat`，不要直接运行本目录原始导出。

## 验证命令与实际结果

在仓库根目录：

```powershell
python -X utf8 document/evidence/stm32-handoff-20261019/check_export.py
python -X utf8 tools/check_project.py
```

归档检查只使用仓库材料。另一次检查使用用户当前副本：

```powershell
python -X utf8 document/evidence/stm32-handoff-20261019/check_export.py --export-dir F:/AMD/work/SoundSight_STM32/handoff/latest --live-project F:/AMD/work/SoundSight_STM32 --output document/evidence/stm32-handoff-20261019/static-result.json
```

结果为静态配置、依赖和源码比较PASS；结构检查单列[project-check.json](project-check.json)。Tcl命令由记录器执行，不调用Vivado，所以不能证明IP参数合法性、BD传播、RTL功能或时序闭合。

检查器首次执行把系统`cmd.exe`兜底误判为个人路径而停止；仅修正此检查器分类后重跑通过。这是辅助检查器问题，不是产品故障。

本批属于既有板上修正接回，RTL仿真SKIPPED；不生成或声称新的compile/elaborate/run日志。新仓库配方重建、板测、Flash回读均NOT_RUN。现有SPI TB没有直接覆盖CS释放与SCK下降同拍，此边界由源码条件及独立只读复核说明，不能称已仿真覆盖。

[独立非作者复核](independent-review.md)结论为PASS WITH CONDITIONS：允许无ILA工程源码接回，保持板级故障未解决及各项未测边界，不作为整机验收。

## 用户最新实现报告

正式报告在[project/reports/stm32](../../../project/reports/stm32/README.md)：用户22:56:34布线后报告WNS +0.379 ns、WHS +0.036 ns；22:55:05 Fully Placed资源LUT 13895、FF 14458、BRAM 25、DSP 41。附路由后DRC，保留所有警告及规则截断。不是本批重新执行，也不证明实际Flash已更新。

[artifact-identities.json](artifact-identities.json)记录外部bit和报告文件摘要，bit未作为源码重建依赖提交。没有同候选的新专项CDC报告；旧Vitis/XSA/BOOT包未更新。

## 未解决的板级故障：不同的ILA诊断候选

此前带ILA的诊断记录在[first_spi_fault.ila](first_spi_fault.ila)，包含原始waveform.csv，不再重复提交单独CSV；[UART](first_spi_fault_uart.txt)来自用户在聊天提供的本次完整FPGA诊断输出。

[解码摘要](first-fault-summary.json)：8192点、61.44MHz，故障初值0；样本6142同步CS变高，6143回低并产生format_error，6144故障锁存为1；当时bits_seen=39，随后仍有第40个时钟。样本6457再次报格式错。此前BIST_REJECT通过，第二次start读取FAULT_STATUS得到1并隔离。

这是同步后的单拍高电平，不是针脚电压波形；不能据此确认真实脉宽、CPU中断或电气根因。UART/ILA属于先前诊断候选，不能用来验收最新无ILA bit。`!fall`是末沿合法性保护，不会消除这次39+1分帧事件。当前根因UNRESOLVED，不能把移除ILA等同于修复。

## 文件管理

正式源码、配方和报告更新原位置，旧报告由Git历史追溯；本目录只保留本批必要原件与结果，不是第二套工程。未创建codex_out临时工程；未删除他人材料。外部旧handoff和已保存故障证据保持原状。
