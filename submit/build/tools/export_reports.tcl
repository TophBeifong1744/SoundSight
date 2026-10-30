# 用户点击综合/实现完成后导出报告。此文件不启动任何run，不复位/替换工程。
# source本文件，然后 ss_reports::save synth 或 ss_reports::save impl。
namespace eval ss_reports {
    variable root [file dirname [file normalize [info script]]]
    proc save {stage} {
        variable root
        if {$stage ni {synth impl}} {error {Use: ss_reports::save synth|impl}}
        if {![llength [get_projects -quiet]]} {error {No open project}}
        if {[get_property NAME [current_project]] ni {SoundSight SoundSight_PS}} {error {Not a migration project}}
        if {$stage eq {synth}} {set run [current_run -synthesis]} else {set run [current_run -implementation]}
        set status [get_property STATUS $run]
        if {[get_property PROGRESS $run] ne {100%} || ![string match -nocase {*complete*} $status]} {
            error "Selected run is not complete: $run $status"
        }
        open_run $run
        set out [file join [get_property DIRECTORY [current_project]] reports ${stage}_[clock format [clock seconds] -format %Y%m%d_%H%M%S]]
        file mkdir $out
        set h [open [file join $out context.txt] w]
        puts $h "project=[get_property DIRECTORY [current_project]]"
        puts $h "part=[get_property PART [current_project]] top=[get_property TOP [get_filesets sources_1]] run=$run status=$status"
        foreach f [get_files -of_objects [get_filesets sources_1]] {puts $h "source=[get_property NAME $f]"}
        foreach f [get_files -of_objects [get_filesets constrs_1]] {puts $h "constraint=[get_property NAME $f]"}
        close $h
        set commands [list \
            [list report_timing_summary -delay_type min_max -report_unconstrained -max_paths 50 -file [file join $out timing_summary.txt]] \
            [list report_timing -delay_type max -slack_lesser_than 0 -max_paths 100 -file [file join $out setup_violations.txt]] \
            [list report_timing -delay_type min -slack_lesser_than 0 -max_paths 100 -file [file join $out hold_violations.txt]] \
            [list report_utilization -hierarchical -file [file join $out utilization.txt]] \
            [list report_clocks -file [file join $out clocks.txt]] \
            [list check_timing -verbose -file [file join $out check_timing.txt]] \
            [list report_cdc -details -file [file join $out cdc.txt]] \
            [list report_drc -file [file join $out drc.txt]] \
            [list report_io -file [file join $out io.txt]] \
            [list report_exceptions -coverage -file [file join $out exceptions.txt]]]
        if {$stage eq {impl}} {lappend commands [list report_route_status -file [file join $out route_status.txt]]}
        set h [open [file join $out export_status.txt] w]
        set errors 0
        foreach command $commands {
            if {[catch {{*}$command} message]} {
                incr errors;puts $h "FAILED $command\n$message"
            } else {puts $h "SAVED [lindex $command 0]"}
        }
        close $h
        puts "MIGRATION_REPORTS_SAVED $out export_errors=$errors"
        # 违例报告同样需要保存。只导出事实，不据某个WNS自动进入下一阶段。
    }
}
