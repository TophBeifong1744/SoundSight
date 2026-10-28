# Source in the already prepared external *_Servo project. Changes XDC only.
# No RTL/BD update, synthesis, implementation, bit generation or hardware action.
namespace eval ss_servo_pins {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc inside {path base} {
        set p [string tolower [file normalize $path]]
        set b [string trimright [string tolower [file normalize $base]] /]
        return [expr {[string first "${b}/" "${p}/"] == 0}]
    }
    proc read_file {path} {
        set h [open $path rb]; try {return [read $h]} finally {close $h}
    }
    proc rewrite {content kind} {
        if {$kind eq {horizontal}} {
            set pattern {set_property\s+PACKAGE_PIN\s+(T15|V7)\s+\[get_ports\s+\{?servo_pwm\}?\]}
            set replacement {set_property PACKAGE_PIN T15 [get_ports servo_pwm]}
        } elseif {$kind eq {vertical}} {
            set pattern {set_property\s+PACKAGE_PIN\s+(W15|U7)\s+\[get_ports\s+\{?servo_vertical_pwm\}?\]}
            set replacement {set_property PACKAGE_PIN W15 [get_ports servo_vertical_pwm]}
        } else {error {STOP: unknown servo constraint kind}}
        # Only count/replace active lines, never commented historical examples.
        set count 0; set lines {}
        foreach line [split $content \n] {
            if {![regexp {^\s*#} $line]} {
                incr count [regsub -all $pattern $line $replacement line]
            }
            lappend lines $line
        }
        if {$count != 1} {error "STOP: expected one known $kind PACKAGE_PIN assignment"}
        return [join $lines \n]
    }
    proc check_collision {content} {
        foreach line [split $content \n] {
            if {[regexp {^\s*#} $line]} {continue}
            foreach {pin port} {T15 servo_pwm W15 servo_vertical_pwm} {
                if {[regexp "PACKAGE_PIN\\s+${pin}\\M" $line] &&
                    ![regexp [format {get_ports\s+\{?%s\}?\]} $port] $line]} {
                    error "STOP: requested servo pin collision: $line"
                }
            }
        }
    }
    proc run {} {
        variable root
        set projects [get_projects -quiet]
        if {[llength $projects]!=1} {error {STOP: open your existing external Servo project}}
        set project [lindex $projects 0]
        set name [get_property NAME $project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {![string match -nocase *_Servo $name] || [inside $dir $root]} {
            error {STOP: open external COPY named *_Servo}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach run [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {
                error "STOP: active run $run"
            }
        }
        set plan {}; set horizontal 0; set vertical 0
        foreach f [get_files -quiet -of_objects [get_filesets constrs_1]] {
            if {[lsearch -exact [list_property $f] IS_GENERATED]>=0 && [get_property IS_GENERATED $f]} {continue}
            set path [file normalize [get_property NAME $f]]
            if {[string tolower [file extension $path]] ne {.xdc}} {continue}
            set content [read_file $path]
            set kind {}
            switch [file tail $path] {
                board_pins.xdc {incr horizontal; set kind horizontal}
                horizontal_reserved.xdc {incr vertical; set kind vertical}
            }
            if {$kind ne {}} {
                if {![inside $path $dir]} {error "STOP: constraint outside your project: $path"}
                set content [rewrite $content $kind]
                lappend plan [list $path $content]
            }
            check_collision $content
        }
        if {$horizontal!=1 || $vertical!=1} {
            error {STOP: expected one board_pins.xdc and one horizontal_reserved.xdc in prepared Servo project}
        }
        # All paths and collisions checked before touching either constraint.
        set backup [file join $dir handoff before_servo_pins_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        foreach item $plan {
            lassign $item path content
            file copy $path [file join $backup [file tail $path]]
        }
        foreach item $plan {
            lassign $item path content
            set h [open $path wb]; try {puts -nonewline $h $content} finally {close $h}
        }
        puts "SERVO_PIN_BACKUP=$backup"
        puts {SERVO_PINS_UPDATED: horizontal=T15 vertical=W15 LVCMOS33; vertical remains LOW}
        puts {OLD_BIT_IS_UNCHANGED: rebuild implementation/bitstream manually before using the new pins}
        puts {NO_SYNTHESIS_IMPLEMENTATION_OR_HARDWARE_ACTIONS_STARTED}
    }
}
if {![info exists ::ss_servo_pins::library_only] || !$::ss_servo_pins::library_only} {ss_servo_pins::run}
