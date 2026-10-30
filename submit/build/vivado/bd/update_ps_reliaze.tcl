# Unified external Reliaze update: manual calibration + timed four-mic PCM DMA.
# Source from the open copy. Never opens/changes the original Servo project.
# Package layout is project/bd + project/rtl; no workstation paths embedded.
namespace eval ss_reliaze_update {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    variable names {ss_manual_servo.sv ss_ps_control_regs.sv ss_ps_link.sv bd_ps_link.v
        ss_axi_lite_regs.sv ss_snapshot_queue.sv f1a_frame_store.sv ss_pair_engine.sv
        ss_pcm_windows.sv ss_clean_compute.sv ss_dual_compute.sv bd_clean_compute.v
        ss_pcm_time_cdc.sv ss_audio_fifo.sv ss_audio_capture.sv bd_audio_capture.v}
    proc one {xs label} {
        if {[llength $xs]!=1} {error "STOP: expected one $label, got $xs"}
        return [lindex $xs 0]
    }
    proc inside {path base} {
        set p [file split [file normalize $path]];set b [file split [file normalize $base]]
        return [expr {[llength $p]>[llength $b] && [string equal -nocase [lrange $p 0 [expr {[llength $b]-1}]] $b]}]
    }
    proc bytes {path} {set f [open $path rb];try {return [read $f]} finally {close $f}}
    proc refs {name} {
        set out {}
        foreach f [get_files -quiet -of_objects [get_filesets sources_1]] {
            if {[string equal -nocase [file tail [get_property NAME $f]] $name]} {lappend out $f}
        }
        return $out
    }
    proc pin {p} {return [one [get_bd_pins -quiet $p] $p]}
    proc net {source sinks} {
        set a [pin $source];set n [get_bd_nets -quiet -of_objects $a]
        foreach s $sinks {
            set b [pin $s];set bn [get_bd_nets -quiet -of_objects $b]
            if {[llength $bn]} {
                if {$n ne $bn} {error "STOP: conflicting net at $s"}
            } elseif {[llength $n]} {connect_bd_net -net $n $b
            } else {connect_bd_net $a $b;set n [get_bd_nets -quiet -of_objects $a]}
        }
    }
    proc intf {source sink} {
        set a [one [get_bd_intf_pins -quiet $source] $source]
        set b [one [get_bd_intf_pins -quiet $sink] $sink]
        set an [get_bd_intf_nets -quiet -of_objects $a];set bn [get_bd_intf_nets -quiet -of_objects $b]
        if {[llength $an] || [llength $bn]} {
            if {$an ne $bn} {error "STOP: conflicting interface $source -> $sink"}
        } else {connect_bd_intf_net $a $b}
    }
    proc control_migration {} {
        # Inspect before any copy/disconnect. Reject hand-edited or half-migrated
        # control wiring instead of stealing a net from another source.
        set old {};set fresh {}
        foreach {sink source} {
            audio_capture/run_enable_async ps_link/run_enable
            audio_capture/compute_draining_async compute/draining
            audio_capture/run_enable compute/audio_run
            audio_capture/compute_draining compute/audio_draining
        } {
            set p [get_bd_pins -quiet $sink]
            if {![llength $p]} {continue}
            set n [get_bd_nets -quiet -of_objects $p]
            set s [get_bd_pins -quiet $source]
            if {[llength $s]!=1 || [llength $n]!=1 ||
                $n ne [get_bd_nets -quiet -of_objects $s]} {
                error "STOP: unexpected audio control connection at $sink"
            }
            if {[string match *_async $sink]} {lappend old $p} else {lappend fresh $p}
        }
        if {!(([llength $old]==2 && [llength $fresh]==0) ||
              ([llength $old]==0 && [llength $fresh]==2))} {
            error {STOP: partially migrated audio control ports}
        }
        return $old
    }
    # Vivado may source initialization Tcl in the caller scope when opening a BD.
    # Keep those temporary variables out of run() and its validated paths.
    proc open_design {bd_file} {open_bd_design $bd_file}
    proc run {} {
        variable root;variable names
        set project [one [get_projects -quiet] project]
        set name [get_property NAME $project];set dir [file normalize [get_property DIRECTORY $project]]
        if {![string equal -nocase $name SoundSight_PS_Reliaze] || [inside $dir $root] || $dir eq $root} {
            error {STOP: open the external SoundSight_PS_Reliaze copy, not Servo or the repository}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: wrong part}}
        foreach r [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $r]]} {error "STOP: active run $r"}
        }
        if {[current_bd_design -quiet] eq {}} {open_design [one [get_files -quiet *.bd] BD]}
        current_bd_instance /
        set bd [current_bd_design];set bdobj [one [get_files -quiet */${bd}.bd] BD]
        set bdpath [get_property NAME $bdobj]
        if {![inside $bdpath $dir]} {error {STOP: BD is outside the copy}}
        if {[get_property TOP [get_filesets sources_1]] ne "${bd}_wrapper"} {error {STOP: unexpected top}}
        foreach {c v} {compute xilinx.com:module_ref:bd_clean_compute:1.0 ps_link xilinx.com:module_ref:bd_ps_link:1.0 ps7 xilinx.com:ip:processing_system7:5.5} {
            if {[get_property VLNV [one [get_bd_cells -quiet $c] $c]] ne $v} {error "STOP: wrong $c"}
        }
        foreach {p v} {ACTUATOR_BOUND 1 LEVEL_ENABLE 1 SERVO_MAX 360 CLK_FREQ_HZ 61440000} {
            if {[get_property CONFIG.$p [get_bd_cells ps_link]]!=$v} {error "STOP: unexpected ps_link $p"}
        }
        foreach {f port package_pin} {board_pins.xdc servo_pwm T15 horizontal_reserved.xdc servo_vertical_pwm W16} {
            set obj [one [get_files -quiet -of_objects [get_filesets constrs_1] */$f] $f]
            set path [get_property NAME $obj]
            if {![inside $path $dir]} {error "STOP: active constraint outside copy: $path"}
            set pattern [format {set_property\s+PACKAGE_PIN\s+%s\s+\[get_ports\s+\{?%s\}?\]} $package_pin $port]
            if {![regexp $pattern [bytes $path]]} {error "STOP: expected $port on $package_pin"}
        }
        # All paths and collisions are checked before copying or editing the BD.
        set existing [refs ss_clean_compute.sv]
        set source_dir [file dirname [get_property NAME [one $existing compute_source]]]
        if {![inside $source_dir $dir]} {error {STOP: RTL is not local to the copy}}
        set plan {}
        foreach f $names {
            set src [file join $root project rtl $f]
            if {![file isfile $src]} {error "STOP: missing package dependency $src"}
            set matches [refs $f]
            if {[llength $matches]>1} {error "STOP: duplicate source $f"}
            set dest [file join $source_dir $f]
            if {[llength $matches]} {
                set dest [file normalize [get_property NAME [lindex $matches 0]]]
                if {![inside $dest $dir]} {error "STOP: external reference $dest"}
            } elseif {[file exists $dest]} {error "STOP: unregistered local file $dest"}
            lappend plan [list $src $dest [llength $matches]]
        }
        set present 0
        foreach {c v} {audio_capture xilinx.com:module_ref:bd_audio_capture:1.0 axi_dma_audio xilinx.com:ip:axi_dma:7.1 audio_mem_bus xilinx.com:ip:axi_interconnect:2.1} {
            set obj [get_bd_cells -quiet $c]
            if {[llength $obj]} {
                incr present
                if {[get_property VLNV $obj] ne $v} {error "STOP: name collision $c"}
            }
        }
        if {$present!=0 && $present!=3} {error {STOP: partially installed audio BD; inspect the saved backup}}
        set old_controls {}
        if {$present==3} {set old_controls [control_migration]}
        if {$present==0 && [get_property CONFIG.NUM_MI [get_bd_cells control_bus]]!=1} {error {STOP: unexpected control bus}}
        if {$present==0 && [llength [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins -quiet ps7/S_AXI_HP0]]]} {
            error {STOP: HP0 is already connected}
        }
        foreach seg [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces ps7/Data]] {
            set lo [get_property OFFSET $seg];set size [get_property RANGE $seg]
            if {$lo eq {} || $size eq {}} {continue}
            foreach base {0x40400000 0x43C00000} {
                if {$lo < $base+0x10000 && $lo+$size > $base &&
                    !($present==3 && ($lo==0x40400000 || $lo==0x43C00000))} {
                    error "STOP: audio address overlaps $seg"
                }
            }
        }
        set backup [file join $dir handoff before_pcm_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]]
        file mkdir $backup
        save_bd_design
        file copy $bdpath [file join $backup before.bd]
        file copy [file join $dir ${name}.xpr] [file join $backup before.xpr]
        # Preserve the old shared nets and every other sink, including the
        # direct PS STOP/control path. Only remove the two obsolete audio sinks.
        foreach p $old_controls {disconnect_bd_net [get_bd_nets -of_objects $p] $p}
        set manifest [open [file join $backup replaced_paths.txt] w]
        try {
            foreach row $plan {
                lassign $row src dest registered
                puts $manifest "$registered\t$dest"
                if {[file exists $dest]} {file copy $dest [file join $backup [file tail $dest]]}
                file copy -force $src $dest
                if {[bytes $src] ne [bytes $dest]} {error "STOP: copy mismatch $dest"}
                if {!$registered} {add_files -norecurse -fileset sources_1 [list $dest]}
            }
        } finally {close $manifest}
        update_compile_order -fileset sources_1
        foreach module {bd_clean_compute bd_ps_link} {
            set ip [one [get_ips -all -filter "IPDEF == xilinx.com:module_ref:${module}:1.0" "${bd}_*"] $module]
            update_module_reference -verbose $ip
        }
        set_property CONFIG.AUDIO_ENABLE 1 [get_bd_cells compute]
        set_property CONFIG.AUDIO_ENABLE 1 [get_bd_cells ps_link]
        if {$present==0} {
            create_bd_cell -type module -reference bd_audio_capture audio_capture
            create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_audio
            create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 audio_mem_bus
        } else {
            update_module_reference -verbose [one [get_ips -all -filter {IPDEF == xilinx.com:module_ref:bd_audio_capture:1.0} "${bd}_*"] audio_capture_ip]
        }
        set_property -dict [list CONFIG.c_include_sg 0 CONFIG.c_include_mm2s 0 CONFIG.c_include_s2mm 1 \
            CONFIG.c_micro_dma 0 CONFIG.c_include_s2mm_dre 0 CONFIG.c_s_axis_s2mm_tdata_width 32 \
            CONFIG.c_m_axi_s2mm_data_width 64 CONFIG.c_sg_length_width 16 \
            CONFIG.c_s2mm_burst_size 16] [get_bd_cells axi_dma_audio]
        set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] [get_bd_cells audio_mem_bus]
        set_property -dict [list CONFIG.PCW_USE_S_AXI_HP0 1 CONFIG.PCW_S_AXI_HP0_DATA_WIDTH 64] [get_bd_cells ps7]
        set_property CONFIG.NUM_MI 3 [get_bd_cells control_bus]
        intf control_bus/M01_AXI axi_dma_audio/S_AXI_LITE
        intf control_bus/M02_AXI audio_capture/S_AXI
        intf audio_capture/M_AXIS axi_dma_audio/S_AXIS_S2MM
        intf axi_dma_audio/M_AXI_S2MM audio_mem_bus/S00_AXI
        intf audio_mem_bus/M00_AXI ps7/S_AXI_HP0
        net clk_main/clk_out2 {control_bus/M01_ACLK control_bus/M02_ACLK audio_capture/clk
            axi_dma_audio/s_axi_lite_aclk axi_dma_audio/m_axi_s2mm_aclk
            audio_mem_bus/ACLK audio_mem_bus/S00_ACLK audio_mem_bus/M00_ACLK ps7/S_AXI_HP0_ACLK}
        net bus_reset/peripheral_aresetn {control_bus/M01_ARESETN control_bus/M02_ARESETN
            audio_capture/aresetn axi_dma_audio/axi_resetn audio_mem_bus/S00_ARESETN audio_mem_bus/M00_ARESETN}
        net bus_reset/interconnect_aresetn {audio_mem_bus/ARESETN}
        net core_release/dest_arst {audio_capture/rst_n}
        net axi_dma_audio/s2mm_prmry_reset_out_n {audio_capture/dma_resetn}
        net compute/audio_run {audio_capture/run_enable}
        net compute/audio_draining {audio_capture/compute_draining}
        foreach {a b} {audio_valid pcm_valid audio_clip pcm_clip audio_source_fault pcm_fault audio_pcm pcm audio_sample_index sample_index} {
            net compute/$a [list audio_capture/$b]
        }
        net audio_capture/epoch {compute/audio_epoch}
        net audio_capture/active {compute/audio_active}
        net compute/feature_meta {ps_link/feature_meta}
        if {$present==0} {
            set old [get_bd_nets -quiet -of_objects [pin irq_concat/In1]]
            if {[llength $old]} {disconnect_bd_net $old [pin irq_concat/In1]}
        }
        set_property -dict [list CONFIG.NUM_PORTS 3 CONFIG.IN0_WIDTH 1 CONFIG.IN1_WIDTH 1 CONFIG.IN2_WIDTH 14] [get_bd_cells irq_concat]
        set_property CONFIG.CONST_WIDTH 14 [get_bd_cells irq_zero]
        net axi_dma_audio/s2mm_introut {irq_concat/In1}
        net irq_zero/dout {irq_concat/In2}
        assign_bd_address -offset 0x40400000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs axi_dma_audio/S_AXI_LITE/Reg] -force
        assign_bd_address -offset 0x43C00000 -range 0x00001000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs audio_capture/S_AXI/reg0] -force
        assign_bd_address -target_address_space [get_bd_addr_spaces axi_dma_audio/Data_S2MM] [get_bd_addr_segs ps7/S_AXI_HP0/HP0_DDR_LOWOCM]
        validate_bd_design
        save_bd_design
        generate_target all [list $bdobj]
        update_compile_order -fileset sources_1
        puts "RELIAZE_BACKUP=$backup"
        puts {RELIAZE_PREPARED: manual + timed PCM; DMA=0x40400000 audio=0x43C00000; T15/W16 unchanged}
        puts {RELIAZE_CDC_CONTROL_V2: source-registered controls; shared compute/audio run; rebuild bit/HWH required}
        puts {NO_SYNTHESIS_IMPLEMENTATION_BITSTREAM_OR_HARDWARE_ACTIONS_STARTED}
    }
}
if {![info exists ::ss_reliaze_library_only] || !$::ss_reliaze_library_only} {ss_reliaze_update::run}
