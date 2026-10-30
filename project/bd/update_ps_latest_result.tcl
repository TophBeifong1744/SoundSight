# 在用户已打开的仓库外3D工程副本使用；只替换两份内部RTL，不重设BD/IP/时钟/引脚。
# 运行后仍由用户点击综合、实现和生成位流；本脚本不创建副本或启动这些运行。
namespace eval ss_latest_result_update {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc one {items label} {
        if {[llength $items]!=1} {error "STOP: expected one $label, got [llength $items]"}
        return [lindex $items 0]
    }
    proc inside {path base} {
        set p [file split [file normalize $path]];set b [file split [file normalize $base]]
        return [expr {[llength $p]>[llength $b] &&
            [string equal -nocase [lrange $p 0 [expr {[llength $b]-1}]] $b]}]
    }
    proc bytes {path} {set h [open $path rb];try {return [read $h]} finally {close $h}}
    proc refs {name} {
        set result {}
        foreach object [get_files -quiet -of_objects [get_filesets sources_1]] {
            if {[string equal -nocase [file tail [get_property NAME $object]] $name]} {lappend result $object}
        }
        return $result
    }
    proc run {} {
        variable root
        set project [one [get_projects -quiet] {open project}]
        set dir [file normalize [get_property DIRECTORY $project]]
        set name [get_property NAME $project]
        if {[inside $dir $root] || [string equal -nocase $dir $root] || ![regexp -nocase {3d} $name]} {
            error {STOP: open your own external 3D project COPY; no copy is created here}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: expected xc7z020clg400-2}}
        foreach run [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {error "STOP: active run $run"}
        }
        if {[current_bd_design -quiet] eq {}} {open_bd_design [one [get_files -quiet *.bd] BD]}
        current_bd_instance /
        set bdname [current_bd_design]
        set bdobj [one [get_files -quiet */${bdname}.bd] BD]
        set bdpath [file normalize [get_property NAME $bdobj]]
        if {![inside $bdpath $dir]} {error {STOP: BD is outside this project copy}}
        set link [one [get_bd_cells -quiet ps_link] ps_link]
        if {[get_property VLNV $link] ne {xilinx.com:module_ref:bd_ps_link:1.0}} {error {STOP: unexpected ps_link}}
        foreach {key value} {AUDIO_ENABLE 1 DUAL_AXIS_ENABLE 1 LEVEL_ENABLE 1 CLK_FREQ_HZ 61440000} {
            if {[lsearch -exact [list_property $link] CONFIG.$key]<0 || [get_property CONFIG.$key $link]!=$value} {
                error "STOP: expected current 3D/PCM CONFIG.$key=$value"
            }
        }
        # 先核两份唯一登记源与目标目录，再写备份；不替换其余用户源码/约束。
        set plan {}
        foreach filename {ss_snapshot_queue.sv ss_ps_control_regs.sv} {
            set object [one [refs $filename] $filename]
            set target [file normalize [get_property NAME $object]]
            set source [file join $root project rtl $filename]
            if {![inside $target $dir]} {error "STOP: source not copied into this project: $target"}
            if {![file isfile $target] || ![file isfile $source]} {error "STOP: missing source $filename"}
            lappend plan [list $filename $source $target]
        }
        set backup [file join $dir handoff before_latest_result_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup;save_bd_design
        file copy $bdpath [file join $backup before.bd]
        file copy [file join $dir ${name}.xpr] [file join $backup before.xpr]
        set h [open [file join $backup registered_sources.txt] w]
        try {
            foreach row $plan {
                lassign $row filename source target
                file copy $target [file join $backup $filename]
                puts $h "$filename\t$target"
            }
        } finally {close $h}
        puts "LATEST_RESULT_BACKUP=$backup"
        foreach row $plan {
            lassign $row filename source target
            file copy -force $source $target
            if {[bytes $source] ne [bytes $target]} {error "STOP: copy mismatch $filename"}
            puts "LATEST_RESULT_COPIED=$target"
        }
        update_compile_order -fileset sources_1
        # 只刷新现有ps_link的内部依赖；不改变模块端口、参数、连线或地址段。
        set ip [one [get_ips -all -filter {IPDEF == xilinx.com:module_ref:bd_ps_link:1.0} "${bdname}_*"] ps_link-module-reference]
        update_module_reference -verbose $ip
        # 模块刷新后再核一次，不能把丢失参数的工程当作LAT1候选交付。
        set link [one [get_bd_cells -quiet ps_link] refreshed-ps_link]
        foreach {key value} {AUDIO_ENABLE 1 DUAL_AXIS_ENABLE 1 LEVEL_ENABLE 1 CLK_FREQ_HZ 61440000} {
            if {[lsearch -exact [list_property $link] CONFIG.$key]<0 || [get_property CONFIG.$key $link]!=$value} {
                error "STOP: module refresh changed CONFIG.$key; preserve backup $backup"
            }
        }
        validate_bd_design;save_bd_design
        generate_target all [list $bdobj]
        update_compile_order -fileset sources_1
        puts {LATEST_RESULT_PREPARED: LAT1 at 0x98; READY replacement enabled during normal real capture}
        puts {LOCKED_FRAME_PRESERVED; STOP_FAULT_TAIL_PRESERVED; PINS_T15_W16_UNCHANGED}
        puts {NEXT: run synthesis, implementation and bitstream generation manually}
        puts {NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED}
    }
}
if {![info exists ::ss_latest_result_update::library_only] || !$::ss_latest_result_update::library_only} {ss_latest_result_update::run}
