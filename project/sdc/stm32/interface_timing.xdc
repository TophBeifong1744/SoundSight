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

# SPI 是异步输入电平的过采样，不把 SCK 当 RTL 时钟、不虚构它与 sys_clk 的相位。
foreach {port regname} {spi_cs_n cs_sync_reg spi_sck ck_sync_reg spi_mosi di_sync_reg} {
    set first [get_pins -hier -regexp [format {.*spi/%s\[0\]/D} $regname]]
    if {[llength $first] != 1} {error "SPI first-stage pin not found: $regname"}
    set_max_delay -datapath_only 4.000 -from [get_ports $port] -to $first
    set_min_delay 0.000 -from [get_ports $port] -to $first
}
# 输出到异步接收端的布线/IO 上限；协议端到端余量另见说明，不是同步 SCK 输出延迟假设。
set_max_delay -datapath_only 20.000 -to [get_ports {spi_miso irq servo_pwm}]
set_min_delay 0.000 -to [get_ports {spi_miso irq servo_pwm}]


# 跨域FIFO/同步器、Clocking Wizard、Processor System Reset的约束由各官方IP/XPM提供。
# 不对整片时钟设置false_path；报告中须检查XPM约束和CDC结构确实生效。
