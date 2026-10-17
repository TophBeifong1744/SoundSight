# 采集/公共控制61.44 MHz，计算/PS AXI100 MHz；时钟由官方IP生成。
# 此文件给出实际 I/O 路径的设计上限，不声称杜邦线/实际布线已测。
# 计算依据见 interface_timing.txt；综合后名称若变化应修正查询，不能静默丢约束。

# PDM 数据经两级同步，在 phase==9 使用。只约束端口到第一级，第二级仍按 61.44 MHz 检查。
set pdm_first [get_pins -hier -regexp {.*acquisition/pdm_meta_reg\[[0-3]\]/D}]
if {[llength $pdm_first] != 4} {error {PDM first-stage pins not found; inspect hierarchy before implementation}}
set_max_delay -datapath_only 4.000 -from [get_ports {pdm_data[*]}] -to $pdm_first
set_min_delay 0.000 -from [get_ports {pdm_data[*]}] -to $pdm_first
set_max_delay -datapath_only 4.000 -to [get_ports {pdm_clocks[*]}]
set_min_delay 0.000 -to [get_ports {pdm_clocks[*]}]

# PS版无外部SPI；AXI与计算使用同一61.44MHz，PS7的GP0 CDC由硬核负责。
# proc_sys_reset自身约束由官方IP提供；PS总线复位不清快照。
set_max_delay -datapath_only 20.000 -to [get_ports servo_pwm]
set_min_delay 0.000 -to [get_ports servo_pwm]


# 跨域FIFO/同步器、Clocking Wizard、Processor System Reset的约束由各官方IP/XPM提供。
# 不对整片时钟设置false_path；报告中须检查XPM约束和CDC结构确实生效。
