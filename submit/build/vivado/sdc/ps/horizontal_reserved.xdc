# Only the explicit horizontal preparation recipe adds this constraint file.
# Vertical 220-degree pin: DUAL_AXIS_ENABLE=0 reserves LOW; =1 enables protected control.
# Horizontal 360-degree servo uses T15 in board_pins.xdc.
set_property PACKAGE_PIN W16 [get_ports servo_vertical_pwm]
set_property IOSTANDARD LVCMOS33 [get_ports servo_vertical_pwm]
set_property DRIVE 4 [get_ports servo_vertical_pwm]
set_property SLEW SLOW [get_ports servo_vertical_pwm]
