# 在用户自己的PL+PS工程内运行：先更新本批RTL并在BD刷新compute/ps_link模块引用。
# 只设置参数、连接音量元数据并验证/保存BD；不生成IP、不综合、不实现、不下载。
namespace eval ss_ps_level {
    proc one {objects label} {
        if {[llength $objects] != 1} {error "Expected one $label; found $objects"}
        return [lindex $objects 0]
    }
    proc apply {} {
        set project [one [get_projects -quiet] project]
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {Wrong part}}
        if {[current_bd_design -quiet] eq {}} {error {Open the PL+PS BD first}}
        foreach run [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {
                error "Run $run is active; do not replace sources or change BD"
            }
        }
        current_bd_instance /
        if {[llength [get_bd_cells -quiet link]]} {error {STM32 link still present; select the separate PL+PS design}}
        foreach {name module} {compute bd_clean_compute ps_link bd_ps_link} {
            set c [one [get_bd_cells -quiet $name] $name]
            if {[get_property VLNV $c] ne "xilinx.com:module_ref:${module}:1.0"} {error "Unexpected module: $name"}
            if {[lsearch -exact [list_property $c] CONFIG.LEVEL_ENABLE] < 0} {
                error "Refresh module reference $name after updating RTL"
            }
        }
        # Check all new nets before any modification; never merge existing nets.
        set connections {}
        foreach p {feature_level feature_level_valid} {
            set a [one [get_bd_pins -quiet compute/$p] compute/$p]
            set b [one [get_bd_pins -quiet ps_link/$p] ps_link/$p]
            set nets [lsort -unique [concat [get_bd_nets -quiet -of_objects $a] [get_bd_nets -quiet -of_objects $b]]]
            if {[llength $nets] > 1} {error "Conflicting nets on $p; preserve and inspect"}
            if {[llength $nets]} {
                set drivers [get_bd_pins -quiet -of_objects [lindex $nets 0] -filter {DIR == O}]
                if {[llength $drivers] && $drivers ne $a} {error "Unexpected existing driver on $p"}
            }
            lappend connections [list $a $b $nets]
        }
        set_property CONFIG.LEVEL_ENABLE 1 [get_bd_cells compute]
        set_property CONFIG.LEVEL_ENABLE 1 [get_bd_cells ps_link]
        foreach entry $connections {
            lassign $entry a b nets
            if {![llength $nets]} {
                connect_bd_net $a $b
            } else {
                foreach p [list $a $b] {
                    if {![llength [get_bd_nets -quiet -of_objects $p]]} {connect_bd_net -net [lindex $nets 0] $p}
                }
            }
        }
        validate_bd_design
        save_bd_design
        puts {PS_LEVEL_BD_SAVED: ABI 0x00010001; no synthesis/implementation/programming launched}
    }
}
ss_ps_level::apply
