# J3 servo remap: vertical J3 pin 3 = J14, Bank 35, LVCMOS33.
# P3 CAN TX jumper 1-2 must be disconnected. Horizontal is M15 / J3 pin 2.
set_property PACKAGE_PIN J14 [get_ports servo_vertical_pwm]
set_property IOSTANDARD LVCMOS33 [get_ports servo_vertical_pwm]
set_property DRIVE 4 [get_ports servo_vertical_pwm]
set_property SLEW SLOW [get_ports servo_vertical_pwm]
