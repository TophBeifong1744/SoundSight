# 三条CDC-10的只读诊断（2026-10-24）

范围：实际routed DCP中的三条Critical，核对RTL、当前BD及Vivado2025.2本机XPM实现；未修改产品RTL/BD/XDC、位流或交付ZIP，未综合实现或执行硬件。
probe.tcl只读打开已有检查点，cones.txt是工具查询的原件，probe.log保存本次运行。工具启动时TclStore权限警告与设计CDC-10分开。
当前bit SHA256仍为550d8803f7bfb5200069cc40f030efe41c14cb753324e282e9a2d68133801878。

## 已确认的结构

三条均为61.44MHz到100MHz；实际源端寄存器都属于61.44MHz。目的端已有两级ASYNC_REG同步链，但SRC_INPUT_REG均为0。

| 目的端 | 同步器前的实际逻辑 | 用途/影响 |
|---|---|---|
| audio_capture/.../run_sync | PS控制的run_enable LUT5 | 音频门控；run短暂变低可令armed撤销，结束本次录音 |
| compute/.../enable_sync | 同一run_enable LUT5，再与io_rst_n经过LUT2 | 计算链启停；错误电平可能造成误取消或计算/采集状态不一致 |
| audio_capture/.../drain_sync | run_enable LUT5，再经draining LUT6 | 判定上次计算是否收尾完毕，参与音频重装会话条件 |

源公式：

```text
run_enable = sys_ctrl[0] && !sys_ctrl[1] && !stop_latched && !counter_exhausted && !host_stop
host_stop = !ps_link.aresetn
draining = !enable && (enable_return || busy_return || feature_valid)
```

实际bus_io_reset/peripheral_aresetn接ps_link/aresetn；compute/io_rst_n另由冷复位io_release提供。
报告把bus_io_reset寄存器列为源，是因为它参与了这些判断，不证明官方复位IP本身损坏。
run_sync当前源时钟接常量0，SRC_INPUT_REG=0时该端口不用，这是合法用法；但不能只改参数为1而继续把src_clk接0。

结论：报告与实际组合逻辑结构一致，不能按误报豁免。不同寄存器/门延迟在状态切换时可能造成窄脉冲；两级同步器不能保证把所有窄脉冲滤掉。
这是结构性风险，不是已经观测到真实毛刺/丢样，也不是计数为3就等于存在三个彼此独立的设计错误。
布线WNS通过与CDC-10并不矛盾，相关同步入口已有False Path；时序通过不能代替CDC/RDC判断。

## 推荐修复方向（尚未实现或验证）

1. 在ss_dual_compute统一处理61.44到100MHz的控制跨域：enable_sync启用源时钟寄存器，src_clk使用已有io_clk，所有组合判断放在源寄存器之前。
2. 把同一个core_enable同步结果输出给音频模块，删除音频内部重复run_sync。两者在相同100MHz域使用同一份控制结果，避免平行同步链独立延迟。
3. draining在61.44MHz源端登记后同步到100MHz，只在AUDIO_ENABLE分支生成，输出给音频；保持原61.44MHz draining给PS的语义。
4. ss_audio_capture使用两个明确标注为100MHz域的输入，删除其原run_sync/drain_sync。bd_clean_compute/bd_audio_capture加透传端口；update_ps_reliaze.tcl把两根音频控制线改接compute的新输出，兼容初次与重复更新。
5. 原PS本地STOP撤动作许可保持直接生效；不能为了消除CDC而延后/绕过执行器保护。冷复位与总线复位仍分开。

涉及主要文件：ss_dual_compute.sv、ss_audio_capture.sv、bd_clean_compute.v、bd_audio_capture.v、update_ps_reliaze.tcl，以及audio/dualaudio/普通双时钟回归TB与BD审计工具的相应端口/连线期待。旧ss_ps_control_regs的公共寄存器含义不变。
不增加时钟、DMA、FFT或大FIFO。源端寄存器数量为个位数，删除重复同步链可抵消部分开销；净FF/LUT与时序必须以新实现为准。源端多一个周期约16.28ns，必须复验启停协议而非默认无影响。

最小替代是为三个同步器分别加源端寄存器并向音频模块补61.44MHz时钟；虽可直接对应CDC-10修复，但仍保留两份同源run同步，故不是首选。

## 完成修复后的判据

- 首个有效采样、512点包边界、同帧元数据保持；快速START/STOP和停止后立即重启不能混会话/提前判空闲。
- 总线复位、冷复位、DMA复位、处理中停止均无旧会话重新激活；原手动/声音动作保护保持。
- 旧AUDIO_ENABLE=0路径仍运行；在不同两时钟相位下检查启停。
- 重新生成BD输出、定向仿真后，由用户综合/实现/生成bit；新报告确认这3个端点不再报CDC-10，且没有新增CDC/RDC/时序问题。
- 现有REQP异步RAM控制、LUTAR互联复位及CDC-15另行判读；本结论不将它们一并关闭。

依据：[AMD UG906组合逻辑CDC规则](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Combinatorial-Logic)、[UG953单比特同步宏](https://docs.amd.com/r/en-US/ug953-vivado-7series-libraries/XPM_CDC_SINGLE)。在线页面当前为2026.1；参数实际行为同时核对了本机2025.2的xpm_cdc.sv中SRC_INPUT_REG生成分支，未依赖更新版本推断本机实现。

收尾：只读查询结束，simulation/work/cdc-inspect会话缓存清理；原始查询脚本/输出/日志保留本目录。
