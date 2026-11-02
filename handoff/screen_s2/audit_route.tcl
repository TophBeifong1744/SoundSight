# Invoked with the candidate routed design open; root is the package directory.
foreach {port pin} {servo_pwm M15 servo_vertical_pwm J14} {
    if {[get_property PACKAGE_PIN [get_ports $port]] ne $pin} {error "Wrong pin for $port"}
    if {[get_property IOSTANDARD [get_ports $port]] ne "LVCMOS33"} {error "Wrong I/O voltage standard"}
    set paths [get_timing_paths -quiet -to [get_ports $port] -delay_type max -max_paths 5]
    if {![llength $paths]} {error "No max timing path to $port"}
    foreach path $paths {
        set slack [get_property SLACK $path]
        if {![string is double -strict $slack] || $slack eq "inf" || $slack < 0} {
            error "Invalid/failing max path to $port: $slack"
        }
    }
    report_timing -to [get_ports $port] -delay_type max -max_paths 5 -file [file join $root reports ${port}-max.rpt]
    # -datapath_only deliberately removes clock skew/hold checks for this
    # asynchronous PWM output. Retain min paths as diagnostic, not a fake PASS.
    report_timing -to [get_ports $port] -delay_type min -max_paths 5 -file [file join $root reports ${port}-min.rpt]
}
report_io -file [file join $root reports io.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $root reports timing-summary.rpt]
check_timing -verbose -file [file join $root reports check-timing.rpt]
report_utilization -file [file join $root reports utilization.rpt]
report_drc -file [file join $root reports drc.rpt]
report_methodology -file [file join $root reports methodology.rpt]
report_cdc -details -file [file join $root reports cdc.rpt]
report_clocks -file [file join $root reports clocks.rpt]
set clkfp [open [file join $root reports screen-clock-actual.txt] w]
foreach c [get_clocks -filter {NAME =~ *screen_pixel_clk*}] {puts $clkfp "$c PERIOD_NS=[get_property PERIOD $c] WAVEFORM=[get_property WAVEFORM $c]"}
close $clkfp
report_clock_interaction -file [file join $root reports clock-interaction.rpt]
report_bus_skew -file [file join $root reports bus-skew.rpt]
report_exceptions -ignored -file [file join $root reports ignored-exceptions.rpt]
foreach delay {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 1]]} {
        error "Negative $delay timing slack; no release bitstream"
    }
}
puts {SCREEN_PS_I2C_S2_ROUTED_AUDIT_COMPLETE BOARD_TEST=NOT_RUN}

report_route_status -file [file join $root reports route-status.rpt]
