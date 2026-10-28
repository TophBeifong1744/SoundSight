# 用户先自行复制外部PCM工程并命名为包含3D或DualAxis的新工程，再在副本source本文件。
# 本脚本只复制源码、更新BD引用和生成输出；不创建副本、不启动综合/实现/下载。
namespace eval ss_dual_axis_update {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc one {items label} {
        if {[llength $items]!=1} {error "STOP: expected one $label, got [llength $items]"}
        return [lindex $items 0]
    }
    proc inside {path base} {
        set path [string tolower [file normalize $path]]
        set base [string trimright [string tolower [file normalize $base]] /]
        return [string equal -length [string length "$base/"] "$base/" $path]
    }
    proc bytes {path} {set h [open $path rb];set value [read $h];close $h;return $value}
    proc generated {object} {
        foreach prop {IS_GENERATED PARENT_COMPOSITE_FILE} {
            if {[lsearch -exact [list_property $object] $prop]<0} {continue}
            set value [get_property $prop $object]
            if {$prop eq {IS_GENERATED} && $value} {return 1}
            if {$prop eq {PARENT_COMPOSITE_FILE} && $value ne {}} {return 1}
        }
        return 0
    }
    proc run {} {
        variable root
        set project [one [get_projects -quiet] project]
        set name [get_property NAME $project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {[inside $dir $root] || [string equal -nocase $dir $root] ||
            ![regexp -nocase {3d|dualaxis} $name]} {
            error {STOP: open your external project COPY named e.g. SoundSight_PS_3D; no copy is created here}
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
        set bdname [file rootname [file tail $bdpath]]
        if {![inside $bdpath $dir]} {error {STOP: BD references the original project, copy it into the new project first}}
        if {[llength [get_bd_cells -quiet link]]} {error {STOP: STM32 link is not a PS target}}
        set link [one [get_bd_cells -quiet ps_link] ps_link]
        if {[get_property VLNV $link] ne {xilinx.com:module_ref:bd_ps_link:1.0}} {error {STOP: unexpected ps_link module}}
        foreach {key value} {AUDIO_ENABLE 1 LEVEL_ENABLE 1 ACTUATOR_BOUND 1 CLK_FREQ_HZ 61440000 SERVO_MAX 360} {
            if {[lsearch -exact [list_property $link] CONFIG.$key]<0 || [get_property CONFIG.$key $link]!=$value} {
                error "STOP: expected current PCM/Servo base CONFIG.$key=$value"
            }
        }
        if {[get_property TOP [get_filesets sources_1]] ne "${bdname}_wrapper"} {error {STOP: unexpected physical wrapper}}
        # 仅替换这批RTL；其他手写RTL/初始化文件按用户当前内容复制，厂商IP仍由其XCI/BD管理。
        set replacement {bd_ps_link.v ss_ps_link.sv ss_ps_control_regs.sv ss_dual_axis_control.sv motor_drive.v i17_turntable_pwm_guard.sv}
        set source_plan {};set seen {}
        foreach object [get_files -quiet -of_objects [get_filesets sources_1]] {
            if {[generated $object]} {continue}
            set old [file normalize [get_property NAME $object]]
            set tail [file tail $old];set extension [string tolower [file extension $old]]
            if {$extension in {.bd .xci} && ![inside $old $dir]} {error "STOP: IP/BD outside your copy: $old"}
            if {$tail eq "${bdname}_wrapper.v" || $extension ni {.v .sv .vh .svh .mem .coe}} {continue}
            if {[lsearch -exact $seen $tail]>=0} {error "STOP: duplicate source basename $tail"}
            lappend seen $tail
            if {![file isfile $old]} {error "STOP: missing registered source $old"}
            set src $old
            if {[lsearch -exact $replacement $tail]>=0} {set src [file join $root project rtl $tail]}
            if {![file isfile $src]} {error "STOP: missing replacement $src"}
            set props {}
            foreach prop {FILE_TYPE LIBRARY USED_IN_SYNTHESIS USED_IN_SIMULATION} {lappend props $prop [get_property $prop $object]}
            lappend source_plan [list $object $old $src [file join $dir dual_axis_sources $tail] $props]
        }
        foreach tail $replacement {
            if {[lsearch -exact $seen $tail]>=0} {continue}
            if {$tail ne {ss_dual_axis_control.sv}} {error "STOP: missing registered base source $tail"}
            set src [file join $root project rtl $tail]
            if {![file isfile $src]} {error "STOP: missing $src"}
            lappend source_plan [list {} {} $src [file join $dir dual_axis_sources $tail] {}]
        }
        # 垂直路径预算只随双轴副本登记；旧单轴约束文件保持原文。
        set timing_src [file join $root project sdc ps dual_axis_output_timing.xdc]
        set timing_target [file join $dir dual_axis_constraints dual_axis_output_timing.xdc]
        if {![file isfile $timing_src]} {error "STOP: missing dual-axis timing constraint $timing_src"}
        set timing_seen 0
        set constraints {};set counts [dict create servo_pwm 0 servo_vertical_pwm 0];set index 0
        foreach object [get_files -quiet -of_objects [get_filesets constrs_1]] {
            if {[generated $object]} {continue}
            set old [file normalize [get_property NAME $object]]
            if {![file isfile $old]} {error "STOP: missing constraint $old"}
            set content [bytes $old]
            foreach line [split $content \n] {
                if {[regexp {^\s*#} $line]} {continue}
                foreach {port pin} {servo_pwm T15 servo_vertical_pwm W15} {
                    set pattern [format {set_property\s+PACKAGE_PIN\s+\{?%s\}?\s+\[get_ports\s+\{?%s\}?\]} $pin $port]
                    if {[regexp $pattern $line]} {dict incr counts $port}
                    if {[regexp [format {PACKAGE_PIN\s+\{?%s\}?\s} $pin] $line] && ![regexp $pattern $line]} {
                        error "STOP: possible pin collision: $line"
                    }
                    if {[regexp [format {PACKAGE_PIN.*get_ports\s+\{?%s\}?\]} $port] $line] && ![regexp $pattern $line]} {
                        error "STOP: unexpected servo pin: $line"
                    }
                }
            }
            set props {}
            foreach prop {FILE_TYPE USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION PROCESSING_ORDER IS_ENABLED} {
                if {[lsearch -exact [list_property $object] $prop]>=0} {lappend props $prop [get_property $prop $object]}
            }
            if {[file tail $old] eq {dual_axis_output_timing.xdc}} {
                if {[incr timing_seen]!=1} {error {STOP: duplicate dual-axis timing constraints}}
                set props {FILE_TYPE XDC USED_IN_SYNTHESIS 1 USED_IN_IMPLEMENTATION 1 PROCESSING_ORDER LATE IS_ENABLED 1}
                lappend constraints [list $object $old $timing_src $timing_target $props]
            } else {
                lappend constraints [list $object $old $old [file join $dir dual_axis_constraints [format %02d [incr index]] [file tail $old]] $props]
            }
        }
        if {!$timing_seen} {
            if {[file exists $timing_target] && [bytes $timing_target] ne [bytes $timing_src]} {
                error "STOP: unregistered timing file already exists: $timing_target"
            }
            lappend constraints [list {} {} $timing_src $timing_target {FILE_TYPE XDC USED_IN_SYNTHESIS 1 USED_IN_IMPLEMENTATION 1 PROCESSING_ORDER LATE IS_ENABLED 1}]
        }
        foreach port {servo_pwm servo_vertical_pwm} {
            if {[dict get $counts $port]!=1} {error "STOP: expected one existing pin constraint for $port"}
            set ext [one [get_bd_ports -quiet $port] $port]
            set pin [one [get_bd_pins -quiet ps_link/$port] ps_link/$port]
            set net [one [get_bd_nets -quiet -of_objects $ext] $port-net]
            if {[get_bd_pins -of_objects $net] ne $pin} {error "STOP: unexpected $port net driver"}
        }
        set backup [file join $dir handoff before_dual_axis_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup;save_bd_design
        set xpr [file join $dir ${name}.xpr]
        file copy $xpr [file join $backup before.xpr];file copy $bdpath [file join $backup before.bd]
        foreach row $source_plan {lassign $row object old src target props;if {$old ne {}} {file copy $old [file join $backup [file tail $old]]}}
        set index 0
        foreach row $constraints {lassign $row object old src target props;if {$old ne {}} {file copy $old [file join $backup xdc_[incr index]_[file tail $old]]}}
        puts "DUAL_AXIS_BACKUP=$backup"
        foreach row $source_plan {
            lassign $row object old src target props
            file mkdir [file dirname $target]
            if {![string equal -nocase $src $target]} {file copy -force $src $target}
            if {[bytes $src] ne [bytes $target]} {error "STOP: source copy failed $target"}
            if {$object ne {}} {remove_files [list $object]}
            add_files -norecurse -fileset sources_1 [list $target]
            if {[llength $props]} {set_property -dict $props [get_files -quiet [list $target]]}
            puts "DUAL_AXIS_COPIED=$target"
        }
        foreach row $constraints {
            lassign $row object old src target props;file mkdir [file dirname $target]
            if {![string equal -nocase $src $target]} {file copy -force $src $target}
            if {[bytes $src] ne [bytes $target]} {error "STOP: constraint copy failed $target"}
            if {$object ne {}} {remove_files [list $object]}
            add_files -norecurse -fileset constrs_1 [list $target]
            if {[llength $props]} {set_property -dict $props [get_files -quiet [list $target]]}
        }
        # 重新打开仅用于刷新模块缓存；不打开第二个工程，不启动任何运行。
        save_bd_design;close_project;open_project $xpr
        open_bd_design [get_files -quiet [list $bdpath]];current_bd_instance /
        update_compile_order -fileset sources_1
        set module_ip [one [get_ips -all -filter {IPDEF == xilinx.com:module_ref:bd_ps_link:1.0} "${bdname}_*"] ps_link-module-reference]
        update_module_reference -verbose $module_ip
        set link [one [get_bd_cells -quiet ps_link] ps_link]
        if {[lsearch -exact [list_property $link] CONFIG.DUAL_AXIS_ENABLE]<0} {error {STOP: module refresh did not expose DUAL_AXIS_ENABLE}}
        set_property CONFIG.DUAL_AXIS_ENABLE 1 $link
        validate_bd_design;save_bd_design
        set bdobj [one [get_files -quiet [list $bdpath]] reopened-BD]
        # 输出生成只导出HDL/IP产物；全局综合仍留给用户点击。
        set_property synth_checkpoint_mode None $bdobj
        generate_target all [list $bdobj]
        set wrappers [make_wrapper -files [list $bdobj] -top]
        set oldwrappers [get_files -quiet */${bdname}_wrapper.v]
        if {[llength $oldwrappers]} {remove_files $oldwrappers}
        add_files -norecurse -fileset sources_1 $wrappers
        set_property TOP ${bdname}_wrapper [get_filesets sources_1]
        update_compile_order -fileset sources_1
        puts {DUAL_AXIS_PREPARED: H=T15 0..360deg V=W15 0..220deg PWM=20ms/500..2500us}
        puts {PYNQ_EXPLICIT_ARM_COMMIT_REQUIRED; BOOT_AND_MEASURE_ONLY_OUTPUTS_OFF}
        puts {NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED}
    }
}
if {![info exists ::ss_dual_axis_update::library_only] || !$::ss_dual_axis_update::library_only} {ss_dual_axis_update::run}
