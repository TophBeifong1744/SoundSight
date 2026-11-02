# 只读重开S2正式工程，核对PS I2C0身份与源文件归属，不启动综合/实现。
set root [file dirname [file dirname [file normalize [info script]]]]
set vendor_store [file join $::env(XILINX_VIVADO) data XilinxTclStore]
foreach rel {support support/appinit tclapp} {lappend ::auto_path [file join $vendor_store $rel]}
package require ::tclapp::support::appinit 1.2
open_project [file join $root project par SoundSight_PS_3D.xpr]
open_bd_design [get_files -norecurse soundsight_stm32_bd.bd]
validate_bd_design
if {[llength [get_bd_cells -quiet screen_iic]]} {error "AXI IIC unexpectedly remains"}
if {[get_property CONFIG.PCW_EN_EMIO_I2C0 [get_bd_cells ps7]] != 1} {error "PS I2C0 EMIO missing"}
if {[get_property CONFIG.NUM_MI [get_bd_cells control_bus]] != 5} {error "Control bus count mismatch"}
report_ip_status -file [file join $root reports reopen-ip-status.rpt]
set inputs [lsort -unique [concat [get_files -compile_order sources -used_in synthesis] [get_files -of_objects [get_filesets constrs_1]]]]
set fp [open [file join $root reports actual-inputs.txt] w]
set errors {}
foreach f $inputs {
    set path [file normalize $f]
    puts $fp $path
    if {![file exists $path]} {lappend errors "MISSING $path"}
    set lower [string tolower $path]
    if {[string first [string tolower "$root/"] $lower] != 0 && [string first [string tolower "[file normalize $::env(XILINX_VIVADO)]/"] $lower] != 0} {lappend errors "EXTERNAL $path"}
}
close $fp
foreach ip [get_ips] {if {[get_property IS_LOCKED $ip]} {lappend errors "LOCKED_IP $ip"}}
set fp [open [file join $root reports reopen-result.txt] w]
puts $fp "PROJECT=[get_property NAME [current_project]]"
puts $fp "VERSION=[version -short]"
puts $fp "INPUTS=[llength $inputs]"
puts $fp "ERRORS=[llength $errors]"
puts $fp "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
puts $fp "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
foreach e $errors {puts $fp $e}
close $fp
if {[llength $errors]} {error $errors}
puts {SCREEN_PS_I2C_S2_REOPEN_PASS}
close_project
