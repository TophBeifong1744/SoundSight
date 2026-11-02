# 同一冻结工程的原生构建续跑，不改变设计策略或源文件。
set root [file dirname [file normalize [info script]]]
cd $root
set vendor_store [file join $::env(XILINX_VIVADO) data XilinxTclStore]
foreach rel {support support/appinit tclapp} {lappend ::auto_path [file join $vendor_store $rel]}
set ::env(TCLLIBPATH) $::auto_path
package require ::tclapp::support::appinit 1.2
set_param general.maxThreads 8
open_project [file join $root project par SoundSight_PS_3D.xpr]
reset_run synth_1
launch_runs synth_1 -jobs 16
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis incomplete"}
launch_runs impl_1 -to_step route_design -jobs 16
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "route_design Complete!"} {error "Route incomplete"}
open_run impl_1
source [file join $root audit_route.tcl]
source [file join $root export_hw.tcl]
