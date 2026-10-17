# 独立 soundsight_stm32_bd_wrapper 的引脚配置。只用于独立迁移工程。
# 2026-10-17双方确认分配；装入前检查实际Bank13供电、LVCMOS33和排针方向。
# 外部PL引脚在本文件；时钟来自PS FCLK和Clocking Wizard；配套接口约束见interface_timing.xdc及其预算说明。
set_property PACKAGE_PIN T15 [get_ports servo_pwm]
set_property PACKAGE_PIN V11 [get_ports {pdm_clocks[0]}]
set_property PACKAGE_PIN Y13 [get_ports {pdm_clocks[1]}]
set_property PACKAGE_PIN U14 [get_ports {pdm_clocks[2]}]
set_property PACKAGE_PIN V12 [get_ports {pdm_clocks[3]}]
set_property PACKAGE_PIN Y9 [get_ports {pdm_data[0]}]
set_property PACKAGE_PIN W10 [get_ports {pdm_data[1]}]
set_property PACKAGE_PIN W14 [get_ports {pdm_data[2]}]
set_property PACKAGE_PIN V15 [get_ports {pdm_data[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {servo_pwm pdm_clocks[*] pdm_data[*]}]
set_property DRIVE 4 [get_ports {servo_pwm pdm_clocks[*]}]
set_property SLEW SLOW [get_ports {servo_pwm pdm_clocks[*]}]
