set work [file dirname [file normalize [info script]]]
set repo [file normalize [file join $work ../../..]]
set stage [file join $work native]
# Batch-session package discovery only; do not reset or edit the user's TclStore.
lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore support appinit]
lappend auto_path [file join $::env(XILINX_VIVADO) data XilinxTclStore support args]
package require ::tclapp::support::appinit 1.2
proc check {} {
    global stage repo work
    # This directory is the test's own isolated source snapshot, not the user's project.
    create_project SoundSight_PS $stage -part xc7z020clg400-2 -force
    set_property target_language Verilog [current_project]
    set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY XPM_FIFO} [current_project]
    set src [file join $work inputs SoundSight_PS.srcs sources_1]
    foreach f [glob [file join $src imports rtl *]] {add_files -norecurse [list $f]}
    foreach f [glob [file join $src ip * *.xci]] {add_files -norecurse [list $f]}
    foreach f [glob [file join $work inputs original_constraints *.xdc]] {
        add_files -norecurse -fileset constrs_1 [list $f]
    }
    set bd [file join $src bd soundsight_stm32_bd soundsight_stm32_bd.bd]
    add_files -norecurse [list $bd]
    update_compile_order -fileset sources_1
    open_bd_design $bd
    set protected {}
    foreach property [list_property [get_bd_cells ps7]] {
        if {[regexp {^CONFIG.PCW_(UIPARAM_DDR|MIO_|.*PERIPHERAL_ENABLE|.*GRP_)} $property]} {
            dict set protected $property [get_property $property [get_bd_cells ps7]]
        }
    }
    # Two executions must preserve the user board settings and not duplicate IP.
    for {set i 0} {$i < 2} {incr i} {
        source [file join $repo project bd complete_manual_ps.tcl]
        if {[llength [get_bd_cells]] != 19} {error "Expected exactly 19 BD cells"}
        dict for {property value} $protected {
            if {[get_property $property [get_bd_cells ps7]] ne $value} {
                error "Board setting changed: $property"
            }
        }
        foreach {a b} {
            ps7/FCLK_RESET0_N bus_reset/ext_reset_in
            ps7/FCLK_RESET0_N bus_io_reset/ext_reset_in
            ps7/FCLK_RESET1_N clk_main/resetn
            io_release/dest_arst ps_link/rst_n
            bus_io_reset/peripheral_aresetn ps_link/aresetn
            compute/draining ps_link/compute_draining
            ps_link/run_enable compute/enable
            ps_link/feature_ready compute/feature_ready
        } {
            if {[get_bd_nets -of_objects [get_bd_pins $a]] ne
                [get_bd_nets -of_objects [get_bd_pins $b]]} {error "Wrong connection $a -> $b"}
        }
        if {[get_bd_nets -of_objects [get_bd_pins ps_link/rst_n]] eq
            [get_bd_nets -of_objects [get_bd_pins ps_link/aresetn]]} {
            error "Cold reset merged with bus reset"
        }
        foreach f [get_files -of_objects [get_filesets constrs_1]] {
            if {[string first ps_constraints [get_property NAME $f]] < 0} {
                error "Old STM32 constraint still registered"
            }
        }
        puts "CHECK_PASS iteration=$i board_properties=[dict size $protected] cells=19"
    }
    # A deliberate conflicting net must be refused without merging the domains.
    if {![catch {ss_manual_ps::wire ps_link/rst_n ps_link/aresetn} message] ||
        ![string match {*Conflicting nets*} $message]} {error "Conflict guard ineffective"}
    foreach run [get_runs] {
        if {[get_property STATUS $run] ne "Not started"} {error "Unexpected run state $run"}
    }
    puts "NATIVE_MANUAL_PS_CHECK_PASS: repeat-safe, board settings preserved, conflict refused, no builds."
    close_project
}
if {[catch {check} result options]} {
    puts stderr [dict get $options -errorinfo]
    exit 1
}
exit 0
