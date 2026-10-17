# 由新项目outputs入口调用：核真实注册路径、当前顶层、器件和run状态。
# 只保存准备阶段事实，不执行综合/实现/下载，也不把Validate当作STA。
set audit_root [file normalize [file join [file dirname [info script]] ..]]
set audit_out [file join [get_property DIRECTORY [current_project]] reports preparation]
file mkdir $audit_out
set audit_handle [open [file join $audit_out native-project.txt] w]
puts $audit_handle "tool=[version -short]"
puts $audit_handle "project=[get_property NAME [current_project]]"
puts $audit_handle "part=[get_property PART [current_project]]"
puts $audit_handle "top=[get_property TOP [get_filesets sources_1]]"
set audit_bad 0
foreach fileset {sources_1 constrs_1} {
    foreach object [get_files -of_objects [get_filesets $fileset]] {
        set source [file normalize [get_property NAME $object]]
        puts $audit_handle "$fileset\t$source"
        if {![file exists $source] || ![string equal -nocase [string range $source 0 [string length $audit_root]] ${audit_root}/]} {
            incr audit_bad
            puts $audit_handle "ERROR missing/outside-new-root=$source"
        }
    }
}
foreach run [get_runs] {
    set status [get_property STATUS $run]
    puts $audit_handle "run=$run status=$status"
    if {$status ne "Not started"} {incr audit_bad;puts $audit_handle "ERROR unexpected run execution=$run"}
}
puts $audit_handle "registered_path_errors=$audit_bad"
close $audit_handle
report_ip_status -file [file join $audit_out ip-status.txt]
set audit_bd [get_files -quiet *.bd]
if {[llength $audit_bd] != 1} {error {Expected exactly one SoundSight BD}}
open_bd_design $audit_bd
write_bd_tcl -force [file join $audit_out actual-bd.tcl]
if {$audit_bad} {error "Native project audit failed; preserve $audit_out"}
puts "SOUNDSIGHT_NATIVE_AUDIT_PASS $audit_out"
