# 官方显示IP接合：独立HP1读DDR，软件提供帧缓冲后才启动VDMA。
set bd [get_files -norecurse soundsight_stm32_bd.bd]
open_bd_design $bd
if {![llength [get_bd_cells -quiet screen_vdma]]} {
set_property -dict [list CONFIG.PCW_USE_S_AXI_HP1 {1} CONFIG.PCW_S_AXI_HP1_DATA_WIDTH {64}] [get_bd_cells ps7]
set_property CONFIG.NUM_MI 6 [get_bd_cells control_bus]
foreach {name vlnv} {
 screen_vdma axi_vdma:6.3 screen_video v_axi4s_vid_out:4.0
 screen_vtc v_tc:6.2 screen_pixel_clk clk_wiz:6.0
 screen_iic axi_iic:2.1 screen_gpio axi_gpio:2.0 screen_hp1 axi_interconnect:2.1
 screen_reset_gate util_vector_logic:2.0 screen_pixel_reset_inv util_vector_logic:2.0
 screen_axi_release xpm_cdc_gen:1.0 screen_pixel_release xpm_cdc_gen:1.0 screen_lock_sync xpm_cdc_gen:1.0
} {create_bd_cell -type ip -vlnv xilinx.com:ip:$vlnv $name}
set_property -dict [list CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {0} CONFIG.c_include_sg {0} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {24} CONFIG.c_num_fstores {2} CONFIG.c_mm2s_linebuffer_depth {1024} CONFIG.c_mm2s_max_burst_length {64} CONFIG.c_include_mm2s_dre {0} CONFIG.c_mm2s_genlock_mode {3}] [get_bd_cells screen_vdma]
set_property -dict [list CONFIG.C_HAS_ASYNC_CLK {1} CONFIG.C_ADDR_WIDTH {10} CONFIG.C_S_AXIS_VIDEO_FORMAT {2} CONFIG.C_S_AXIS_VIDEO_DATA_WIDTH {8} CONFIG.C_NATIVE_COMPONENT_WIDTH {8} CONFIG.C_PIXELS_PER_CLOCK {1}] [get_bd_cells screen_video]
set_property -dict [list CONFIG.HAS_AXI4_LITE {false} CONFIG.enable_detection {false} CONFIG.VIDEO_MODE {Custom} CONFIG.GEN_HACTIVE_SIZE {800} CONFIG.GEN_VACTIVE_SIZE {480} CONFIG.GEN_HFRAME_SIZE {1056} CONFIG.GEN_HSYNC_START {840} CONFIG.GEN_HSYNC_END {968} CONFIG.GEN_F0_VFRAME_SIZE {525} CONFIG.GEN_F0_VSYNC_VSTART {490} CONFIG.GEN_F0_VSYNC_VEND {492} CONFIG.GEN_F0_VBLANK_HSTART {800} CONFIG.GEN_F0_VBLANK_HEND {800} CONFIG.GEN_F0_VSYNC_HSTART {800} CONFIG.GEN_F0_VSYNC_HEND {800} CONFIG.GEN_HSYNC_POLARITY {High} CONFIG.GEN_VSYNC_POLARITY {High} CONFIG.GEN_AVIDEO_POLARITY {High}] [get_bd_cells screen_vtc]
set_property -dict [list CONFIG.PRIM_SOURCE {No_buffer} CONFIG.PRIM_IN_FREQ {100} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {33.3} CONFIG.USE_LOCKED {true} CONFIG.USE_RESET {true} CONFIG.RESET_TYPE {ACTIVE_LOW} CONFIG.RESET_PORT {resetn}] [get_bd_cells screen_pixel_clk]
set_property -dict [list CONFIG.C_GPIO_WIDTH {3} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {1} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_TRI_DEFAULT {0x00000002}] [get_bd_cells screen_gpio]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] [get_bd_cells screen_hp1]
set_property -dict [list CONFIG.C_SIZE {1} CONFIG.C_OPERATION {and}] [get_bd_cells screen_reset_gate]
set_property -dict [list CONFIG.C_SIZE {1} CONFIG.C_OPERATION {not}] [get_bd_cells screen_pixel_reset_inv]
# 两个时钟域均异步置复位、三级同步释放，禁止直接以locked释放IP复位。
foreach cell {screen_axi_release screen_pixel_release} {
 set_property -dict [list CONFIG.CDC_TYPE {xpm_cdc_async_rst} CONFIG.DEST_SYNC_FF {3} CONFIG.INIT_SYNC_FF {true} CONFIG.RST_ACTIVE_HIGH {false}] [get_bd_cells $cell]
}
set_property -dict [list CONFIG.CDC_TYPE {xpm_cdc_single} CONFIG.DEST_SYNC_FF {2} CONFIG.SRC_INPUT_REG {false} CONFIG.INIT_SYNC_FF {true}] [get_bd_cells screen_lock_sync]
proc ss_net {src args} {foreach dst $args {connect_bd_net [get_bd_pins $src] [get_bd_pins $dst]}}
proc ss_intf {src dst} {connect_bd_intf_net [get_bd_intf_pins $src] [get_bd_intf_pins $dst]}
ss_intf control_bus/M03_AXI screen_vdma/S_AXI_LITE
ss_intf control_bus/M04_AXI screen_iic/S_AXI
ss_intf control_bus/M05_AXI screen_gpio/S_AXI
ss_intf screen_vdma/M_AXI_MM2S screen_hp1/S00_AXI
ss_intf screen_hp1/M00_AXI ps7/S_AXI_HP1
ss_intf screen_vdma/M_AXIS_MM2S screen_video/video_in
ss_intf screen_vtc/vtiming_out screen_video/vtiming_in
foreach n {03 04 05} {
 ss_net clk_main/clk_out2 control_bus/M${n}_ACLK
 ss_net bus_reset/peripheral_aresetn control_bus/M${n}_ARESETN
}
ss_net clk_main/clk_out2 screen_vdma/s_axi_lite_aclk screen_vdma/m_axi_mm2s_aclk screen_vdma/m_axis_mm2s_aclk screen_iic/s_axi_aclk screen_gpio/s_axi_aclk screen_hp1/ACLK screen_hp1/S00_ACLK screen_hp1/M00_ACLK ps7/S_AXI_HP1_ACLK screen_pixel_clk/clk_in1 screen_video/aclk screen_axi_release/dest_clk screen_lock_sync/dest_clk
ss_net bus_reset/peripheral_aresetn screen_vdma/axi_resetn screen_iic/s_axi_aresetn screen_gpio/s_axi_aresetn screen_hp1/ARESETN screen_hp1/S00_ARESETN screen_hp1/M00_ARESETN screen_pixel_clk/resetn screen_reset_gate/Op1
ss_net screen_pixel_clk/locked screen_reset_gate/Op2
ss_net screen_reset_gate/Res screen_axi_release/src_arst screen_pixel_release/src_arst
ss_net screen_axi_release/dest_arst screen_video/aresetn
ss_net screen_pixel_release/dest_arst screen_vtc/resetn screen_pixel_reset_inv/Op1
ss_net screen_pixel_reset_inv/Res screen_video/vid_io_out_reset
ss_net screen_pixel_clk/clk_out1 screen_vtc/clk screen_video/vid_io_out_clk screen_pixel_release/dest_clk screen_lock_sync/src_clk
ss_net screen_video/vtg_ce screen_vtc/gen_clken
ss_net screen_video/locked screen_lock_sync/src_in
ss_net screen_lock_sync/dest_out screen_gpio/gpio2_io_i
ss_net one/dout screen_video/aclken screen_video/vid_io_out_ce screen_vtc/clken
ss_net zero/dout screen_video/fid
foreach {src name width} {screen_video/vid_data lcd_rgb 24 screen_video/vid_hsync lcd_hs 1 screen_video/vid_vsync lcd_vs 1 screen_video/vid_active_video lcd_de 1 screen_pixel_clk/clk_out1 lcd_clk 1} {
 if {$width > 1} {create_bd_port -dir O -from [expr {$width-1}] -to 0 $name} else {create_bd_port -dir O $name}
 connect_bd_net [get_bd_pins $src] [get_bd_ports $name]
}
make_bd_intf_pins_external [get_bd_intf_pins screen_iic/IIC]
set_property name screen_iic [get_bd_intf_ports IIC_0]
make_bd_intf_pins_external [get_bd_intf_pins screen_gpio/GPIO]
set_property name screen_gpio [get_bd_intf_ports GPIO_0]
assign_bd_address -offset 0x43000000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs screen_vdma/S_AXI_LITE/Reg] -force
assign_bd_address -offset 0x41600000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs screen_iic/S_AXI/Reg] -force
assign_bd_address -offset 0x41200000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs screen_gpio/S_AXI/Reg] -force
assign_bd_address -offset 0x00000000 -range 0x40000000 -target_address_space [get_bd_addr_spaces screen_vdma/Data_MM2S] [get_bd_addr_segs ps7/S_AXI_HP1/HP1_DDR_LOWOCM] -force
}
source [file join $ss_package ps_i2c_integration.tcl]
validate_bd_design
save_bd_design
write_bd_tcl -force [file join $ss_package reports screen-integrated-bd.tcl]
set fp [open [file join $ss_package reports screen-ip-properties.txt] w]
foreach cell [get_bd_cells screen*] {puts $fp "CELL $cell"; foreach p [list_property $cell] {if {[string match CONFIG.* $p] || $p eq "VLNV"} {puts $fp "$p=[get_property $p $cell]"}}}
close $fp
remove_files [get_files -quiet *soundsight_stm32_bd_wrapper.v]
generate_target all $bd
set wrappers [make_wrapper -files $bd -top]
add_files -norecurse $wrappers
add_files -fileset constrs_1 -norecurse [file join $ss_package payload screen_pins.xdc]
update_compile_order -fileset sources_1
