# Update an existing external *_Servo project. Pins/BD interfaces stay unchanged.
namespace eval ss_volume_update {variable library_only 1}
try {source [file join [file dirname [info script]] update_ps_volume.tcl]} finally {set ::ss_volume_update::library_only 0}
namespace eval ss_manual_update {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc run {} {
        variable root
        set project [ss_volume_update::one [get_projects -quiet] project]
        set name [get_property NAME $project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {![string match -nocase *_Servo $name] || [ss_volume_update::inside $dir $root] || $dir eq $root} {
            error {STOP: open your existing external *_Servo project}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach r [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $r]]} {error "STOP: active run $r"}
        }
        if {[current_bd_design -quiet] eq {}} {open_bd_design [ss_volume_update::one [get_files -quiet *.bd] BD]}
        current_bd_instance /
        set bd [current_bd_design]
        set bdobj [ss_volume_update::one [get_files -quiet */${bd}.bd] BD]
        if {![ss_volume_update::inside [get_property NAME $bdobj] $dir]} {error {STOP: BD outside project}}
        set link [ss_volume_update::one [get_bd_cells -quiet ps_link] ps_link]
        foreach {p value} {ACTUATOR_BOUND 1 LEVEL_ENABLE 1 SERVO_MAX 360 CLK_FREQ_HZ 61440000} {
            if {[get_property CONFIG.$p $link] != $value} {error "STOP: unexpected $p"}
        }
        # Use the REGISTERED XDC files, not old import-source copies nearby.
        foreach {name port pin} {board_pins.xdc servo_pwm T15 horizontal_reserved.xdc servo_vertical_pwm W15} {
            set f [ss_volume_update::one [get_files -quiet -of_objects [get_filesets constrs_1] */$name] $name]
            set text [ss_volume_update::bytes [get_property NAME $f]]
            set pattern [format {set_property\s+PACKAGE_PIN\s+%s\s+\[get_ports\s+\{?%s\}?\]} $pin $port]
            if {![regexp $pattern $text]} {error "STOP: expected $port on $pin; no pin changes are made"}
        }
        set regs [ss_volume_update::one [ss_volume_update::refs ss_ps_control_regs.sv] registers]
        set target [file normalize [get_property NAME $regs]]
        if {![ss_volume_update::inside $target $dir]} {error {STOP: registers not copied into your project}}
        set queue [file normalize [get_property NAME [ss_volume_update::one [ss_volume_update::refs ss_snapshot_queue.sv] snapshot_queue]]]
        if {![ss_volume_update::inside $queue $dir]} {error {STOP: snapshot queue outside project}}
        set newrefs [ss_volume_update::refs ss_manual_servo.sv]
        if {[llength $newrefs]>1} {error {STOP: duplicate manual controller}}
        set manual [file join [file dirname $target] ss_manual_servo.sv]
        if {[llength $newrefs]} {
            set manual [file normalize [get_property NAME [lindex $newrefs 0]]]
            if {![ss_volume_update::inside $manual $dir]} {error {STOP: manual controller outside project}}
        } elseif {[file exists $manual]} {error {STOP: unregistered manual source exists; preserve it}}
        foreach file {ss_ps_control_regs.sv ss_manual_servo.sv ss_snapshot_queue.sv} {
            if {![file isfile [file join $root project rtl $file]]} {error "STOP: missing $file"}
        }
        set backup [file join $dir handoff before_manual_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        file copy $target [file join $backup ss_ps_control_regs.sv]
        file copy $queue [file join $backup ss_snapshot_queue.sv]
        if {[file exists $manual]} {file copy $manual [file join $backup ss_manual_servo.sv]}
        save_bd_design
        file copy [get_property NAME $bdobj] [file join $backup before.bd]
        foreach {name dest} [list ss_ps_control_regs.sv $target ss_manual_servo.sv $manual ss_snapshot_queue.sv $queue] {
            set source [file join $root project rtl $name]
            file copy -force $source $dest
            if {[ss_volume_update::bytes $source] ne [ss_volume_update::bytes $dest]} {error "STOP: copy mismatch $dest"}
        }
        if {![llength $newrefs]} {add_files -norecurse -fileset sources_1 [list $manual]}
        update_compile_order -fileset sources_1
        set ip [ss_volume_update::one [get_ips -all -filter {IPDEF == xilinx.com:module_ref:bd_ps_link:1.0} "${bd}_*"] ps_link_ip]
        update_module_reference -verbose $ip
        validate_bd_design
        save_bd_design
        generate_target all [list $bdobj]
        update_compile_order -fileset sources_1
        puts "MANUAL_BACKUP=$backup"
        puts {MANUAL_PREPARED: audio-independent calibration; horizontal=T15 vertical=W15 unchanged}
        puts {NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED}
    }
}
ss_manual_update::run
