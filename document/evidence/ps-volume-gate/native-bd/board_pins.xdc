# PL+PS目标的外部PL引脚配置；无STM32 SPI/IRQ端口。
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
# 与公共RTL的四路独立输出寄存器配套；本目标仍需单独运行实现验证。
set_property SLEW FAST [get_ports {pdm_clocks[*]}]
set_property DRIVE 8 [get_ports {pdm_clocks[*]}]
set_property IOB TRUE [get_ports {pdm_clocks[*]}]
