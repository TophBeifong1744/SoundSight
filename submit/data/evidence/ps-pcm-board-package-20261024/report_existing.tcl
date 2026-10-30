# Read existing routed design only. No synthesis, implementation or bit generation.
set dcp [lindex $argv 0]
set out [lindex $argv 1]
# Process-local workaround for the sandbox's unavailable user TclStore index.
# Uses the running Vivado installation, never changes the user's TclStore.
foreach rel {support support/appinit support/args tclapp} {
    lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore $rel]
}
file mkdir $out
open_checkpoint $dcp
report_cdc -details -file [file join $out cdc_routed.rpt]
report_utilization -hierarchical -file [file join $out utilization_hierarchical.rpt]
close_design
puts "EXISTING_CHECKPOINT_REPORTS_COMPLETE"
