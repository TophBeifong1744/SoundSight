# 最新三维双轴工程的完整源重建；复制源码到新工程，不引用发送方工作目录。
# 只做工程/IP HDL/BD准备；不运行综合、实现、下载或板端动作。
namespace eval ss_rebuild {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    variable project_name SoundSight_PS_3D
    variable bd_name soundsight_stm32_bd

    proc source_list {} {
        variable root
        set h [open [file join $root project script ps_3d_sources.txt] r]
        set lines [split [read $h] \n]; close $h
        set paths {}
        foreach line $lines {
            set line [string trim $line]
            if {$line eq "" || [string match {#*} $line]} {continue}
            if {[file pathtype $line] ne "relative" || ".." in [file split $line]} {error "Nonportable source entry: $line"}
            set path [file join $root $line]
            if {![file isfile $path]} {error "Missing source: $line"}
            lappend paths $path
        }
        if {[llength $paths] != 32} {error {Expected 31 RTL files and one memory initializer}}
        return $paths
    }

    proc create {{destination {}}} {
        variable root
        variable project_name
        variable bd_name
        if {[version -short] ne "2025.2"} {error {This exported recipe requires Vivado 2025.2; do not silently upgrade IP}}
        if {[llength [get_projects -quiet]]} {error {Close the current project before rebuilding into a new directory}}
        if {$destination eq ""} {set destination [file join $root project par]}
        set destination [file normalize $destination]
        if {[regexp {[^\x00-\x7f]} $destination]} {error {Vivado FFT generation requires an ASCII output path}}
        if {[string bytelength $destination] > 78} {error {Vivado Windows path limit: choose an output path of at most 78 UTF-8 bytes}}
        if {[file exists $destination] && ![file isdirectory $destination]} {error {Output is not a directory}}
        foreach item [glob -nocomplain -directory $destination * .*] {
            if {[file tail $item] ni {. .. _launcher}} {error {Output contains existing work; select a new empty directory}}
        }
        set sources [source_list]
        set constraints {spi_ila_debug.xdc board_pins.xdc interface_timing.xdc horizontal_reserved.xdc dual_axis_output_timing.xdc}
        foreach name $constraints {
            if {![file isfile [file join $root project sdc ps $name]]} {error "Missing constraint: $name"}
        }
        file mkdir $destination
        create_project $project_name $destination -part xc7z020clg400-2
        set_property target_language Verilog [current_project]
        set_property simulator_language Mixed [current_project]
        set_property target_simulator XSim [current_project]
        set_property XPM_LIBRARIES {XPM_CDC XPM_FIFO XPM_MEMORY} [current_project]
        foreach path $sources {import_files -fileset sources_1 -norecurse [list $path]}
        set_property file_type {Memory File} [get_files -quiet */hann-u18f17.mem]
        source [file join $root project ip ps_3d_fft.tcl]
        ss_create_ps_3d_fft $destination
        update_compile_order -fileset sources_1
        create_bd_design $bd_name
        source [file join $root project bd ps_3d_export.tcl]
        ss_create_ps_3d_export {}
        set bd [get_files -quiet */${bd_name}.bd]
        if {[llength $bd] != 1} {error {Expected one recreated block design}}
        # 原工程为Global综合。生成HDL不启动OOC run，更不读取旧综合DCP。
        foreach object [concat [get_files -quiet */ss_fft29.xci] [get_files -quiet */ss_ifft25.xci] $bd] {
            set_property GENERATE_SYNTH_CHECKPOINT 0 $object
            set_property SYNTH_CHECKPOINT_MODE None $object
        }
        generate_target all [get_ips {ss_fft29 ss_ifft25}]
        generate_target all $bd
        set wrappers [make_wrapper -files $bd -top]
        add_files -norecurse $wrappers
        set_property top ${bd_name}_wrapper [get_filesets sources_1]
        foreach name $constraints {import_files -fileset constrs_1 -norecurse [list [file join $root project sdc ps $name]]}
        set legacy [get_files -quiet */spi_ila_debug.xdc]
        set_property IS_ENABLED 0 $legacy
        set_property USED_IN_SYNTHESIS 0 $legacy
        set_property PROCESSING_ORDER LATE $legacy
        # 保留同版本默认综合/实现策略，明确禁止依赖旧增量检查点。
        foreach run {synth_1 impl_1} {
            set_property incremental_checkpoint {} [get_runs $run]
            set_property auto_incremental_checkpoint 0 [get_runs $run]
        }
        set_property strategy {Vivado Synthesis Defaults} [get_runs synth_1]
        set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY rebuilt [get_runs synth_1]
        set_property strategy {Vivado Implementation Defaults} [get_runs impl_1]
        update_compile_order -fileset sources_1
        foreach object [get_files -of_objects [get_filesets {sources_1 constrs_1}]] {
            set path [file normalize [get_property NAME $object]]
            if {![string equal -nocase [string range $path 0 [expr {[string length $destination]}]] "${destination}/"]} {
                error "External source registration remains: [file tail $path]"
            }
        }
        foreach run [get_runs] {
            if {[regexp -nocase {running|queued|launching|complete} [get_property STATUS $run]]} {error {Unexpected executed run during preparation}}
        }
        set h [open [file join $destination PREPARED.txt] w]
        puts $h "project=${project_name}.xpr\npart=xc7z020clg400-2\nvivado=2025.2\nBD_VALIDATED=1\nIP_HDL_GENERATED=1\nSYNTHESIS=NOT_RUN\nIMPLEMENTATION=NOT_RUN\nHARDWARE_ACTIONS=0\nRTL_FILES=31\nMEMORY_FILES=1\nSERVO_HORIZONTAL=T15\nSERVO_VERTICAL=W16"
        close $h
        puts "PS_3D_PREPARED=[file join $destination ${project_name}.xpr]"
    }
}
