# Arguments: isolated copied XPR, isolated package Tcl, output evidence directory.
# BD validation/output generation only; never launches synthesis or implementation.
foreach rel {support support/appinit support/args tclapp} {
 lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore $rel]
}
set xpr [lindex $argv 0]
set entry [lindex $argv 1]
set out [lindex $argv 2]
open_project $xpr
puts "FIXTURE_DIR=[get_property DIRECTORY [current_project]]"
puts "FIXTURE_BD=[get_property NAME [lindex [get_files -quiet *.bd] 0]]"
source $entry
set bd [lindex [get_files -quiet *.bd] 0]
file copy -force [get_property NAME $bd] [file join $out after-first.bd]
source $entry
file copy -force [get_property NAME $bd] [file join $out after-repeat.bd]
close_project
puts "CDC_BD_FIRST_REPEAT_PASS"
