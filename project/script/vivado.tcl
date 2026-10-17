# SoundSight的正式入口。默认只准备工程，综合和实现由用户在GUI点击。
# Tcl Console: source <本文件>; ss_project::prepare stm32 或 ps
namespace eval ss_project {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    proc destination {variant} {
        variable root
        if {$variant eq "stm32"} {return [file join $root project par]}
        if {$variant eq "ps"} {return [file join $root variants pl_ps project par]}
        error {Variant must be stm32 or ps}
    }
    proc name {variant} {if {$variant eq "stm32"} {return SoundSight};return SoundSight_PS}
    proc prepare {variant} {
        variable root
        if {[llength [get_projects -quiet]]} {error {Close the current project before preparing another project}}
        set destination [destination $variant]
        set project_name [name $variant]
        if {[file exists [file join $destination ${project_name}.xpr]]} {error {Project exists; open it. Preparation never overwrites a project}}
        foreach existing [glob -nocomplain -directory $destination *] {
            if {[file tail $existing] ne "_launcher"} {error {Output directory contains existing work; preparation does not overwrite it}}
        }
        file mkdir $destination
        create_project $project_name $destination -part xc7z020clg400-1
        set_property target_language Verilog [current_project]
        set_property simulator_language Mixed [current_project]
        set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY XPM_FIFO} [current_project]
        set listfile [file join $root project script src_list.txt]
        if {$variant eq "ps"} {set listfile [file join $root document build ps-src-list.txt]}
        set handle [open $listfile r];set lines [split [read $handle] \n];close $handle
        foreach line $lines {
            set line [string trim $line]
            if {$line eq "" || [string match {#*} $line]} {continue}
            set path [file normalize [file join $root $line]]
            if {![file isfile $path]} {error "Missing source: $line"}
            add_files -norecurse [list $path]
        }
        source [file join $root project ip create_fft_ip.tcl]
        update_compile_order -fileset sources_1
        set ss_root $root
        source [file join $root project bd ${variant}.tcl]
        validate_bd_design
        save_bd_design
        set bd_file [get_files -quiet */soundsight_${variant}_bd.bd]
        set wrappers [make_wrapper -files $bd_file -top]
        add_files -norecurse $wrappers
        set_property top soundsight_${variant}_bd_wrapper [get_filesets sources_1]
        foreach file {board_pins.xdc interface_timing.xdc} {
            add_files -fileset constrs_1 -norecurse [list [file join $root project sdc $variant $file]]
        }
        update_compile_order -fileset sources_1
        set handle [open [file join $destination prepared.txt] w]
        puts $handle "variant=$variant\npart=xc7z020clg400-1\nvivado=[version -short]\nPS_DDR_MIO=user_configuration_required\nsynthesis=NOT_RUN\nimplementation=NOT_RUN"
        close $handle
        puts "SOUNDSIGHT_PREPARED $destination; no synthesis, implementation or hardware action"
    }
    proc open_variant {variant} {
        set path [file join [destination $variant] [name $variant].xpr]
        if {![file isfile $path]} {error {Prepare the selected variant first}}
        open_project $path
    }
    proc outputs {} {
        variable root
        if {![llength [get_projects -quiet]] || [get_property NAME [current_project]] ni {SoundSight SoundSight_PS}} {error {Open a SoundSight project first}}
        foreach run [get_runs] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {error "Active run: $run"}
        }
        # BD内嵌IP必须由父BD生成；这里只有两个独立FFT IP可单独生成。
        generate_target all [get_ips {ss_fft29 ss_ifft25}]
        generate_target all [get_files -quiet *.bd]
        export_ip_user_files -of_objects [get_ips {ss_fft29 ss_ifft25}] -no_script -sync -force -quiet
        source [file join $root tools audit_native.tcl]
        puts {SOUNDSIGHT_OUTPUTS_READY: no synthesis or implementation run launched}
    }
}
if {[info exists ::ss_cli] && $::ss_cli} {
    set action [lindex $::ss_args 0];set variant [lindex $::ss_args 1]
    if {$action eq ""} {set action prepare};if {$variant eq ""} {set variant stm32}
    switch -- $action {
        prepare {ss_project::prepare $variant}
        open {ss_project::open_variant $variant}
        outputs {ss_project::open_variant $variant;ss_project::outputs}
        default {error {Use prepare|open|outputs stm32|ps. Synthesis and implementation are manual.}}
    }
}
