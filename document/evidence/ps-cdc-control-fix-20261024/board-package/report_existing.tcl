# Inspect an existing routed checkpoint; never rebuild, write bit, or access board.
foreach rel {support support/appinit support/args tclapp} {
 lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore $rel]
}
set checkpoint [lindex $argv 0]
set reports [lindex $argv 1]
file mkdir $reports
open_checkpoint $checkpoint
report_cdc -details -file [file join $reports cdc_routed.rpt]
report_utilization -file [file join $reports utilization_routed.rpt]
report_utilization -hierarchical -file [file join $reports utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -max_paths 10 -file [file join $reports timing_verified.rpt]
set f [open [file join $reports control_structure.txt] w]
puts $f "PART=[get_property PART [current_design]]"
foreach c [get_cells -hier -filter {NAME =~ *enable_sync* || NAME =~ *with_audio*drain_sync* || NAME =~ *audio_capture*run_sync* || NAME =~ *audio_capture*drain_sync*}] {
 puts $f "CELL=$c REF=[get_property REF_NAME $c]"
 if {[string match FD* [get_property REF_NAME $c]]} {
  puts $f " CLOCK=[get_clocks -quiet -of_objects [get_pins $c/C]] ASYNC_REG=[get_property ASYNC_REG $c]"
  puts $f " D_STARTPOINTS=[all_fanin -flat -startpoints_only -to [get_pins $c/D]]"
 }
}
close $f
close_design
puts "CDC_REBUILD_REPORTS_COMPLETE"
