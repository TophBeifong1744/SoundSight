# CDC控制修复验证记录

2026-10-24，Vivado/XSim 2025.2，xc7z020clg400-2。基线为用户10:34:34生成bit对应的外部Reliaze工程；原三条CDC-10证据在 `../ps-pcm-board-package-20261024/cdc-analysis`。

## 候选与验证

正式修改：`project/rtl/ss_dual_compute.sv`、`bd_clean_compute.v`、`ss_audio_capture.sv`、`bd_audio_capture.v`；工程入口为 `project/bd/update_ps_reliaze.tcl`。修改含源端寄存、共享enable、源端寄存drain，以及旧接口连线迁移。未改变数值处理、PCM格式、公共STOP或XDC。

`validation.json` 汇总本次各仿真结果、PASS原文、源文件哈希和检查器反向验证。`simulations/` 保留 RESULT、编译/展开/仿真日志及六对输出；大数据库不纳入证据包。

| 仿真 | 真实检查内容 |
|---|---|
| audioctrl | 40次跨域前短毛刺、共享run、8次快速启停、drain互锁、总线/DMA/冷复位；5个完整包核对首样本、顺序、epoch、TLAST |
| audio | S24符号/通道、包头/TLAST、背压稳定性、窗口/半包/溢出、epoch和DMA复位 |
| dualaudio | 官方FFT/IFFT，正常帧、在途STOP取消、恢复；3帧12组声对、时间关联 |
| duallevel | AUDIO_ENABLE=0；同样3帧和音量检查，六对输出与开启音频一致 |
| dual | AUDIO_ENABLE=0、LEVEL_ENABLE=0的旧模式，正常/取消/恢复 |
| manual | 84694项手动控制、范围、看门狗、STOP和模式互斥检查 |

`run_canary.py enable` / `run_canary.py drain` 仅在隔离仿真快照内分别将源端寄存改回0；应命中相应的 `AUDIOCTRL_FAIL ... glitch crossed`。这是预期失败，证明毛刺检查器能检测错误；正式RTL不含该修改。仿真不能模拟真实亚稳态或证明硬件MTBF。

复现常规仿真：仓库根目录 `python -B tools/run_sim.py <case>`。Tcl保护检查为 `python -B -m unittest software.tests.test_reliaze_tcl -v`，共10项。`audioctrl` 的PCM输入是夹具，收尾互锁强制busy仅覆盖该接口条件；其余完整算法仿真覆盖真实取消。

## BD原件

`before.bd` 是外部工程的实际旧PCM BD。`after-first.bd`、`after-repeat.bd` 来自隔离复制工程中执行最新入口两次。`fixture.tcl` / `fixture.log` 是实际工具驱动与日志，只打开隔离工程、Validate、生成输出，不启动物理构建。

`bd-audit.json` 绑定17份候选文件，确认只迁移两根控制线、无新增IP、重复执行BD完全相同、其余BD字段及原有显式PS参数保留。`ps-parameters.json` 保存原外部HWH与隔离新HWH的参数：929项相同；8项未启用交叉触发选择器由 `DISABLED` 变为 `<Select>`，总使能与四个端口使能均保持0，PS端口相同。没有把工具默认值序列化误报为新增DDR/MIO配置。

审计入口：`tools/check_cdc_control_bd.py --evidence <本目录> --sources <隔离工程实际登记RTL目录>`。实际目录为隔离工程 `.srcs/sources_1/imports/horizontal_sources`，审计结果已保存。隔离工程完成用途后清理，日志原路径保留。

首次模块刷新两条 `Coretcl 2-1280` 对应有意端口增删，后续接线、Validate及输出生成完成；保留日志中TclStore、未安装无关board part、Windows长路径等环境警告，不宣称工具零Warning。

## 失败事实及修复

- 隔离验证最初在修改前报 `STOP: BD is outside the copy`。XPR迁移路径核对后问题仍在；诊断明确打开BD时Vivado初始化脚本把调用者 `dir` 改为工具内部目录。正式入口增加独立 `open_design` 过程隔离变量，添加回归后，同一隔离工程两次更新成功。保留 `fixture-initial-failure.log`、`fixture-caller-scope-failure.log`；中间重复日志归并到本说明。
- Tcl测试首次把嵌套列表当平坦Python元组比较，改用Tcl `llength/lindex` 后通过，没有据此改RTL。
- 反向验证辅助脚本准备阶段曾遇到默认GBK解码、只读厂商文件重复复制、环境键大小写/Windows命令路径问题；统一UTF-8、保留已复制只读文件、沿用正式仿真入口的原生路径后，编译/展开成功并命中指定Fatal。这些是辅助脚本错误，不是DUT失败；最终原生日志与退出码保留。
- 首次审计命令误用了不存在的 `imports/rtl`，读取实际登记路径 `imports/horizontal_sources` 后通过；无放宽审计条件。

## 未完成范围

新候选综合、实现、布线CDC/STA/资源、bit/HWH配套核验、板测均 `NOT_RUN`。原1252条CDC-15 Warning及其他RDC/DRC不因本次结构修复自动关闭。没有执行F盘工程修改、综合、实现、下载、舵机动作，也没有独立非作者签核或Git提交/推送。
