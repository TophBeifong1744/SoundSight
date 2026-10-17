create_bd_design soundsight_ps_bd
create_bd_cell -type module -reference bd_clean_compute compute
create_bd_cell -type module -reference bd_ps_link ps_link
source [file join $ss_root project ip create_platform_clock.tcl]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 CONFIG.PCW_USE_FABRIC_INTERRUPT 1 CONFIG.PCW_IRQ_F2P_INTR 1] [get_bd_cells ps7]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control_bus
set_property CONFIG.NUM_MI 1 [get_bd_cells control_bus]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 control_cdc
set_property -dict [list CONFIG.PROTOCOL AXI4LITE CONFIG.ACLK_ASYNC 1 CONFIG.SYNCHRONIZATION_STAGES 3] [get_bd_cells control_cdc]
# PS总线复位分两域同步释放；不接存储/计算冷复位。
foreach {name clock} {bus_reset clk_main/clk_out2 bus_io_reset clk_audio/clk_out1} {
 create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 $name
 connect_bd_net [get_bd_pins $clock] [get_bd_pins $name/slowest_sync_clk]
 connect_bd_net [get_bd_pins clk_audio/locked] [get_bd_pins $name/dcm_locked]
 connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins $name/ext_reset_in]
 connect_bd_net [get_bd_pins one/dout] [get_bd_pins $name/aux_reset_in]
 connect_bd_net [get_bd_pins zero/dout] [get_bd_pins $name/mb_debug_sys_rst]
}
connect_bd_net [get_bd_pins clk_main/clk_out2] [get_bd_pins ps7/M_AXI_GP0_ACLK] [get_bd_pins control_bus/ACLK] [get_bd_pins control_bus/S00_ACLK] [get_bd_pins control_bus/M00_ACLK] [get_bd_pins control_cdc/s_axi_aclk]
connect_bd_net [get_bd_pins clk_audio/clk_out1] [get_bd_pins control_cdc/m_axi_aclk] [get_bd_pins ps_link/clk]
connect_bd_net [get_bd_pins io_release/dest_arst] [get_bd_pins ps_link/rst_n]
connect_bd_net [get_bd_pins bus_reset/interconnect_aresetn] [get_bd_pins control_bus/ARESETN]
connect_bd_net [get_bd_pins bus_reset/peripheral_aresetn] [get_bd_pins control_bus/S00_ARESETN] [get_bd_pins control_bus/M00_ARESETN] [get_bd_pins control_cdc/s_axi_aresetn]
connect_bd_net [get_bd_pins bus_io_reset/peripheral_aresetn] [get_bd_pins control_cdc/m_axi_aresetn] [get_bd_pins ps_link/aresetn]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control_bus/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_bus/M00_AXI] [get_bd_intf_pins control_cdc/S_AXI]
connect_bd_intf_net [get_bd_intf_pins control_cdc/M_AXI] [get_bd_intf_pins ps_link/S_AXI]
foreach pin {feature_valid feature_pairs feature_flags source_faults} {connect_bd_net [get_bd_pins compute/$pin] [get_bd_pins ps_link/$pin]}
connect_bd_net [get_bd_pins ps_link/feature_ready] [get_bd_pins compute/feature_ready]
connect_bd_net [get_bd_pins ps_link/run_enable] [get_bd_pins compute/enable]
connect_bd_net [get_bd_pins compute/draining] [get_bd_pins ps_link/compute_draining]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 irq_concat
set_property -dict [list CONFIG.NUM_PORTS 2 CONFIG.IN0_WIDTH 1 CONFIG.IN1_WIDTH 15] [get_bd_cells irq_concat]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 irq_zero
set_property -dict [list CONFIG.CONST_WIDTH 15 CONFIG.CONST_VAL 0] [get_bd_cells irq_zero]
connect_bd_net [get_bd_pins ps_link/irq] [get_bd_pins irq_concat/In0]
connect_bd_net [get_bd_pins irq_zero/dout] [get_bd_pins irq_concat/In1]
connect_bd_net [get_bd_pins irq_concat/dout] [get_bd_pins ps7/IRQ_F2P]
foreach item {{pdm_data I} {pdm_clocks O}} {
    lassign $item pin direction
    connect_bd_net [create_bd_port -dir $direction -from 3 -to 0 $pin] [get_bd_pins compute/$pin]
}
connect_bd_net [create_bd_port -dir O servo_pwm] [get_bd_pins ps_link/servo_pwm]
assign_bd_address
