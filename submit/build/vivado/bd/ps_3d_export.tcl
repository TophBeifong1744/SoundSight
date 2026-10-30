# Actual user-exported 3-D PS/BD/IP configuration. Vivado 2025.2.
# Define only; caller creates the BD and adds the repository RTL/FFT IP first.
proc ss_create_ps_3d_export { parentCell } {

  variable script_folder
  variable design_name

  if { $parentCell eq "" } {
     set parentCell [get_bd_cells /]
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj


  # Create interface ports
  set DDR [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:ddrx_rtl:1.0 DDR ]

  set FIXED_IO [ create_bd_intf_port -mode Master -vlnv xilinx.com:display_processing_system7:fixedio_rtl:1.0 FIXED_IO ]


  # Create ports
  set pdm_clocks [ create_bd_port -dir O -from 3 -to 0 pdm_clocks ]
  set pdm_data [ create_bd_port -dir I -from 3 -to 0 pdm_data ]
  set servo_pwm [ create_bd_port -dir O servo_pwm ]
  set servo_vertical_pwm [ create_bd_port -dir O servo_vertical_pwm ]

  # Create instance: ps7, and set properties
  set ps7 [ create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7 ]
  set_property -dict [list \
    CONFIG.PCW_ACT_APU_PERIPHERAL_FREQMHZ {666.666687} \
    CONFIG.PCW_ACT_CAN_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_DCI_PERIPHERAL_FREQMHZ {10.158730} \
    CONFIG.PCW_ACT_ENET0_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_ENET1_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ {100.000000} \
    CONFIG.PCW_ACT_FPGA1_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_FPGA2_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_FPGA3_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_PCAP_PERIPHERAL_FREQMHZ {200.000000} \
    CONFIG.PCW_ACT_QSPI_PERIPHERAL_FREQMHZ {200.000000} \
    CONFIG.PCW_ACT_SDIO_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_SMC_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_SPI_PERIPHERAL_FREQMHZ {10.000000} \
    CONFIG.PCW_ACT_TPIU_PERIPHERAL_FREQMHZ {200.000000} \
    CONFIG.PCW_ACT_TTC0_CLK0_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_TTC0_CLK1_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_TTC0_CLK2_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_TTC1_CLK0_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_TTC1_CLK1_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_TTC1_CLK2_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_ACT_UART_PERIPHERAL_FREQMHZ {100.000000} \
    CONFIG.PCW_ACT_WDT_PERIPHERAL_FREQMHZ {111.111115} \
    CONFIG.PCW_CLK0_FREQ {100000000} \
    CONFIG.PCW_CLK1_FREQ {10000000} \
    CONFIG.PCW_CLK2_FREQ {10000000} \
    CONFIG.PCW_CLK3_FREQ {10000000} \
    CONFIG.PCW_DDR_RAM_HIGHADDR {0x3FFFFFFF} \
    CONFIG.PCW_EN_EMIO_UART0 {0} \
    CONFIG.PCW_EN_QSPI {1} \
    CONFIG.PCW_EN_RST0_PORT {1} \
    CONFIG.PCW_EN_RST1_PORT {1} \
    CONFIG.PCW_EN_UART0 {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_FPGA_FCLK0_ENABLE {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
    CONFIG.PCW_MIO_14_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_14_PULLUP {enabled} \
    CONFIG.PCW_MIO_14_SLEW {slow} \
    CONFIG.PCW_MIO_15_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_15_PULLUP {enabled} \
    CONFIG.PCW_MIO_15_SLEW {slow} \
    CONFIG.PCW_MIO_1_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_1_PULLUP {enabled} \
    CONFIG.PCW_MIO_1_SLEW {slow} \
    CONFIG.PCW_MIO_2_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_2_SLEW {slow} \
    CONFIG.PCW_MIO_3_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_3_SLEW {slow} \
    CONFIG.PCW_MIO_4_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_4_SLEW {slow} \
    CONFIG.PCW_MIO_5_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_5_SLEW {slow} \
    CONFIG.PCW_MIO_6_IOTYPE {LVCMOS 3.3V} \
    CONFIG.PCW_MIO_6_SLEW {slow} \
    CONFIG.PCW_MIO_TREE_PERIPHERALS {unassigned#Quad SPI Flash#Quad SPI Flash#Quad SPI Flash#Quad SPI Flash#Quad SPI Flash#Quad SPI Flash#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#UART\
0#UART 0#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned}\
\
    CONFIG.PCW_MIO_TREE_SIGNALS {unassigned#qspi0_ss_b#qspi0_io[0]#qspi0_io[1]#qspi0_io[2]#qspi0_io[3]/HOLD_B#qspi0_sclk#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#rx#tx#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned}\
\
    CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 1.8V} \
    CONFIG.PCW_QSPI_GRP_FBCLK_ENABLE {0} \
    CONFIG.PCW_QSPI_GRP_IO1_ENABLE {0} \
    CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE {1} \
    CONFIG.PCW_QSPI_GRP_SINGLE_SS_IO {MIO 1 .. 6} \
    CONFIG.PCW_QSPI_GRP_SS1_ENABLE {0} \
    CONFIG.PCW_QSPI_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_QSPI_PERIPHERAL_FREQMHZ {200} \
    CONFIG.PCW_QSPI_QSPI_IO {MIO 1 .. 6} \
    CONFIG.PCW_SINGLE_QSPI_DATA_MODE {x4} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_UART0_GRP_FULL_ENABLE {0} \
    CONFIG.PCW_UART0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_UART0_UART0_IO {MIO 14 .. 15} \
    CONFIG.PCW_UART_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_UART_PERIPHERAL_VALID {1} \
    CONFIG.PCW_UIPARAM_ACT_DDR_FREQ_MHZ {533.333374} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41J256M16 RE-125} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
  ] $ps7


  # Create instance: clk_main, and set properties
  set clk_main [ create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_main ]
  set_property -dict [list \
    CONFIG.CLKOUT1_JITTER {138.844} \
    CONFIG.CLKOUT1_PHASE_ERROR {105.461} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {96} \
    CONFIG.CLKOUT2_JITTER {137.681} \
    CONFIG.CLKOUT2_PHASE_ERROR {105.461} \
    CONFIG.CLKOUT2_USED {true} \
    CONFIG.MMCM_CLKFBOUT_MULT_F {9.000} \
    CONFIG.MMCM_CLKOUT0_DIVIDE_F {9.375} \
    CONFIG.MMCM_CLKOUT1_DIVIDE {9} \
    CONFIG.NUM_OUT_CLKS {2} \
    CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.RESET_PORT {resetn} \
    CONFIG.RESET_TYPE {ACTIVE_LOW} \
  ] $clk_main


  # Create instance: clk_audio, and set properties
  set clk_audio [ create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_audio ]
  set_property -dict [list \
    CONFIG.CLKIN1_JITTER_PS {104.16} \
    CONFIG.CLKOUT1_DRIVES {BUFG} \
    CONFIG.CLKOUT1_JITTER {266.281} \
    CONFIG.CLKOUT1_PHASE_ERROR {318.150} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {61.44} \
    CONFIG.CLKOUT2_DRIVES {BUFG} \
    CONFIG.CLKOUT3_DRIVES {BUFG} \
    CONFIG.CLKOUT4_DRIVES {BUFG} \
    CONFIG.CLKOUT5_DRIVES {BUFG} \
    CONFIG.CLKOUT6_DRIVES {BUFG} \
    CONFIG.CLKOUT7_DRIVES {BUFG} \
    CONFIG.FEEDBACK_SOURCE {FDBK_AUTO} \
    CONFIG.MMCM_CLKFBOUT_MULT_F {52.000} \
    CONFIG.MMCM_CLKIN1_PERIOD {10.417} \
    CONFIG.MMCM_CLKOUT0_DIVIDE_F {16.250} \
    CONFIG.MMCM_DIVCLK_DIVIDE {5} \
    CONFIG.PRIM_IN_FREQ {96} \
    CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.RESET_PORT {resetn} \
    CONFIG.RESET_TYPE {ACTIVE_LOW} \
    CONFIG.USE_SAFE_CLOCK_STARTUP {false} \
  ] $clk_audio


  # Create instance: core_reset, and set properties
  set core_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 core_reset ]

  # Create instance: io_reset, and set properties
  set io_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 io_reset ]

  # Create instance: core_reset_gate, and set properties
  set core_reset_gate [ create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 core_reset_gate ]
  set_property CONFIG.C_SIZE {1} $core_reset_gate


  # Create instance: io_reset_gate, and set properties
  set io_reset_gate [ create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 io_reset_gate ]
  set_property CONFIG.C_SIZE {1} $io_reset_gate


  # Create instance: core_release, and set properties
  set core_release [ create_bd_cell -type ip -vlnv xilinx.com:ip:xpm_cdc_gen:1.0 core_release ]
  set_property -dict [list \
    CONFIG.CDC_TYPE {xpm_cdc_async_rst} \
    CONFIG.DEST_SYNC_FF {3} \
    CONFIG.INIT_SYNC_FF {true} \
    CONFIG.RST_ACTIVE_HIGH {false} \
  ] $core_release


  # Create instance: io_release, and set properties
  set io_release [ create_bd_cell -type ip -vlnv xilinx.com:ip:xpm_cdc_gen:1.0 io_release ]
  set_property -dict [list \
    CONFIG.CDC_TYPE {xpm_cdc_async_rst} \
    CONFIG.DEST_SYNC_FF {3} \
    CONFIG.INIT_SYNC_FF {true} \
  ] $io_release


  # Create instance: zero, and set properties
  set zero [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero ]
  set_property CONFIG.CONST_VAL {0} $zero


  # Create instance: one, and set properties
  set one [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one ]

  # Create instance: compute, and set properties
  set block_name bd_clean_compute
  set block_cell_name compute
  if { [catch {set compute [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $compute eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
    set_property -dict [list \
    CONFIG.AUDIO_ENABLE {1} \
    CONFIG.LEVEL_ENABLE {1} \
  ] $compute


  # Create instance: ps_link, and set properties
  set block_name bd_ps_link
  set block_cell_name ps_link
  if { [catch {set ps_link [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $ps_link eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
    set_property -dict [list \
    CONFIG.ACTUATOR_BOUND {1} \
    CONFIG.AUDIO_ENABLE {1} \
    CONFIG.CLK_FREQ_HZ {61440000} \
    CONFIG.DUAL_AXIS_ENABLE {1} \
    CONFIG.LEVEL_ENABLE {1} \
    CONFIG.MECHANICAL_MAX {360} \
    CONFIG.MECHANICAL_MIN {0} \
    CONFIG.SERVO_MAX {360} \
  ] $ps_link


  # Create instance: control_bus, and set properties
  set control_bus [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control_bus ]
  set_property -dict [list \
    CONFIG.NUM_MI {3} \
    CONFIG.NUM_SI {1} \
  ] $control_bus


  # Create instance: control_cdc, and set properties
  set control_cdc [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 control_cdc ]
  set_property -dict [list \
    CONFIG.ACLK_ASYNC {1} \
    CONFIG.DATA_WIDTH {32} \
    CONFIG.PROTOCOL {AXI4LITE} \
    CONFIG.SYNCHRONIZATION_STAGES {3} \
  ] $control_cdc


  # Create instance: bus_reset, and set properties
  set bus_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 bus_reset ]
  set_property CONFIG.C_AUX_RESET_HIGH {0} $bus_reset


  # Create instance: bus_io_reset, and set properties
  set bus_io_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 bus_io_reset ]
  set_property CONFIG.C_AUX_RESET_HIGH {0} $bus_io_reset


  # Create instance: irq_concat, and set properties
  set irq_concat [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 irq_concat ]
  set_property -dict [list \
    CONFIG.IN0_WIDTH {1} \
    CONFIG.IN1_WIDTH {1} \
    CONFIG.IN2_WIDTH {14} \
    CONFIG.NUM_PORTS {3} \
  ] $irq_concat


  # Create instance: irq_zero, and set properties
  set irq_zero [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 irq_zero ]
  set_property -dict [list \
    CONFIG.CONST_VAL {0} \
    CONFIG.CONST_WIDTH {14} \
  ] $irq_zero


  # Create instance: audio_capture, and set properties
  set block_name bd_audio_capture
  set block_cell_name audio_capture
  if { [catch {set audio_capture [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $audio_capture eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
  
  # Create instance: axi_dma_audio, and set properties
  set axi_dma_audio [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_audio ]
  set_property -dict [list \
    CONFIG.c_include_mm2s {0} \
    CONFIG.c_include_s2mm {1} \
    CONFIG.c_include_s2mm_dre {0} \
    CONFIG.c_include_sg {0} \
    CONFIG.c_m_axi_s2mm_data_width {64} \
    CONFIG.c_micro_dma {0} \
    CONFIG.c_s2mm_burst_size {16} \
    CONFIG.c_s_axis_s2mm_tdata_width {32} \
    CONFIG.c_sg_length_width {16} \
  ] $axi_dma_audio


  # Create instance: audio_mem_bus, and set properties
  set audio_mem_bus [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 audio_mem_bus ]
  set_property -dict [list \
    CONFIG.NUM_MI {1} \
    CONFIG.NUM_SI {1} \
  ] $audio_mem_bus


  # Create interface connections
  connect_bd_intf_net -intf_net audio_capture_M_AXIS [get_bd_intf_pins audio_capture/M_AXIS] [get_bd_intf_pins axi_dma_audio/S_AXIS_S2MM]
  connect_bd_intf_net -intf_net audio_mem_bus_M00_AXI [get_bd_intf_pins audio_mem_bus/M00_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
  connect_bd_intf_net -intf_net axi_dma_audio_M_AXI_S2MM [get_bd_intf_pins axi_dma_audio/M_AXI_S2MM] [get_bd_intf_pins audio_mem_bus/S00_AXI]
  connect_bd_intf_net -intf_net control_bus_M00_AXI [get_bd_intf_pins control_bus/M00_AXI] [get_bd_intf_pins control_cdc/S_AXI]
  connect_bd_intf_net -intf_net control_bus_M01_AXI [get_bd_intf_pins control_bus/M01_AXI] [get_bd_intf_pins axi_dma_audio/S_AXI_LITE]
  connect_bd_intf_net -intf_net control_bus_M02_AXI [get_bd_intf_pins control_bus/M02_AXI] [get_bd_intf_pins audio_capture/S_AXI]
  connect_bd_intf_net -intf_net control_cdc_M_AXI [get_bd_intf_pins control_cdc/M_AXI] [get_bd_intf_pins ps_link/S_AXI]
  connect_bd_intf_net -intf_net processing_system7_0_DDR [get_bd_intf_ports DDR] [get_bd_intf_pins ps7/DDR]
  connect_bd_intf_net -intf_net processing_system7_0_FIXED_IO [get_bd_intf_ports FIXED_IO] [get_bd_intf_pins ps7/FIXED_IO]
  connect_bd_intf_net -intf_net ps7_M_AXI_GP0 [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control_bus/S00_AXI]

  # Create port connections
  connect_bd_net -net audio_capture_active  [get_bd_pins audio_capture/active] \
  [get_bd_pins compute/audio_active]
  connect_bd_net -net audio_capture_epoch  [get_bd_pins audio_capture/epoch] \
  [get_bd_pins compute/audio_epoch]
  connect_bd_net -net axi_dma_audio_s2mm_introut  [get_bd_pins axi_dma_audio/s2mm_introut] \
  [get_bd_pins irq_concat/In1]
  connect_bd_net -net axi_dma_audio_s2mm_prmry_reset_out_n  [get_bd_pins axi_dma_audio/s2mm_prmry_reset_out_n] \
  [get_bd_pins audio_capture/dma_resetn]
  connect_bd_net -net bus_io_reset_peripheral_aresetn  [get_bd_pins bus_io_reset/peripheral_aresetn] \
  [get_bd_pins control_cdc/m_axi_aresetn] \
  [get_bd_pins ps_link/aresetn]
  connect_bd_net -net bus_reset_interconnect_aresetn  [get_bd_pins bus_reset/interconnect_aresetn] \
  [get_bd_pins control_bus/ARESETN] \
  [get_bd_pins audio_mem_bus/ARESETN]
  connect_bd_net -net bus_reset_peripheral_aresetn  [get_bd_pins bus_reset/peripheral_aresetn] \
  [get_bd_pins control_bus/S00_ARESETN] \
  [get_bd_pins control_bus/M00_ARESETN] \
  [get_bd_pins control_cdc/s_axi_aresetn] \
  [get_bd_pins control_bus/M01_ARESETN] \
  [get_bd_pins control_bus/M02_ARESETN] \
  [get_bd_pins axi_dma_audio/axi_resetn] \
  [get_bd_pins audio_mem_bus/S00_ARESETN] \
  [get_bd_pins audio_mem_bus/M00_ARESETN] \
  [get_bd_pins audio_capture/aresetn]
  connect_bd_net -net clk_audio_clk_out1  [get_bd_pins clk_audio/clk_out1] \
  [get_bd_pins io_release/dest_clk] \
  [get_bd_pins io_reset/slowest_sync_clk] \
  [get_bd_pins control_cdc/m_axi_aclk] \
  [get_bd_pins bus_io_reset/slowest_sync_clk] \
  [get_bd_pins compute/io_clk] \
  [get_bd_pins ps_link/clk]
  connect_bd_net -net clk_audio_locked  [get_bd_pins clk_audio/locked] \
  [get_bd_pins core_reset/dcm_locked] \
  [get_bd_pins io_reset/dcm_locked] \
  [get_bd_pins core_reset_gate/Op2] \
  [get_bd_pins io_reset_gate/Op2] \
  [get_bd_pins bus_reset/dcm_locked] \
  [get_bd_pins bus_io_reset/dcm_locked]
  connect_bd_net -net clk_main_clk_out1  [get_bd_pins clk_main/clk_out1] \
  [get_bd_pins clk_audio/clk_in1]
  connect_bd_net -net clk_main_clk_out2  [get_bd_pins clk_main/clk_out2] \
  [get_bd_pins core_reset/slowest_sync_clk] \
  [get_bd_pins core_release/dest_clk] \
  [get_bd_pins ps7/M_AXI_GP0_ACLK] \
  [get_bd_pins control_bus/ACLK] \
  [get_bd_pins control_bus/S00_ACLK] \
  [get_bd_pins control_bus/M00_ACLK] \
  [get_bd_pins control_cdc/s_axi_aclk] \
  [get_bd_pins bus_reset/slowest_sync_clk] \
  [get_bd_pins control_bus/M01_ACLK] \
  [get_bd_pins control_bus/M02_ACLK] \
  [get_bd_pins axi_dma_audio/s_axi_lite_aclk] \
  [get_bd_pins axi_dma_audio/m_axi_s2mm_aclk] \
  [get_bd_pins audio_mem_bus/ACLK] \
  [get_bd_pins audio_mem_bus/S00_ACLK] \
  [get_bd_pins audio_mem_bus/M00_ACLK] \
  [get_bd_pins ps7/S_AXI_HP0_ACLK] \
  [get_bd_pins compute/clk] \
  [get_bd_pins audio_capture/clk]
  connect_bd_net -net clk_main_locked  [get_bd_pins clk_main/locked] \
  [get_bd_pins clk_audio/resetn]
  connect_bd_net -net compute_audio_clip  [get_bd_pins compute/audio_clip] \
  [get_bd_pins audio_capture/pcm_clip]
  connect_bd_net -net compute_audio_draining  [get_bd_pins compute/audio_draining] \
  [get_bd_pins audio_capture/compute_draining]
  connect_bd_net -net compute_audio_pcm  [get_bd_pins compute/audio_pcm] \
  [get_bd_pins audio_capture/pcm]
  connect_bd_net -net compute_audio_run  [get_bd_pins compute/audio_run] \
  [get_bd_pins audio_capture/run_enable]
  connect_bd_net -net compute_audio_sample_index  [get_bd_pins compute/audio_sample_index] \
  [get_bd_pins audio_capture/sample_index]
  connect_bd_net -net compute_audio_source_fault  [get_bd_pins compute/audio_source_fault] \
  [get_bd_pins audio_capture/pcm_fault]
  connect_bd_net -net compute_audio_valid  [get_bd_pins compute/audio_valid] \
  [get_bd_pins audio_capture/pcm_valid]
  connect_bd_net -net compute_draining  [get_bd_pins compute/draining] \
  [get_bd_pins ps_link/compute_draining]
  connect_bd_net -net compute_feature_flags  [get_bd_pins compute/feature_flags] \
  [get_bd_pins ps_link/feature_flags]
  connect_bd_net -net compute_feature_level  [get_bd_pins compute/feature_level] \
  [get_bd_pins ps_link/feature_level]
  connect_bd_net -net compute_feature_level_valid  [get_bd_pins compute/feature_level_valid] \
  [get_bd_pins ps_link/feature_level_valid]
  connect_bd_net -net compute_feature_meta  [get_bd_pins compute/feature_meta] \
  [get_bd_pins ps_link/feature_meta]
  connect_bd_net -net compute_feature_pairs  [get_bd_pins compute/feature_pairs] \
  [get_bd_pins ps_link/feature_pairs]
  connect_bd_net -net compute_feature_valid  [get_bd_pins compute/feature_valid] \
  [get_bd_pins ps_link/feature_valid]
  connect_bd_net -net compute_pdm_clocks  [get_bd_pins compute/pdm_clocks] \
  [get_bd_ports pdm_clocks]
  connect_bd_net -net compute_source_faults  [get_bd_pins compute/source_faults] \
  [get_bd_pins ps_link/source_faults]
  connect_bd_net -net core_release_dest_arst  [get_bd_pins core_release/dest_arst] \
  [get_bd_pins compute/rst_n] \
  [get_bd_pins audio_capture/rst_n]
  connect_bd_net -net core_reset_gate_Res  [get_bd_pins core_reset_gate/Res] \
  [get_bd_pins core_release/src_arst]
  connect_bd_net -net core_reset_peripheral_aresetn  [get_bd_pins core_reset/peripheral_aresetn] \
  [get_bd_pins core_reset_gate/Op1]
  connect_bd_net -net io_release_dest_arst  [get_bd_pins io_release/dest_arst] \
  [get_bd_pins compute/io_rst_n] \
  [get_bd_pins ps_link/rst_n]
  connect_bd_net -net io_reset_gate_Res  [get_bd_pins io_reset_gate/Res] \
  [get_bd_pins io_release/src_arst]
  connect_bd_net -net io_reset_peripheral_aresetn  [get_bd_pins io_reset/peripheral_aresetn] \
  [get_bd_pins io_reset_gate/Op1]
  connect_bd_net -net irq_concat_dout  [get_bd_pins irq_concat/dout] \
  [get_bd_pins ps7/IRQ_F2P]
  connect_bd_net -net irq_zero_dout  [get_bd_pins irq_zero/dout] \
  [get_bd_pins irq_concat/In2]
  connect_bd_net -net one_dout  [get_bd_pins one/dout] \
  [get_bd_pins core_reset/aux_reset_in] \
  [get_bd_pins io_reset/aux_reset_in] \
  [get_bd_pins bus_reset/aux_reset_in] \
  [get_bd_pins bus_io_reset/aux_reset_in]
  connect_bd_net -net pdm_data_0_1  [get_bd_ports pdm_data] \
  [get_bd_pins compute/pdm_data]
  connect_bd_net -net ps7_FCLK_CLK0  [get_bd_pins ps7/FCLK_CLK0] \
  [get_bd_pins clk_main/clk_in1]
  connect_bd_net -net ps7_FCLK_RESET0_N  [get_bd_pins ps7/FCLK_RESET0_N] \
  [get_bd_pins bus_reset/ext_reset_in] \
  [get_bd_pins bus_io_reset/ext_reset_in]
  connect_bd_net -net ps7_FCLK_RESET1_N  [get_bd_pins ps7/FCLK_RESET1_N] \
  [get_bd_pins clk_main/resetn] \
  [get_bd_pins core_reset/ext_reset_in] \
  [get_bd_pins io_reset/ext_reset_in]
  connect_bd_net -net ps_link_feature_ready  [get_bd_pins ps_link/feature_ready] \
  [get_bd_pins compute/feature_ready]
  connect_bd_net -net ps_link_irq  [get_bd_pins ps_link/irq] \
  [get_bd_pins irq_concat/In0]
  connect_bd_net -net ps_link_run_enable  [get_bd_pins ps_link/run_enable] \
  [get_bd_pins compute/enable]
  connect_bd_net -net ps_link_servo_pwm  [get_bd_pins ps_link/servo_pwm] \
  [get_bd_ports servo_pwm]
  connect_bd_net -net ps_link_servo_vertical_pwm  [get_bd_pins ps_link/servo_vertical_pwm] \
  [get_bd_ports servo_vertical_pwm]
  connect_bd_net -net zero_dout  [get_bd_pins zero/dout] \
  [get_bd_pins io_reset/mb_debug_sys_rst] \
  [get_bd_pins core_reset/mb_debug_sys_rst] \
  [get_bd_pins bus_reset/mb_debug_sys_rst] \
  [get_bd_pins bus_io_reset/mb_debug_sys_rst]

  # Create address segments
  assign_bd_address -offset 0x43C00000 -range 0x00001000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs audio_capture/S_AXI/reg0] -force
  assign_bd_address -offset 0x40400000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs axi_dma_audio/S_AXI_LITE/Reg] -force
  assign_bd_address -offset 0x40000000 -range 0x00001000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs ps_link/S_AXI/reg0] -force
  assign_bd_address -offset 0x00000000 -range 0x40000000 -target_address_space [get_bd_addr_spaces axi_dma_audio/Data_S2MM] [get_bd_addr_segs ps7/S_AXI_HP0/HP0_DDR_LOWOCM] -force


  # Restore current instance
  current_bd_instance $oldCurInst

  validate_bd_design
  save_bd_design
}

