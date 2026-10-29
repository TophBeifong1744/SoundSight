# 供批处理入口使用；失败必须返回真实非零退出码。
if {[catch {
    if {[llength $argv] != 1} {error {Expected one output directory argument}}
    source [file join [file dirname [info script]] ../project/script/rebuild_ps_3d.tcl]
    ss_rebuild::create [lindex $argv 0]
    close_project
} message options]} {
    puts stderr "PS_3D_REBUILD_FAILED: $message"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
exit 0
