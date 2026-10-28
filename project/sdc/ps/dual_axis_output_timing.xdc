# 双轴专用垂直PWM最大路径预算，与interface_timing.xdc中的水平20ns一致。
# 仅由update_ps_dual_axis.tcl登记；普通PS/STM32和旧单轴入口不加载本文件。
# 这是寄存器到端口的设计预算，不代表外部连线或舵机已经实测。
# PWM无外部采样时钟；datapath_only自动忽略hold，最小路径仅报告，不作0ns hold验收。
set dual_axis_io_launch_pins [all_registers -clock_pins]
set_max_delay -datapath_only 20.000 -from $dual_axis_io_launch_pins -to [get_ports servo_vertical_pwm]
