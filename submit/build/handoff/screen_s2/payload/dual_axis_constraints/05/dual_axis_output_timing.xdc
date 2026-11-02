# Internal register-to-pin engineering budget, not a servo sampling-clock delay.
# Same 20 ns maximum / 0 ns minimum convention as existing horizontal PWM.
# Check matched endpoints and finite routed slack in build.tcl.
set servo_j3_launch_pins [all_registers -clock_pins]
set_max_delay -datapath_only 20.000 -from $servo_j3_launch_pins -to [get_ports servo_vertical_pwm]
set_min_delay 0.000 -from $servo_j3_launch_pins -to [get_ports servo_vertical_pwm]
