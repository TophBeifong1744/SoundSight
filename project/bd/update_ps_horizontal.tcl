# Source in the user's EXTERNAL COPY named *_Servo. Preparation only.
# No synthesis, implementation, bit generation, programming, reset or motion.
namespace eval ss_volume_update {variable library_only 1}
try {
    source [file join [file dirname [info script]] update_ps_volume.tcl]
} finally {set ::ss_volume_update::library_only 0}
namespace eval ss_horizontal {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc one {x label} {return [ss_volume_update::one $x $label]}
    proc inside {p b} {return [ss_volume_update::inside $p $b]}
    proc bytes {p} {return [ss_volume_update::bytes $p]}
    proc generated {f} {
        # get_files also walks BD/IP generated children. They remain owned by
        # their XCI/BD and must never be copied/re-registered as user RTL/XDC.
        foreach p {IS_GENERATED PARENT_COMPOSITE_FILE} {
            if {[lsearch -exact [list_property $f] $p]<0} {continue}
            set v [get_property $p $f]
            if {$p eq {IS_GENERATED} && $v} {return 1}
            if {$p eq {PARENT_COMPOSITE_FILE} && $v ne {}} {return 1}
        }
        return 0
    }
    proc run {} {
        variable root
        set project [one [get_projects -quiet] project]
        set name [get_property NAME $project]
        set dir [file normalize [get_property DIRECTORY $project]]
        # An explicit new project name protects the existing Volume baseline.
        if {![string match -nocase *_Servo $name] || [inside $dir $root] || $dir eq $root} {
            error {STOP: open an external project COPY named *_Servo, e.g. SoundSight_PS_Servo}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach r [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $r]]} {error "STOP: active run $r"}
        }
        if {[current_bd_design -quiet] eq {}} {open_bd_design [one [get_files -quiet *.bd] BD]}
        current_bd_instance /
        set bd [current_bd_design]
        set bdobj [one [get_files -quiet */${bd}.bd] BD]
        set bdpath [file normalize [get_property NAME $bdobj]]
        # Keep a plain filename-derived string, not a Vivado design handle that
        # becomes invalid after close_project during the module-cache refresh.
        set bd [file rootname [file tail $bdpath]]
        if {![inside $bdpath $dir]} {error {STOP: BD still references the original project; copy it first}}
        if {[llength [get_bd_cells -quiet link]]} {error {STOP: STM32 link present}}
        foreach {cell module} {compute bd_clean_compute ps_link bd_ps_link} {
            set c [one [get_bd_cells -quiet $cell] $cell]
            if {[get_property VLNV $c] ne "xilinx.com:module_ref:${module}:1.0" ||
                [get_property CONFIG.LEVEL_ENABLE $c] != 1} {error "STOP: expected current volume $cell"}
        }
        if {[get_property CONFIG.CLK_FREQ_HZ [get_bd_cells ps_link]] != 61440000} {error {STOP: unexpected control clock}}
        set pwm [one [get_bd_ports -quiet servo_pwm] servo_pwm]
        set net [one [get_bd_nets -quiet -of_objects $pwm] servo_pwm_net]
        if {[lsort [get_bd_pins -of_objects $net]] ne [get_bd_pins ps_link/servo_pwm]} {error {STOP: unexpected horizontal PWM wiring}}
        if {[get_property TOP [get_filesets sources_1]] ne "${bd}_wrapper"} {error {STOP: unexpected top wrapper}}

        set replace {bd_ps_link.v ss_ps_link.sv ss_ps_control_regs.sv ss_actuator_control.sv motor_drive.v i17_turntable_pwm_guard.sv ss_manual_servo.sv}
        # Preflight every affected input before replacing anything. Localize all
        # hand-written RTL/memory, keeping other user source contents unchanged.
        set plan {}; set seen {}
        foreach f [get_files -quiet -of_objects [get_filesets sources_1]] {
            if {[generated $f]} {continue}
            set old [file normalize [get_property NAME $f]]
            set tail [file tail $old]
            if {[string tolower [file extension $old]] in {.xci .bd} && ![inside $old $dir]} {
                error "STOP: IP/BD still references another project; copy it into your project first: $old"
            }
            if {$tail eq "${bd}_wrapper.v"} {continue}
            if {[string tolower [file extension $old]] ni {.sv .v .mem}} {continue}
            if {![file isfile $old]} {error "STOP: missing input $old"}
            if {[lsearch -exact $seen $tail]>=0} {error "STOP: duplicate source basename $tail"}
            lappend seen $tail
            set src $old
            if {[lsearch -exact $replace $tail]>=0} {set src [file join $root project rtl $tail]}
            if {![file isfile $src]} {error "STOP: missing package input $src"}
            set props {}
            foreach p {FILE_TYPE LIBRARY USED_IN_SYNTHESIS USED_IN_SIMULATION} {lappend props $p [get_property $p $f]}
            lappend plan [list $f $old $src [file join $dir horizontal_sources $tail] $props]
        }
        foreach n $replace {if {$n ne {ss_manual_servo.sv} && [lsearch -exact $seen $n]<0} {error "STOP: missing registered $n"}}
        if {[lsearch -exact $seen ss_manual_servo.sv]<0} {
            set src [file join $root project rtl ss_manual_servo.sv]
            if {![file isfile $src]} {error {STOP: missing manual source}}
            lappend plan [list {} {} $src [file join $dir horizontal_sources ss_manual_servo.sv] {}]
        }
        set xdcplan {}; set index 0; set board_count 0
        foreach f [get_files -quiet -of_objects [get_filesets constrs_1]] {
            if {[generated $f]} {continue}
            set old [file normalize [get_property NAME $f]]
            if {![file isfile $old]} {error "STOP: missing constraint $old"}
            set content [bytes $old]
            if {[file tail $old] eq {board_pins.xdc}} {
                incr board_count
                set pattern {set_property\s+PACKAGE_PIN\s+(T15|V7)\s+\[get_ports\s+\{?servo_pwm\}?\]}
                if {[regsub -all $pattern $content {set_property PACKAGE_PIN T15 [get_ports servo_pwm]} content]!=1} {
                    error {STOP: expected one known horizontal pin assignment in board_pins.xdc}
                }
            } elseif {[file tail $old] eq {horizontal_reserved.xdc}} {
                continue
            }
            # Preserve all non-servo constraints. Detect pin collisions rather
            # than silently taking a microphone/LCD/other signal's pin.
            foreach line [split $content \n] {
                if {[regexp {^\s*#} $line]} {continue}
                if {[regexp {PACKAGE_PIN\s+(T15|W16)\M} $line] &&
                    ![regexp {get_ports\s+\{?servo_pwm\}?\]} $line]} {error "STOP: servo pin collision: $line"}
            }
            set props {}
            foreach p {FILE_TYPE USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION PROCESSING_ORDER IS_ENABLED} {
                if {[lsearch -exact [list_property $f] $p]>=0} {lappend props $p [get_property $p $f]}
            }
            lappend xdcplan [list $f $old [file join $dir horizontal_constraints [format %02d $index] [file tail $old]] $content $props]
            incr index
        }
        if {$board_count!=1} {error {STOP: expected one board_pins.xdc}}
        set backup [file join $dir handoff before_horizontal_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        save_bd_design
        set xpr [file join $dir ${name}.xpr]
        file copy $xpr [file join $backup before.xpr]
        file copy $bdpath [file join $backup before.bd]
        foreach entry $plan {
            lassign $entry f old src target props
            if {$old ne {}} {file copy $old [file join $backup [file tail $old]]}
        }
        set index 0
        foreach entry $xdcplan {
            lassign $entry f old target content props
            file copy $old [file join $backup constraint_[incr index]_[file tail $old]]
        }
        puts "HORIZONTAL_BACKUP=$backup"
        foreach entry $plan {
            lassign $entry f old src target props
            file mkdir [file dirname $target]
            if {![string equal -nocase $src $target]} {file copy -force $src $target}
            if {[bytes $src] ne [bytes $target]} {error "STOP: copy mismatch $target"}
            if {$f ne {}} {remove_files [list $f]}
            add_files -norecurse -fileset sources_1 [list $target]
            if {[llength $props]} {set_property -dict $props [get_files -quiet [list $target]]}
        }
        foreach entry $xdcplan {
            lassign $entry f old target content props
            file mkdir [file dirname $target]
            set h [open $target wb]; puts -nonewline $h $content; close $h
            remove_files [list $f]
            add_files -norecurse -fileset constrs_1 [list $target]
            set_property -dict $props [get_files -quiet [list $target]]
        }
        set reserved [file join $dir horizontal_constraints horizontal_reserved.xdc]
        set oldrefs [get_files -quiet */horizontal_reserved.xdc]
        if {[llength $oldrefs]} {remove_files $oldrefs}
        file copy -force [file join $root project sdc ps horizontal_reserved.xdc] $reserved
        add_files -norecurse -fileset constrs_1 [list $reserved]
        # Reopen to invalidate cached module metadata after copying source.
        save_bd_design; close_project; open_project $xpr
        open_bd_design [get_files -quiet [list $bdpath]]
        current_bd_instance /
        update_compile_order -fileset sources_1
        set ip [one [get_ips -all -filter {IPDEF == xilinx.com:module_ref:bd_ps_link:1.0} "${bd}_*"] ps_link_ip]
        update_module_reference -verbose $ip
        set_property -dict [list CONFIG.ACTUATOR_BOUND 1 CONFIG.SERVO_MAX 360 CONFIG.MECHANICAL_MIN 0 CONFIG.MECHANICAL_MAX 360] [get_bd_cells ps_link]
        set vertical [get_bd_ports -quiet servo_vertical_pwm]
        if {![llength $vertical]} {set vertical [create_bd_port -dir O servo_vertical_pwm]}
        set pin [one [get_bd_pins -quiet ps_link/servo_vertical_pwm] vertical_pin]
        set nets [lsort -unique [concat [get_bd_nets -quiet -of_objects $vertical] [get_bd_nets -quiet -of_objects $pin]]]
        if {[llength $nets]>1} {error {STOP: conflicting vertical nets}}
        if {![llength $nets]} {connect_bd_net $vertical $pin} else {
            if {[get_bd_pins -of_objects [lindex $nets 0]] ne $pin} {error {STOP: conflicting vertical driver}}
        }
        validate_bd_design
        save_bd_design
        set bdobj [get_files -quiet [list $bdpath]]
        set_property synth_checkpoint_mode None $bdobj
        generate_target all [list $bdobj]
        set wrappers [make_wrapper -files [list $bdobj] -top]
        set oldwrappers [ss_volume_update::refs ${bd}_wrapper.v]
        if {[llength $oldwrappers]} {remove_files $oldwrappers}
        add_files -norecurse -fileset sources_1 $wrappers
        set_property TOP ${bd}_wrapper [get_filesets sources_1]
        update_compile_order -fileset sources_1
        puts {HORIZONTAL_PREPARED: T15 horizontal 360deg; W16 vertical reserved LOW; LVCMOS33}
        puts {SOFTWARE_DEFAULT_OFF: mechanical calibration is configured on PYNQ}
        puts {NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED}
    }
}
ss_horizontal::run
