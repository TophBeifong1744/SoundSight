# PS FCLK100 → Clocking Wizard：96MHz中间频率 + 100MHz计算/AXI。
# 第二个Wizard：96 → 61.44MHz采集/公共控制，保持SPI ABI及看门狗单位。
# 不装入任何DDR/MIO板级preset；实际PS板级配置由用户填写。
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7
set_property -dict [list CONFIG.PCW_EN_CLK0_PORT 1 CONFIG.PCW_EN_RST0_PORT 1 CONFIG.PCW_EN_RST1_PORT 1 CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 100] [get_bd_cells ps7]
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR] [get_bd_intf_pins ps7/FIXED_IO]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] [get_bd_cells zero]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] [get_bd_cells one]
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_main
set_property -dict [list CONFIG.PRIM_SOURCE No_buffer CONFIG.PRIM_IN_FREQ 100.000 CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 96.000 CONFIG.CLKOUT2_USED true CONFIG.CLKOUT2_REQUESTED_OUT_FREQ 100.000 CONFIG.USE_RESET true CONFIG.RESET_TYPE ACTIVE_LOW] [get_bd_cells clk_main]
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_audio
set_property -dict [list CONFIG.PRIM_SOURCE No_buffer CONFIG.PRIM_IN_FREQ 96.000 CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 61.440 CONFIG.USE_RESET true CONFIG.RESET_TYPE ACTIVE_LOW] [get_bd_cells clk_audio]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins clk_main/clk_in1]
# RESET0_N只复位PS总线；RESET1_N为显式平台冷复位及失锁后恢复入口。
connect_bd_net [get_bd_pins ps7/FCLK_RESET1_N] [get_bd_pins clk_main/resetn]
connect_bd_net [get_bd_pins clk_main/clk_out1] [get_bd_pins clk_audio/clk_in1]
connect_bd_net [get_bd_pins clk_main/locked] [get_bd_pins clk_audio/resetn]
foreach {name clock} {core_reset clk_main/clk_out2 io_reset clk_audio/clk_out1} {
 create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 $name
 connect_bd_net [get_bd_pins $clock] [get_bd_pins $name/slowest_sync_clk]
 connect_bd_net [get_bd_pins clk_audio/locked] [get_bd_pins $name/dcm_locked]
 # 当前IP生成的ext/aux均低有效，闲置必须接1；debug高有效接0。
 connect_bd_net [get_bd_pins ps7/FCLK_RESET1_N] [get_bd_pins $name/ext_reset_in]
 connect_bd_net [get_bd_pins one/dout] [get_bd_pins $name/aux_reset_in]
 connect_bd_net [get_bd_pins zero/dout] [get_bd_pins $name/mb_debug_sys_rst]
}
foreach {name clock} {core clk_main/clk_out2 io clk_audio/clk_out1} {
 # Processor System Reset在目标时钟停掉时未必立即撤销输出。
 # 锁定信号经官方逻辑IP合入异步复位，再由XPM复位IP在本域同步释放。
 create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 ${name}_reset_gate
 set_property -dict [list CONFIG.C_SIZE 1 CONFIG.C_OPERATION and] [get_bd_cells ${name}_reset_gate]
 create_bd_cell -type ip -vlnv xilinx.com:ip:xpm_cdc_gen:1.0 ${name}_release
 set_property -dict [list CONFIG.CDC_TYPE xpm_cdc_async_rst CONFIG.DEST_SYNC_FF 3 CONFIG.INIT_SYNC_FF true CONFIG.RST_ACTIVE_HIGH false] [get_bd_cells ${name}_release]
 connect_bd_net [get_bd_pins ${name}_reset/peripheral_aresetn] [get_bd_pins ${name}_reset_gate/Op1]
 connect_bd_net [get_bd_pins clk_audio/locked] [get_bd_pins ${name}_reset_gate/Op2]
 connect_bd_net [get_bd_pins ${name}_reset_gate/Res] [get_bd_pins ${name}_release/src_arst]
 connect_bd_net [get_bd_pins $clock] [get_bd_pins ${name}_release/dest_clk]
}
connect_bd_net [get_bd_pins clk_main/clk_out2] [get_bd_pins compute/clk]
connect_bd_net [get_bd_pins core_release/dest_arst] [get_bd_pins compute/rst_n]
connect_bd_net [get_bd_pins clk_audio/clk_out1] [get_bd_pins compute/io_clk]
connect_bd_net [get_bd_pins io_release/dest_arst] [get_bd_pins compute/io_rst_n]
