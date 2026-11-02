# Run in an empty Vivado session; all input paths follow this package.
if {[llength [get_projects -quiet]]} {error {Close the current project before recreating this package}}
set ss_package [file dirname [file normalize [info script]]]
if {[file exists [file join $ss_package project par]]} {error {project/par already exists; use a fresh package copy}}
set ss_old_pwd [pwd]
set ss_saved_vars [dict create]
foreach key {origin_dir_loc argv argc} {
    if {[info exists ::$key]} {dict set ss_saved_vars $key [set ::$key]}
}
try {
    cd $ss_package
    set ::origin_dir_loc [file join $ss_package payload]
    set ::argv {};set ::argc 0
    source [file join $ss_package recipe.tcl]
} finally {
    cd $ss_old_pwd
    foreach key {origin_dir_loc argv argc} {
        if {[dict exists $ss_saved_vars $key]} {set ::$key [dict get $ss_saved_vars $key]} else {unset -nocomplain ::$key}
    }
}
add_files -fileset constrs_1 -norecurse [file join $ss_package payload dual_axis_constraints 05 dual_axis_output_timing.xdc]
puts {PROJECT_RECREATED_NO_SYNTHESIS_OR_IMPLEMENTATION_STARTED}

# 屏幕独立接合，不修改声音算法或既有地址。
source [file join $ss_package screen_integration.tcl]
