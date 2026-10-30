set ::ss_cli 1
set ::ss_args $argv
if {[catch {source [file normalize [file join [file dirname [info script]] ../project/script/vivado.tcl]]} message options]} {
    puts stderr "SOUNDSIGHT_PREPARATION_ERROR: $message"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
