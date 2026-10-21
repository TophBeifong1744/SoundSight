# Complete the user's copied STM32 BD as a PL+PS design.
# Run with source in the open SoundSight_PS project, with its BD open.
# Keeps board-specific PS DDR/MIO and existing clock/FFT configuration.
# Does not launch synthesis, implementation, programming, or hardware resets.
namespace eval ss_manual_ps {
    variable repo [file normalize [file join [file dirname [info script]] ../..]]

    proc one {objects label} {
        if {[llength $objects] != 1} {error "Expected one $label; found: $objects"}
        return [lindex $objects 0]
    }
    proc cell {name} {return [one [get_bd_cells -quiet $name] "BD cell $name"]}
    proc pin {name} {
        if {[string first / $name] >= 0} {
            return [one [get_bd_pins -quiet $name] "pin $name"]
        }
        return [one [get_bd_ports -quiet $name] "port $name"]
    }

    # Extend an existing net, or create one. Never silently merge conflicting
    # nets: that could short clock/reset domains or introduce multiple drivers.
    proc wire {args} {
        set objects {}; set nets {}
        foreach name $args {
            set p [pin $name]
            lappend objects $p
            foreach n [get_bd_nets -quiet -of_objects $p] {lappend nets $n}
        }
        set nets [lsort -unique $nets]
        if {[llength $nets] > 1} {error "Conflicting nets for $args: $nets"}
        if {[llength $nets] == 0} {
            connect_bd_net {*}$objects
        } else {
            foreach p $objects {
                if {[llength [get_bd_nets -quiet -of_objects $p]] == 0} {
                    connect_bd_net -net [lindex $nets 0] $p
                }
            }
        }
    }
    proc bus {a b} {
        set pa [one [get_bd_intf_pins -quiet $a] $a]
        set pb [one [get_bd_intf_pins -quiet $b] $b]
        set na [get_bd_intf_nets -quiet -of_objects $pa]
        set nb [get_bd_intf_nets -quiet -of_objects $pb]
        if {[llength $na] == 0 && [llength $nb] == 0} {
            connect_bd_intf_net $pa $pb
        } elseif {[llength $na] != 1 || $na ne $nb} {
            error "Unexpected existing AXI connection: $a=$na, $b=$nb"
        }
    }
    proc ip {name vlnv properties} {
        if {[llength [get_bd_cells -quiet $name]] == 0} {
            create_bd_cell -type ip -vlnv $vlnv $name
        }
        if {[get_property VLNV [cell $name]] ne $vlnv} {
            error "Wrong IP type for $name"
        }
        if {[llength $properties]} {set_property -dict $properties [cell $name]}
    }

    proc complete {} {
        variable repo
        set project [one [get_projects -quiet] "open project"]
        if {![string equal -nocase [get_property NAME $project] SoundSight_PS]} {
            error "Open the copied SoundSight_PS project, not the STM32 original."
        }
        if {[get_property PART $project] ne "xc7z020clg400-2"} {
            error "Expected part xc7z020clg400-2"
        }
        foreach run [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {
                error "Run $run is active. Wait for it to finish before changing the BD."
            }
        }
        set bd [current_bd_design -quiet]
        if {$bd eq ""} {error "Open the copied BD before sourcing this script."}
        current_bd_instance /
        set bdfile [one [get_files -quiet */${bd}.bd] "current BD file"]
        foreach {name ref} {compute bd_clean_compute ps_link bd_ps_link} {
            if {[get_property VLNV [cell $name]] ne "xilinx.com:module_ref:${ref}:1.0"} {
                error "Expected $name to reference $ref"
            }
        }
        if {[llength [get_bd_cells -quiet link]] ||
            [llength [get_bd_ports -quiet {spi_sck spi_cs_n spi_mosi spi_miso irq}]]} {
            error "Remove the old STM32 link and external SPI/IRQ ports first."
        }
        foreach name {ps7 clk_main clk_audio core_reset io_reset core_reset_gate
                      io_reset_gate core_release io_release one zero} {cell $name}
        # Check retained clocks; do not replace user's MMCM or PS presets.
        foreach {name property expected} {
            ps7 PCW_FPGA0_PERIPHERAL_FREQMHZ 100
            clk_main PRIM_IN_FREQ 100
            clk_main CLKOUT1_REQUESTED_OUT_FREQ 96
            clk_main CLKOUT2_REQUESTED_OUT_FREQ 100
            clk_audio PRIM_IN_FREQ 96
            clk_audio CLKOUT1_REQUESTED_OUT_FREQ 61.44
        } {
            if {abs([get_property CONFIG.$property [cell $name]] - $expected) > 0.0001} {
                error "Unexpected clock configuration: $name CONFIG.$property"
            }
        }
        foreach name {core_release io_release} {
            if {[get_property CONFIG.RST_ACTIVE_HIGH [cell $name]]} {
                error "$name must produce an active-low cold reset."
            }
        }
        foreach name {board_pins.xdc interface_timing.xdc} {
            if {![file isfile [file join $repo project sdc ps $name]]} {
                error "Missing PS constraint file: $name"
            }
        }

        # Save the user's in-memory edits before any design mutation. A failed
        # operation leaves this backup and the working BD available for diagnosis.
        save_bd_design
        set projdir [get_property DIRECTORY $project]
        set backup [file join $projdir handoff before_ps_bd_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        file copy [get_property NAME $bdfile] [file join $backup ${bd}.bd]
        set xpr [file join $projdir [get_property NAME $project].xpr]
        if {[file isfile $xpr]} {file copy $xpr [file join $backup before.xpr]}
        puts "PS_BD_BACKUP $backup"

        # Enable only the PS interfaces needed here. No board preset is applied.
        set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 \
            CONFIG.PCW_USE_FABRIC_INTERRUPT 1 CONFIG.PCW_IRQ_F2P_INTR 1 \
            CONFIG.PCW_EN_RST0_PORT 1 CONFIG.PCW_EN_RST1_PORT 1] [cell ps7]
        ip control_bus xilinx.com:ip:axi_interconnect:2.1 {
            CONFIG.NUM_SI 1 CONFIG.NUM_MI 1
        }
        ip control_cdc xilinx.com:ip:axi_clock_converter:2.1 {
            CONFIG.PROTOCOL AXI4LITE CONFIG.DATA_WIDTH 32
            CONFIG.ACLK_ASYNC 1 CONFIG.SYNCHRONIZATION_STAGES 3
        }
        foreach name {bus_reset bus_io_reset} {
            # Vivado derives C_EXT_RESET_HIGH from the connected FCLK_RESET0_N
            # interface. It is read-only in BD; check the propagated value below.
            ip $name xilinx.com:ip:proc_sys_reset:5.0 {
                CONFIG.C_AUX_RESET_HIGH 0
            }
        }
        ip irq_concat xilinx.com:ip:xlconcat:2.1 {
            CONFIG.NUM_PORTS 2 CONFIG.IN0_WIDTH 1 CONFIG.IN1_WIDTH 15
        }
        ip irq_zero xilinx.com:ip:xlconstant:1.1 {
            CONFIG.CONST_WIDTH 15 CONFIG.CONST_VAL 0
        }
        set_property -dict {CONFIG.ACTUATOR_BOUND 0 CONFIG.CLK_FREQ_HZ 61440000} [cell ps_link]

        # Data/handshake signals already belong to the 61.44 MHz control domain.
        foreach name {feature_valid feature_pairs feature_flags source_faults} {
            wire compute/$name ps_link/$name
        }
        wire compute/draining ps_link/compute_draining
        wire ps_link/feature_ready compute/feature_ready
        wire ps_link/run_enable compute/enable
        wire ps_link/servo_pwm servo_pwm
        wire compute/pdm_clocks pdm_clocks
        wire pdm_data compute/pdm_data

        wire clk_main/clk_out2 ps7/M_AXI_GP0_ACLK control_bus/ACLK \
            control_bus/S00_ACLK control_bus/M00_ACLK control_cdc/s_axi_aclk \
            bus_reset/slowest_sync_clk
        wire clk_audio/clk_out1 control_cdc/m_axi_aclk ps_link/clk \
            bus_io_reset/slowest_sync_clk
        wire clk_audio/locked bus_reset/dcm_locked bus_io_reset/dcm_locked
        wire ps7/FCLK_RESET0_N bus_reset/ext_reset_in bus_io_reset/ext_reset_in
        wire one/dout bus_reset/aux_reset_in bus_io_reset/aux_reset_in
        wire zero/dout bus_reset/mb_debug_sys_rst bus_io_reset/mb_debug_sys_rst
        wire bus_reset/interconnect_aresetn control_bus/ARESETN
        wire bus_reset/peripheral_aresetn control_bus/S00_ARESETN \
            control_bus/M00_ARESETN control_cdc/s_axi_aresetn
        wire bus_io_reset/peripheral_aresetn control_cdc/m_axi_aresetn ps_link/aresetn
        # Ordinary AXI reset must not clear the retained feature slots.
        wire io_release/dest_arst ps_link/rst_n
        bus ps7/M_AXI_GP0 control_bus/S00_AXI
        bus control_bus/M00_AXI control_cdc/S_AXI
        bus control_cdc/M_AXI ps_link/S_AXI
        wire ps_link/irq irq_concat/In0
        wire irq_zero/dout irq_concat/In1
        wire irq_concat/dout ps7/IRQ_F2P
        assign_bd_address
        validate_bd_design
        foreach name {bus_reset bus_io_reset} {
            if {[get_property CONFIG.C_EXT_RESET_HIGH [cell $name]] ||
                [get_property CONFIG.C_AUX_RESET_HIGH [cell $name]]} {
                error "Expected active-low external/auxiliary resets on $name"
            }
        }
        save_bd_design

        # Copy PS constraints into the external working project. Preserve old
        # files on disk, but remove their project references (SPI ports are gone).
        set dest [file join $projdir ps_constraints]
        file mkdir $dest
        set constraints [get_filesets constrs_1]
        foreach name {board_pins.xdc interface_timing.xdc} {
            set i 0
            foreach f [get_files -quiet -of_objects $constraints] {
                if {[file tail [get_property NAME $f]] eq $name} {
                    incr i
                    file copy [get_property NAME $f] [file join $backup ${i}_$name]
                    remove_files [list $f]
                }
            }
            set target [file join $dest $name]
            if {[file exists $target]} {
                file copy $target [file join $backup previous_$name]
            }
            file copy -force [file join $repo project sdc ps $name] $target
            add_files -norecurse -fileset constrs_1 [list $target]
        }

        # Update the copied wrapper's port list; this is not an HDL synthesis.
        set wrappers [make_wrapper -files [list $bdfile] -top -force]
        foreach f $wrappers {
            if {[llength [get_files -quiet [list $f]]] == 0} {
                add_files -norecurse -fileset sources_1 [list $f]
            }
        }
        set_property TOP ${bd}_wrapper [get_filesets sources_1]
        update_compile_order -fileset sources_1
        puts "PS_BD_COMPLETE: $bd; [llength [get_bd_cells]] cells; Validate completed."
        puts "PS_BD_NO_BUILD: no synthesis, implementation, bitstream or hardware action."
        puts "Next: Generate Output Products in the GUI; inspect Messages before building."
    }
}
ss_manual_ps::complete
