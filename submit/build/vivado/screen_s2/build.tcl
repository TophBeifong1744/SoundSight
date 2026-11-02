# Run with Vivado 2025.2 in batch mode. Never accesses board hardware.
set root [file dirname [file normalize [info script]]]
cd $root
# 默认只综合；route参数显式启动布线和候选硬件导出。
set ss_action synth
if {$argc > 0} {set ss_action [lindex $argv 0]}
if {$ss_action ni {synth route}} {error "Usage: build.tcl -tclargs synth|route"}
# Process-local workaround for this host's damaged user TclStore catalog.
# Load the actual vendor package; do not stub or disable initialization.
if {[info exists ::env(XILINX_VIVADO)]} {
    set vendor_store [file join $::env(XILINX_VIVADO) data XilinxTclStore]
    foreach rel {support support/appinit tclapp} {
        lappend ::auto_path [file join $vendor_store $rel]
    }
    set ::env(TCLLIBPATH) $::auto_path
    package require ::tclapp::support::appinit 1.2
}
file mkdir reports
file mkdir output
# Vivado implementation supports at most 8 general worker threads.
set_param general.maxThreads 8
source [file join $root project.tcl]
update_compile_order -fileset sources_1
report_ip_status -file [file join $root reports ip-status.rpt]
set fp [open [file join $root reports source-files.txt] w]
foreach f [get_files -compile_order sources -used_in synthesis] {
    puts $fp $f
    if {![file exists $f]} {error "Missing synthesis source: $f"}
}
close $fp
launch_runs synth_1 -jobs 16
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis incomplete"}
if {$ss_action eq "synth"} {puts {SCREEN_PS_I2C_S2_SYNTHESIS_COMPLETE}; return}
launch_runs impl_1 -to_step route_design -jobs 16
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "route_design Complete!"} {
    error "Implementation did not finish routing: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
source [file join $root audit_route.tcl]
source [file join $root export_hw.tcl]
