# Read-only logic-cone inspection of the user's already-routed checkpoint.
foreach rel {support support/appinit support/args tclapp} {
    lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore $rel]
}
open_checkpoint [lindex $argv 0]
set out [open [lindex $argv 1] w]
set targets [get_pins -hier -regexp {soundsight_stm32_bd_i/(audio_capture/inst/core/(run_sync|drain_sync)|compute/inst/u_core/enable_sync)/syncstages_ff_reg\[0\]/D}]
if {[llength $targets] != 3} {error "Expected three CDC-10 targets, got [llength $targets]"}
foreach target $targets {
    puts $out "TARGET $target"
    puts $out "STARTPOINTS [all_fanin -flat -startpoints_only -to $target]"
    foreach cell [lsort [all_fanin -flat -only_cells -to $target]] {
        set ref [get_property REF_NAME [get_cells $cell]]
        set clocks [get_clocks -quiet -of_objects [get_pins -quiet -of_objects [get_cells $cell] -filter {REF_PIN_NAME == C || REF_PIN_NAME == CLK}]]
        puts $out "CELL $cell REF=$ref CLOCKS=$clocks"
        if {[string match LUT* $ref]} {
            puts $out "INIT [get_property INIT [get_cells $cell]]"
            foreach p [get_pins -of_objects [get_cells $cell] -filter {DIRECTION == IN}] {
                puts $out " INPUT $p DRIVERS=[get_pins -quiet -of_objects [get_nets -quiet -of_objects $p] -filter {DIRECTION == OUT}]"
            }
        }
    }
    puts $out ""
}
close $out
close_design
puts "CDC_CONE_INSPECTION_COMPLETE"
