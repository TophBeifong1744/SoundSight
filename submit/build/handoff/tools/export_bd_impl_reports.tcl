# Generic Vivado Project Mode report exporter. Source in the Vivado GUI.
# No project names, device names, tool paths or source paths are hard-coded.
# Optional settings BEFORE source:
#   set ::bd_impl_export_run impl_2
#   set ::bd_impl_export_dir {./my_reports}
# Each invocation creates a new directory; existing exports are preserved.

namespace eval bd_impl_export {}

proc bd_impl_export::nonempty {path} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Report was not created or is empty: $path"
    }
}

proc bd_impl_export::run {} {
    if {[llength [get_projects -quiet]] != 1} {
        error {Open one Vivado project before sourcing this script.}
    }
    set project [current_project]
    set run [current_run -implementation]
    if {[info exists ::bd_impl_export_run]} {
        set run [get_runs -quiet $::bd_impl_export_run]
    }
    if {[llength $run] != 1 || ![get_property IS_IMPLEMENTATION $run]} {
        error {Select an implementation run, or set ::bd_impl_export_run.}
    }
    set status [get_property STATUS $run]
    # A synthesis/place-only result must never be labelled as routed timing.
    if {![regexp -nocase {^(route_design|post_route_phys_opt_design|write_bitstream) Complete} $status]} {
        error "Implementation must finish routing first. Run=$run; status=$status. No run was launched."
    }
    if {[lsearch -exact [list_property $run] NEEDS_REFRESH] >= 0 &&
        [get_property NEEDS_REFRESH $run]} {
        error {Implementation is out of date. Complete the intended implementation first.}
    }
    set base [file join [get_property DIRECTORY $project] reports]
    if {[info exists ::bd_impl_export_dir]} {set base $::bd_impl_export_dir}
    set stamp [clock format [clock seconds] -format %Y%m%d_%H%M%S]
    set out [file normalize [file join $base export_$stamp]]
    set suffix 0
    while {[file exists $out]} {
        incr suffix
        set out [file normalize [file join $base export_${stamp}_$suffix]]
    }
    file mkdir $out
    puts "REPORT_EXPORT_DIR=$out"
    set errors {}
    set notes [list "Project: [get_property NAME $project]" \
        "Implementation: $run" "Run status: $status" "Vivado: [version -short]" \
        {Reports describe the saved implementation run. BD PDFs describe the current BD.} \
        {Export completion does not mean timing or constraints passed.}]

    # Export every registered BD without changing its layout or saving edits.
    # PDF drawing needs the Vivado GUI; failures do not discard STA reports.
    set bds [get_files -quiet -filter {FILE_TYPE == "Block Designs"}]
    set prior_bd [current_bd_design -quiet]
    set index 0
    foreach bd $bds {
        incr index
        set name [file rootname [file tail [get_property NAME $bd]]]
        set pdf [file join $out [format {bd_%02d_%s.pdf} $index $name]]
        if {[catch {
            open_bd_design $bd
            write_bd_layout -format pdf -orientation landscape $pdf
            nonempty $pdf
        } why]} {
            lappend errors "BD $name: $why"
        } else {
            lappend notes "BD PDF: [file tail $pdf]"
        }
    }
    if {$prior_bd ne {}} {catch {current_bd_design $prior_bd}}
    if {$index == 0} {lappend notes {No registered Block Design; PDF skipped.}}

    # Open a separately named saved implementation, not an edited netlist tab.
    if {[catch {open_run $run -name report_export_[clock clicks]} why]} {
        lappend errors "Open implementation: $why"
    } else {
        foreach {file options} {
            utilization_report_imp.txt {report_utilization}
            utilization_hierarchy_imp.txt {report_utilization -hierarchical}
            timing_report_imp.txt {report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -max_paths 50 -input_pins}
        } {
            set path [file join $out $file]
            if {[catch {
                {*}$options -file $path
                nonempty $path
            } why]} {lappend errors "$file: $why"}
        }
    }
    set f [open [file join $out export_info.txt] w]
    fconfigure $f -encoding utf-8
    puts $f [join $notes \n]
    puts $f "Export errors: [llength $errors]"
    foreach why $errors {puts $f "ERROR: $why"}
    close $f
    if {[llength $errors]} {
        error "Partial export retained at $out\n[join $errors \n]"
    }
    puts "EXPORT_COMPLETE=$out"
    return $out
}

if {![info exists ::bd_impl_export_library_only] || !$::bd_impl_export_library_only} {
    bd_impl_export::run
}
