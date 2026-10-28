# 在已打开的 PL+PS 工程中 source 本文件。复制源码、刷新 BD 并生成输出文件。
# 不启动综合/实现/下载，不改 DDR/MIO、时钟、复位、约束内容或执行器配置。
namespace eval ss_volume_update {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    variable names {ss_preprocess.sv ss_fft_frontend.sv f1a_frame_store.sv
        ss_pair_engine.sv ss_clean_compute.sv ss_dual_compute.sv bd_clean_compute.v
        ss_ps_control_regs.sv ss_ps_link.sv bd_ps_link.v ss_manual_servo.sv ss_snapshot_queue.sv}
    proc one {objects label} {
        if {[llength $objects] != 1} {error "STOP: expected one $label; found $objects"}
        return [lindex $objects 0]
    }
    proc inside {path base} {
        set p [file split [file normalize $path]]
        set b [file split [file normalize $base]]
        return [expr {[llength $p]>[llength $b] &&
            [string equal -nocase [lrange $p 0 [expr {[llength $b]-1}]] $b]}]
    }
    proc refs {name} {
        set result {}
        foreach f [get_files -quiet -of_objects [get_filesets sources_1]] {
            if {[string equal -nocase [file tail [get_property NAME $f]] $name]} {lappend result $f}
        }
        return $result
    }
    proc bytes {path} {
        set f [open $path rb]
        try {return [read $f]} finally {close $f}
    }
    proc localize_constraints {backup dir} {
        # Copy the user's actual constraints verbatim, not repository defaults.
        set plan {}
        foreach name {board_pins.xdc interface_timing.xdc} {
            set matches {}
            foreach f [get_files -quiet -of_objects [get_filesets constrs_1]] {
                if {[string equal -nocase [file tail [get_property NAME $f]] $name]} {lappend matches $f}
            }
            set f [one $matches "constraint $name"]
            set old [file normalize [get_property NAME $f]]
            if {![file isfile $old]} {error "STOP: missing actual constraint $old"}
            set props {}
            foreach prop {FILE_TYPE USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION PROCESSING_ORDER IS_ENABLED} {
                if {[lsearch -exact [list_property $f] $prop]>=0} {
                    lappend props $prop [get_property $prop $f]
                }
            }
            lappend plan [list $name $f $old $props]
        }
        foreach entry $plan {
            lassign $entry name f old props
            if {[inside $old $dir]} {continue}
            set target [file join $dir ps_constraints $name]
            file mkdir [file dirname $target]
            file copy $old [file join $backup constraint_$name]
            if {[file exists $target]} {file copy $target [file join $backup previous_constraint_$name]}
            file copy -force $old $target
            if {[bytes $old] ne [bytes $target]} {error "STOP: constraint copy differs: $target"}
            remove_files [list $f]
            add_files -norecurse -fileset constrs_1 [list $target]
            if {[llength $props]} {set_property -dict $props [get_files -quiet [list $target]]}
            puts "PS_VOLUME_CONSTRAINT_COPIED=$target"
        }
    }
    proc apply_level {} {
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
    proc run {} {
        variable root; variable names
        set project [one [get_projects -quiet] project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {[string equal -nocase $dir $root] || [inside $dir $root]} {
            error {STOP: open your external working project, not the repository project}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach r [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $r]]} {
                error "STOP: active run $r; wait for it to finish"
            }
        }
        set bd [current_bd_design -quiet]
        if {$bd eq {}} {
            open_bd_design [one [get_files -quiet *.bd] {BD to open}]
            set bd [current_bd_design]
        }
        current_bd_instance /
        if {[llength [get_bd_cells -quiet link]]} {error {STOP: STM32 link present; wrong target}}
        foreach {cell module} {compute bd_clean_compute ps_link bd_ps_link} {
            set c [one [get_bd_cells -quiet $cell] $cell]
            if {[get_property VLNV $c] ne "xilinx.com:module_ref:${module}:1.0"} {
                error "STOP: unexpected $cell module"
            }
        }
        set bdobj [one [get_files -quiet */${bd}.bd] {current BD source}]
        set bdpath [file normalize [get_property NAME $bdobj]]
        if {![inside $bdpath $dir]} {error {STOP: BD must be copied inside the working project}}
        set fs [get_filesets sources_1]
        # No boundary port changes: keep the existing wrapper and its top setting.
        if {[get_property TOP $fs] ne "${bd}_wrapper"} {error {STOP: unexpected top; preserve it for inspection}}
        set xpr [file join $dir [get_property NAME $project].xpr]
        if {![file isfile $xpr]} {error {STOP: project file missing}}

        # Resolve every source before changing anything. Existing local imports
        # keep their location; external references are relocated into the project.
        set plan {}
        foreach name $names {
            set src [file join $root project rtl $name]
            if {![file isfile $src]} {error "STOP: missing package source $src"}
            set matches [refs $name]
            # PS registers now instantiate this controller even when motion is disabled.
            if {$name eq {ss_manual_servo.sv} && ![llength $matches]} {
                set target [file join $dir ps_volume_sources $name]
                if {[file exists $target]} {error "STOP: unregistered source exists: $target"}
                lappend plan [list $src {} $target {} {}]
                continue
            }
            set f [one $matches "registered source $name"]
            set old [file normalize [get_property NAME $f]]
            if {![file isfile $old]} {error "STOP: missing registered file $old"}
            set target $old
            if {![inside $old $dir]} {set target [file join $dir ps_volume_sources $name]}
            if {![inside $target $dir] || [inside $target $root]} {error "STOP: invalid copy target $target"}
            set props {}
            foreach prop {FILE_TYPE LIBRARY USED_IN_SYNTHESIS USED_IN_SIMULATION} {
                lappend props $prop [get_property $prop $f]
            }
            lappend plan [list $src $old $target $f $props]
        }

        set backup [file join $dir handoff before_ps_volume_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        save_bd_design
        file copy $bdpath [file join $backup before.bd]
        file copy $xpr [file join $backup before.xpr]
        set receipt [open [file join $backup sources.tsv] {WRONLY CREAT EXCL}]
        try {
            puts $receipt "package_source\tprevious_registration\tinstalled_path"
            foreach entry $plan {
                lassign $entry src old target f props
                set name [file tail $src]
                if {$old ne {}} {file copy $old [file join $backup $name]}
                if {![string equal -nocase $old $target] && [file exists $target]} {
                    file copy $target [file join $backup previous_target_$name]
                }
                puts $receipt "$src\t$old\t$target"
            }
        } finally {close $receipt}
        puts "PS_VOLUME_BACKUP=$backup"
        # Remove/re-add the same registered source to force rereading the RTL.
        # Tcl list arguments preserve paths containing spaces.
        foreach entry $plan {
            lassign $entry src old target f props
            file mkdir [file dirname $target]
            file copy -force $src $target
            if {[bytes $src] ne [bytes $target]} {error "STOP: copy differs: $target"}
            if {$f ne {}} {remove_files [list $f]}
            add_files -norecurse -fileset sources_1 [list $target]
            set installed [one [refs [file tail $src]] {installed source}]
            if {[llength $props]} {set_property -dict $props $installed}
            puts "PS_VOLUME_COPIED=$target"
        }
        localize_constraints $backup $dir
        finish
    }
    # Resume after source copying without overwriting the original backup.
    proc finish {} {
        variable root; variable names
        set project [one [get_projects -quiet] project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach r [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $r]]} {
                error "STOP: active run $r"
            }
        }
        set bd [current_bd_design -quiet]
        if {$bd eq {}} {error {STOP: open the PL+PS block design first}}
        current_bd_instance /
        if {[llength [get_bd_cells -quiet link]]} {error {STOP: wrong STM32 target}}
        set bdobj [one [get_files -quiet */${bd}.bd] {current BD source}]
        if {![inside [get_property NAME $bdobj] $dir] || [inside $dir $root] ||
            [string equal -nocase $dir $root]} {error {STOP: expected external working project}}
        # Confirm copied files before continuing; resume never rewrites sources.
        foreach name $names {
            set actual [get_property NAME [one [refs $name] {copied source}]]
            if {![inside $actual $dir] || [bytes $actual] ne [bytes [file join $root project rtl $name]]} {
                error "STOP: source not copied/current: $actual"
            }
        }
        # A GUI session can retain old module metadata after an on-disk update.
        # Reopen the saved project to reread the actual local RTL and BD together.
        set xpr [file join $dir [get_property NAME $project].xpr]
        # Materialize a filename: Vivado BD object handles become invalid when
        # the project closes, even if kept in a Tcl variable.
        set bdpath [file normalize [get_property NAME $bdobj]]
        save_bd_design
        close_project
        open_project $xpr
        set bdobj [one [get_files -quiet [list $bdpath]] {reopened BD source}]
        open_bd_design $bdobj
        current_bd_instance /
        update_compile_order -fileset sources_1
        # Reopening rereads parameters; explicit module refresh updates the BD
        # boundary pins. Both are required before checking/connecting new ports.
        set bdname [file rootname [file tail $bdpath]]
        foreach module {bd_clean_compute bd_ps_link} {
            set ip [one [get_ips -all -filter "IPDEF == xilinx.com:module_ref:${module}:1.0" "${bdname}_*"] "IP for $module"]
            puts "PS_VOLUME_REFRESH_IP=$ip"
            update_module_reference -verbose $ip
        }
        apply_level
        # Global BD generation creates HDL/output products without launching OOC
        # synthesis here. The user's Generate Bitstream runs the physical flow.
        set_property synth_checkpoint_mode None $bdobj
        generate_target all [list $bdobj]
        update_compile_order -fileset sources_1
        foreach name $names {
            set actual [get_property NAME [one [refs $name] {final registration}]]
            if {![inside $actual $dir] || [bytes $actual] ne [bytes [file join $root project rtl $name]]} {
                error "STOP: final source registration/copy mismatch: $name"
            }
        }
        puts {PS_VOLUME_READY_FOR_GENERATE_BITSTREAM}
        puts {Copied 11 RTL files into working project; BD validated; output products generated.}
        puts {No synthesis, implementation, bitstream generation or programming launched by this script.}
    }
}
if {[info exists ::ss_volume_update::library_only] && $::ss_volume_update::library_only} {
    # Other preparation recipes may reuse path/copy helpers without updating a project.
} elseif {[info exists ::ss_volume_update::resume_once] && $::ss_volume_update::resume_once} {
    ss_volume_update::finish
} else {
    ss_volume_update::run
}
