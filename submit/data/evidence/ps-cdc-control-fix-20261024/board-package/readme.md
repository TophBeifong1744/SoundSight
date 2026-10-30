# CDC修复后新构建接收与PYNQ包

2026-10-24。用户完成综合、实现和bit生成；本轮仅只读检查现有工程/检查点、生成报告及打包。未执行新综合/实现/bit生成、下载、复位或运动。

## 核对结论

- 原三条CDC-10 Critical全部消除，当前CDC报告Critical=0。enable和drain两条链均为CDC-3 Info；实际源端各1个FDRE、目的端各2个FDRE且ASYNC_REG=1，总计6个触发器。原audio_capture的run_sync/drain_sync已不存在。源/目的时钟分别为61.44MHz与100MHz。
- WNS +0.229ns（原+0.165ns，改善0.064ns）；WHS +0.036ns；WPWS +2.208ns。setup/hold/pulse-width失败端点均0。用户原报告与重新打开同一DCP生成的min/max报告一致；check_timing各摘要项0。
- LUT17398/53200（32.70%）、FF19351/106400（18.19%）、BRAM32/140（22.86%）、DSP41/220（18.64%），与旧实现完全相同。不是估算，数值来自本次routed检查点。36,093条可布线网络全部完成，布线错误0；bus skew无违例，最小余量见hardware-review.json。
- bit内部时间12:47:56，文件完成12:47:57；XSA导出12:48:51。bit/HWH与XSA内容逐字节相同；实际XPR登记16份RTL与已仿真修复候选逐字节匹配，文件修改时间早于新bit。HWH中两根新控制线连接正确；T15/W15、Bank34、LVCMOS33保持。

bit SHA256：`b45b0f2be5572665f761b11e5d7160f3b8520803c65012850734519c3f505380`

HWH SHA256：`4383b94604e7626a1dbd7e2da8f856213144fecb8cf7021f8a535c9212f16914`

XSA SHA256：`97017343e2cd6191184c15099b3e2a72f013cec7436d90eb7355f955cec096ff`

## 原件与复现

`inputs.json`记录实际路径/产物哈希/登记RTL匹配；`hardware-review.json`记录数值、完整CDC摘要、剩余DRC项及所有报告摘要；`reports/control_structure.txt`来自实现网表，不是源码推断。`implementation-runme.log`为用户本次实现原日志，含checkpoint与bit生成完成记录。

`report_existing.tcl`通过open_checkpoint读取已有routed DCP，只调用report命令及网表查询；`report-existing.log`为实际工具原件。可用Vivado2025.2 batch执行，`-tclargs <routed.dcp> <报告输出目录>`。仅进程内补齐安装目录的TclStore搜索路径，没有修改用户环境。保留用户TclStore Critical Warning、commands.paini权限警告；它们与设计CDC Critical计数分开。时序更新显示工具最多使用2个CPU，没有修改全局线程设置。

## 独立新包

`release/output/soundsight_pynq_pcm_cdc.zip`，解压根目录 `SoundSight_PYNQ_PCM_CDC`；旧Servo、旧PCM、原工程更新包均未覆盖。

复现打包：`python -B tools/package_pynq.py --hardware-project <Reliaze目录> --xsa <本次XSA> --pcm-cdc`。目标ZIP已存在时拒绝覆盖。新增模式要求本次review的bit/HWH/XSA/DCP及报告哈希一致，实际RTL匹配已仿真候选，并检查HWH控制连线；不再将修复前CDC报告混入新包。

新包78文件、76项载荷哈希检查、ZIP CRC和Python3.8语法检查通过。43份软件/测试/启动文件与原PCM包逐字节一致。包内复测7组90项：PCM19、board_tools15、serial_english3、manual8、filter13、normal17、volume15，见`tests.json`及`logs`。

复测驱动首次误用了不存在的test_normal_mode.py（退出2），没有运行该组测试；核对包内清单后用实际test_normal.py通过，前五组无需重跑，失败命令及日志保留。不是产品测试失败或忽略失败。

`package-receipt.json`绑定新ZIP摘要与离线结果；板端安装/prepare/pcm-check见仓库 `document/pynq-pcm-cdc-first-run.md`及包内README。先只读接口检查，随后做无动作的一包诊断。

## 保留边界

仍有1252条CDC-15 Warning；DRC中的RAM异步控制、互联异步复位、DSP流水及其他Warning未在本轮逐项签核。DRC包含CHECK-3报告条数上限提示，不能从显示项数推断全设计问题总数。详细时序仍有PS复位/IP内部Unconstrained Path，摘要0不等于每条豁免/复位路径均已审查。

本结论是指定3条CDC-10关闭及同候选产物检查，不是全部CDC/RDC或独立非作者签核。新组合ARM、真实PCM/DMA、麦克风连续性、声纹、机械动作均NOT_RUN。

正式证据保留本目录；本任务解压验证目录codex_out/pcm-cdc-package-check与只读报告缓存simulation/work/cdc-receipt完成后清理。原始日志中的历史路径不改写，其他仿真结果保留。
