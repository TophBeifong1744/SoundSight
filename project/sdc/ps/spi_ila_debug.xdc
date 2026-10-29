# SoundSight SPI ILA -- generated implementation-only debug constraints.
# probe16=tx.D, probe20=fault_status bits 11:0; all bit lists are LSB first.
create_debug_core u_ss_spi_ila ila
set_property C_DATA_DEPTH 8192 [get_debug_cores u_ss_spi_ila]
set_property C_INPUT_PIPE_STAGES 1 [get_debug_cores u_ss_spi_ila]
set_property C_ADV_TRIGGER true [get_debug_cores u_ss_spi_ila]
set_property C_EN_STRG_QUAL false [get_debug_cores u_ss_spi_ila]
set_property ALL_PROBE_SAME_MU true [get_debug_cores u_ss_spi_ila]
set_property ALL_PROBE_SAME_MU_CNT 2 [get_debug_cores u_ss_spi_ila]
connect_debug_port u_ss_spi_ila/clk [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/clk]]
# probe0: rst_n
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe0]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe0]
connect_debug_port u_ss_spi_ila/probe0 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/rst_n]]
# probe1: cs_sync_2
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe1]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe1]
connect_debug_port u_ss_spi_ila/probe1 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/cs_sync[2]}]]
# probe2: ck_sync_2
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe2]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe2]
connect_debug_port u_ss_spi_ila/probe2 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/ck_sync[2]}]]
# probe3: di_sync_2
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe3]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe3]
connect_debug_port u_ss_spi_ila/probe3 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/di_sync[2]}]]
# probe4: miso
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe4]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe4]
connect_debug_port u_ss_spi_ila/probe4 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/spi_miso]]
# probe5: active
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe5]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe5]
connect_debug_port u_ss_spi_ila/probe5 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/active]]
# probe6: bits_seen
create_debug_port u_ss_spi_ila probe
set_property port_width 6 [get_debug_ports u_ss_spi_ila/probe6]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe6]
connect_debug_port u_ss_spi_ila/probe6 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[3]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[4]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/bits_seen_reg[5]}]]
# probe7: malformed
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe7]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe7]
connect_debug_port u_ss_spi_ila/probe7 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/malformed_reg_n_0]]
# probe8: edge_age
create_debug_port u_ss_spi_ila probe
set_property port_width 4 [get_debug_ports u_ss_spi_ila/probe8]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe8]
connect_debug_port u_ss_spi_ila/probe8 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/edge_age[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/edge_age[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/edge_age[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/edge_age[3]}]]
# probe9: idle_age
create_debug_port u_ss_spi_ila probe
set_property port_width 4 [get_debug_ports u_ss_spi_ila/probe9]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe9]
connect_debug_port u_ss_spi_ila/probe9 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/idle_age[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/idle_age[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/idle_age[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/idle_age[3]}]]
# probe10: address
create_debug_port u_ss_spi_ila probe
set_property port_width 7 [get_debug_ports u_ss_spi_ila/probe10]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe10]
connect_debug_port u_ss_spi_ila/probe10 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/address[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/address[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/address[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/Q[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/Q[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/Q[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/Q[3]}]]
# probe11: write_access
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe11]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe11]
connect_debug_port u_ss_spi_ila/probe11 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/write_access]]
# probe12: commit
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe12]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe12]
connect_debug_port u_ss_spi_ila/probe12 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/commit]]
# probe13: format_error
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe13]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe13]
connect_debug_port u_ss_spi_ila/probe13 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/format_error]]
# probe14: write_data
create_debug_port u_ss_spi_ila probe
set_property port_width 32 [get_debug_ports u_ss_spi_ila/probe14]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe14]
connect_debug_port u_ss_spi_ila/probe14 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[3]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[4]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[5]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[6]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[7]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[8]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[9]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[10]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[11]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[12]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[13]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[14]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[15]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[16]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[17]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[18]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[19]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[20]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[21]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[22]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[23]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[24]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[25]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[26]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[27]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[28]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[29]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[30]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/write_data_reg[31]_0[31]}]]
# probe15: pair_select
create_debug_port u_ss_spi_ila probe
set_property port_width 3 [get_debug_ports u_ss_spi_ila/probe15]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe15]
connect_debug_port u_ss_spi_ila/probe15 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/pair_select_reg[0]_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/pair_select_reg[1]_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/pair_select_reg[2]_0}]]
# probe16: tx_d
create_debug_port u_ss_spi_ila probe
set_property port_width 32 [get_debug_ports u_ss_spi_ila/probe16]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe16]
connect_debug_port u_ss_spi_ila/probe16 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[0]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[1]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[2]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[3]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[4]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[5]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[6]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[7]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[8]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[9]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[10]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[11]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[12]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[13]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[14]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[15]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[16]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[17]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[18]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[19]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[20]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[21]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[22]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[23]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[24]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[25]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[26]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[27]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[28]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[29]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[30]_i_1_n_0}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx[31]_i_2_n_0}]]
# probe17: read_pending
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe17]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe17]
connect_debug_port u_ss_spi_ila/probe17 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/read_pending_reg_n_0]]
# probe18: tx
create_debug_port u_ss_spi_ila probe
set_property port_width 32 [get_debug_ports u_ss_spi_ila/probe18]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe18]
connect_debug_port u_ss_spi_ila/probe18 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[3]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[4]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[5]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[6]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[7]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[8]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[9]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[10]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[11]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[12]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[13]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[14]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[15]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[16]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[17]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[18]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[19]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[20]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[21]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[22]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[23]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[24]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[25]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[26]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[27]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[28]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[29]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/tx_reg_n_0_[30]}] [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/p_1_in]]
# probe19: rx
create_debug_port u_ss_spi_ila probe
set_property port_width 32 [get_debug_ports u_ss_spi_ila/probe19]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe19]
connect_debug_port u_ss_spi_ila/probe19 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[3]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[4]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[5]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[6]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[7]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[8]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[9]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[10]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[11]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[12]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[13]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[14]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[15]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[16]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[17]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[18]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[19]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[20]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[21]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[22]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[23]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[24]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[25]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[26]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[27]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[28]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[29]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[30]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/spi/rx[31]}]]
# probe20: fault_status_11_0
create_debug_port u_ss_spi_ila probe
set_property port_width 12 [get_debug_ports u_ss_spi_ila/probe20]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe20]
connect_debug_port u_ss_spi_ila/probe20 [list [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[0]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[1]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[2]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[3]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[4]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[5]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[6]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[7]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[8]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg_n_0_[9]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[9]}] [get_nets {soundsight_stm32_bd_i/link/inst/u_core/registers/faults_reg[11]_0[10]}]]
# probe21: register_error
create_debug_port u_ss_spi_ila probe
set_property port_width 1 [get_debug_ports u_ss_spi_ila/probe21]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ss_spi_ila/probe21]
connect_debug_port u_ss_spi_ila/probe21 [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/registers/register_error_reg_0]]
set_property C_CLK_INPUT_FREQ_HZ 61440000 [get_debug_cores dbg_hub]
set_property C_ENABLE_CLK_DIVIDER false [get_debug_cores dbg_hub]
set_property C_USER_SCAN_CHAIN 1 [get_debug_cores dbg_hub]
connect_debug_port dbg_hub/clk [list [get_nets soundsight_stm32_bd_i/link/inst/u_core/spi/clk]]
