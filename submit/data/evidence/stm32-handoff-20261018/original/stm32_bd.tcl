
################################################################
# This is a generated script based on design: soundsight_stm32_bd
#
# Though there are limitations about the generated script,
# the main purpose of this utility is to make learning
# IP Integrator Tcl commands easier.
################################################################

namespace eval _tcl {
proc get_script_folder {} {
   set script_path [file normalize [info script]]
   set script_folder [file dirname $script_path]
   return $script_folder
}
}
variable script_folder
set script_folder [_tcl::get_script_folder]

################################################################
# Check if script is running in correct Vivado version.
################################################################
set scripts_vivado_version 2025.2
set current_vivado_version [version -short]

if { [string first $scripts_vivado_version $current_vivado_version] == -1 } {
   puts ""
   if { [string compare $scripts_vivado_version $current_vivado_version] > 0 } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2042 -severity "ERROR" " This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Sourcing the script failed since it was created with a future version of Vivado."}

   } else {
     catch {common::send_gid_msg -ssname BD::TCL -id 2041 -severity "ERROR" "This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Please run the script in Vivado <$scripts_vivado_version> then open the design in Vivado <$current_vivado_version>. Upgrade the design by running \"Tools => Report => Report IP Status...\", then run write_bd_tcl to create an updated script."}

   }

   return 1
}

################################################################
# START
################################################################

# To test this script, run the following commands from Vivado Tcl console:
# source soundsight_stm32_bd_script.tcl


# The design that will be created by this Tcl script contains the following 
# module references:
# bd_clean_compute, bd_stm32_link

# Please add the sources of those modules before sourcing this Tcl script.

# If there is no project opened, this script will create a
# project, but make sure you do not have an existing project
# <./myproj/project_1.xpr> in the current working folder.

set list_projs [get_projects -quiet]
if { $list_projs eq "" } {
   create_project project_1 myproj -part xc7z020clg400-2
}


# CHANGE DESIGN NAME HERE
variable design_name
set design_name soundsight_stm32_bd

# If you do not already have an existing IP Integrator design open,
# you can create a design using the following command:
#    create_bd_design $design_name

# Creating design if needed
set errMsg ""
set nRet 0

set cur_design [current_bd_design -quiet]
set list_cells [get_bd_cells -quiet]

if { ${design_name} eq "" } {
   # USE CASES:
   #    1) Design_name not set

   set errMsg "Please set the variable <design_name> to a non-empty value."
   set nRet 1

} elseif { ${cur_design} ne "" && ${list_cells} eq "" } {
   # USE CASES:
   #    2): Current design opened AND is empty AND names same.
   #    3): Current design opened AND is empty AND names diff; design_name NOT in project.
   #    4): Current design opened AND is empty AND names diff; design_name exists in project.

   if { $cur_design ne $design_name } {
      common::send_gid_msg -ssname BD::TCL -id 2001 -severity "INFO" "Changing value of <design_name> from <$design_name> to <$cur_design> since current design is empty."
      set design_name [get_property NAME $cur_design]
   }
   common::send_gid_msg -ssname BD::TCL -id 2002 -severity "INFO" "Constructing design in IPI design <$cur_design>..."

} elseif { ${cur_design} ne "" && $list_cells ne "" && $cur_design eq $design_name } {
   # USE CASES:
   #    5) Current design opened AND has components AND same names.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 1
} elseif { [get_files -quiet ${design_name}.bd] ne "" } {
   # USE CASES: 
   #    6) Current opened design, has components, but diff names, design_name exists in project.
   #    7) No opened design, design_name exists in project.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 2

} else {
   # USE CASES:
   #    8) No opened design, design_name not in project.
   #    9) Current opened design, has components, but diff names, design_name not in project.

   common::send_gid_msg -ssname BD::TCL -id 2003 -severity "INFO" "Currently there is no design <$design_name> in project, so creating one..."

   create_bd_design $design_name

   common::send_gid_msg -ssname BD::TCL -id 2004 -severity "INFO" "Making design <$design_name> as current_bd_design."
   current_bd_design $design_name

}

common::send_gid_msg -ssname BD::TCL -id 2005 -severity "INFO" "Currently the variable <design_name> is equal to \"$design_name\"."

if { $nRet != 0 } {
   catch {common::send_gid_msg -ssname BD::TCL -id 2006 -severity "ERROR" $errMsg}
   return $nRet
}

set bCheckIPsPassed 1
##################################################################
# CHECK IPs
##################################################################
set bCheckIPs 1
if { $bCheckIPs == 1 } {
   set list_check_ips "\ 
xilinx.com:ip:processing_system7:5.5\
xilinx.com:ip:clk_wiz:6.0\
xilinx.com:ip:proc_sys_reset:5.0\
xilinx.com:ip:util_vector_logic:2.0\
xilinx.com:ip:xpm_cdc_gen:1.0\
xilinx.com:ip:xlconstant:1.1\
"

   set list_ips_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2011 -severity "INFO" "Checking if the following IPs exist in the project's IP catalog: $list_check_ips ."

   foreach ip_vlnv $list_check_ips {
      set ip_obj [get_ipdefs -all $ip_vlnv]
      if { $ip_obj eq "" } {
         lappend list_ips_missing $ip_vlnv
      }
   }

   if { $list_ips_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2012 -severity "ERROR" "The following IPs are not found in the IP Catalog:\n  $list_ips_missing\n\nResolution: Please add the repository containing the IP(s) to the project." }
      set bCheckIPsPassed 0
   }

}

##################################################################
# CHECK Modules
##################################################################
set bCheckModules 1
if { $bCheckModules == 1 } {
   set list_check_mods "\ 
bd_clean_compute\
bd_stm32_link\
"

   set list_mods_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2020 -severity "INFO" "Checking if the following modules exist in the project's sources: $list_check_mods ."

   foreach mod_vlnv $list_check_mods {
      if { [can_resolve_reference $mod_vlnv] == 0 } {
         lappend list_mods_missing $mod_vlnv
      }
   }

   if { $list_mods_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2021 -severity "ERROR" "The following module(s) are not found in the project: $list_mods_missing" }
      common::send_gid_msg -ssname BD::TCL -id 2022 -severity "INFO" "Please add source files for the missing module(s) above."
      set bCheckIPsPassed 0
   }
}

if { $bCheckIPsPassed != 1 } {
  common::send_gid_msg -ssname BD::TCL -id 2023 -severity "WARNING" "Will not continue with creation of design due to the error(s) above."
  return 3
}

##################################################################
# DESIGN PROCs
##################################################################



# Procedure to create entire design; Provide argument to make
# procedure reusable. If parentCell is "", will use root.
proc create_root_design { parentCell } {

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
  set irq [ create_bd_port -dir O -type intr irq ]
  set servo_pwm [ create_bd_port -dir O servo_pwm ]
  set spi_miso [ create_bd_port -dir O spi_miso ]
  set pdm_data [ create_bd_port -dir I -from 3 -to 0 pdm_data ]
  set spi_cs_n [ create_bd_port -dir I spi_cs_n ]
  set spi_sck [ create_bd_port -dir I spi_sck ]
  set spi_mosi [ create_bd_port -dir I spi_mosi ]

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
    CONFIG.PCW_EN_RST1_PORT {1} \
    CONFIG.PCW_EN_UART0 {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_FPGA_FCLK0_ENABLE {1} \
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
    CONFIG.PCW_UART0_GRP_FULL_ENABLE {0} \
    CONFIG.PCW_UART0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_UART0_UART0_IO {MIO 14 .. 15} \
    CONFIG.PCW_UART_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_UART_PERIPHERAL_VALID {1} \
    CONFIG.PCW_UIPARAM_ACT_DDR_FREQ_MHZ {533.333374} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41J256M16 RE-125} \
    CONFIG.PCW_USE_M_AXI_GP0 {0} \
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
  
  # Create instance: link, and set properties
  set block_name bd_stm32_link
  set block_cell_name link
  if { [catch {set link [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $link eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
  
  # Create interface connections
  connect_bd_intf_net -intf_net processing_system7_0_DDR [get_bd_intf_ports DDR] [get_bd_intf_pins ps7/DDR]
  connect_bd_intf_net -intf_net processing_system7_0_FIXED_IO [get_bd_intf_ports FIXED_IO] [get_bd_intf_pins ps7/FIXED_IO]

  # Create port connections
  connect_bd_net -net clk_audio_clk_out1  [get_bd_pins clk_audio/clk_out1] \
  [get_bd_pins io_release/dest_clk] \
  [get_bd_pins io_reset/slowest_sync_clk] \
  [get_bd_pins compute/io_clk] \
  [get_bd_pins link/clk]
  connect_bd_net -net clk_audio_locked  [get_bd_pins clk_audio/locked] \
  [get_bd_pins core_reset/dcm_locked] \
  [get_bd_pins io_reset/dcm_locked] \
  [get_bd_pins core_reset_gate/Op2] \
  [get_bd_pins io_reset_gate/Op2]
  connect_bd_net -net clk_main_clk_out1  [get_bd_pins clk_main/clk_out1] \
  [get_bd_pins clk_audio/clk_in1]
  connect_bd_net -net clk_main_clk_out2  [get_bd_pins clk_main/clk_out2] \
  [get_bd_pins core_reset/slowest_sync_clk] \
  [get_bd_pins core_release/dest_clk] \
  [get_bd_pins compute/clk]
  connect_bd_net -net clk_main_locked  [get_bd_pins clk_main/locked] \
  [get_bd_pins clk_audio/resetn]
  connect_bd_net -net compute_draining  [get_bd_pins compute/draining] \
  [get_bd_pins link/compute_draining]
  connect_bd_net -net compute_feature_flags  [get_bd_pins compute/feature_flags] \
  [get_bd_pins link/feature_flags]
  connect_bd_net -net compute_feature_pairs  [get_bd_pins compute/feature_pairs] \
  [get_bd_pins link/feature_pairs]
  connect_bd_net -net compute_feature_valid  [get_bd_pins compute/feature_valid] \
  [get_bd_pins link/feature_valid]
  connect_bd_net -net compute_pdm_clocks  [get_bd_pins compute/pdm_clocks] \
  [get_bd_ports pdm_clocks]
  connect_bd_net -net compute_source_faults  [get_bd_pins compute/source_faults] \
  [get_bd_pins link/source_faults]
  connect_bd_net -net core_release_dest_arst  [get_bd_pins core_release/dest_arst] \
  [get_bd_pins compute/rst_n]
  connect_bd_net -net core_reset_gate_Res  [get_bd_pins core_reset_gate/Res] \
  [get_bd_pins core_release/src_arst]
  connect_bd_net -net core_reset_peripheral_aresetn  [get_bd_pins core_reset/peripheral_aresetn] \
  [get_bd_pins core_reset_gate/Op1]
  connect_bd_net -net io_release_dest_arst  [get_bd_pins io_release/dest_arst] \
  [get_bd_pins compute/io_rst_n] \
  [get_bd_pins link/rst_n]
  connect_bd_net -net io_reset_gate_Res  [get_bd_pins io_reset_gate/Res] \
  [get_bd_pins io_release/src_arst]
  connect_bd_net -net io_reset_peripheral_aresetn  [get_bd_pins io_reset/peripheral_aresetn] \
  [get_bd_pins io_reset_gate/Op1]
  connect_bd_net -net link_feature_ready  [get_bd_pins link/feature_ready] \
  [get_bd_pins compute/feature_ready]
  connect_bd_net -net link_irq  [get_bd_pins link/irq] \
  [get_bd_ports irq]
  connect_bd_net -net link_run_enable  [get_bd_pins link/run_enable] \
  [get_bd_pins compute/enable]
  connect_bd_net -net link_servo_pwm  [get_bd_pins link/servo_pwm] \
  [get_bd_ports servo_pwm]
  connect_bd_net -net link_spi_miso  [get_bd_pins link/spi_miso] \
  [get_bd_ports spi_miso]
  connect_bd_net -net one_dout  [get_bd_pins one/dout] \
  [get_bd_pins core_reset/aux_reset_in] \
  [get_bd_pins io_reset/aux_reset_in]
  connect_bd_net -net pdm_data_0_1  [get_bd_ports pdm_data] \
  [get_bd_pins compute/pdm_data]
  connect_bd_net -net ps7_FCLK_CLK0  [get_bd_pins ps7/FCLK_CLK0] \
  [get_bd_pins clk_main/clk_in1]
  connect_bd_net -net ps7_FCLK_RESET1_N  [get_bd_pins ps7/FCLK_RESET1_N] \
  [get_bd_pins clk_main/resetn] \
  [get_bd_pins core_reset/ext_reset_in] \
  [get_bd_pins io_reset/ext_reset_in]
  connect_bd_net -net spi_cs_n_0_1  [get_bd_ports spi_cs_n] \
  [get_bd_pins link/spi_cs_n]
  connect_bd_net -net spi_mosi_0_1  [get_bd_ports spi_mosi] \
  [get_bd_pins link/spi_mosi]
  connect_bd_net -net spi_sck_0_1  [get_bd_ports spi_sck] \
  [get_bd_pins link/spi_sck]
  connect_bd_net -net zero_dout  [get_bd_pins zero/dout] \
  [get_bd_pins io_reset/mb_debug_sys_rst] \
  [get_bd_pins core_reset/mb_debug_sys_rst]

  # Create address segments

  # Perform GUI Layout
  regenerate_bd_layout -layout_string {
   "ActiveEmotionalView":"Default View",
   "Default View_ScaleFactor":"0.453544",
   "Default View_TopLeft":"-165,-287",
   "ExpandedHierarchyInLayout":"",
   "guistr":"# # String gsaved with Nlview 7.8.0 2024-04-26 e1825d835c VDI=44 GEI=38 GUI=JA:21.0
#  -string -flagsOSRD
preplace port DDR -pg 1 -lvl 8 -x 2400 -y 640 -defaultsOSRD
preplace port FIXED_IO -pg 1 -lvl 8 -x 2400 -y 670 -defaultsOSRD
preplace port port-id_irq -pg 1 -lvl 8 -x 2400 -y 20 -defaultsOSRD
preplace port port-id_servo_pwm -pg 1 -lvl 8 -x 2400 -y 310 -defaultsOSRD
preplace port port-id_spi_miso -pg 1 -lvl 8 -x 2400 -y 280 -defaultsOSRD
preplace port port-id_spi_cs_n -pg 1 -lvl 0 -x -20 -y 110 -defaultsOSRD
preplace port port-id_spi_sck -pg 1 -lvl 0 -x -20 -y 140 -defaultsOSRD
preplace port port-id_spi_mosi -pg 1 -lvl 0 -x -20 -y 170 -defaultsOSRD
preplace portBus pdm_clocks -pg 1 -lvl 8 -x 2400 -y 80 -defaultsOSRD
preplace portBus pdm_data -pg 1 -lvl 0 -x -20 -y 590 -defaultsOSRD
preplace inst ps7 -pg 1 -lvl 7 -x 2150 -y 690 -defaultsOSRD
preplace inst clk_main -pg 1 -lvl 1 -x 120 -y 270 -defaultsOSRD
preplace inst clk_audio -pg 1 -lvl 2 -x 330 -y 240 -defaultsOSRD
preplace inst core_reset -pg 1 -lvl 4 -x 1010 -y 690 -defaultsOSRD
preplace inst io_reset -pg 1 -lvl 3 -x 650 -y 330 -defaultsOSRD
preplace inst core_reset_gate -pg 1 -lvl 5 -x 1330 -y 520 -defaultsOSRD
preplace inst io_reset_gate -pg 1 -lvl 4 -x 1010 -y 380 -defaultsOSRD
preplace inst core_release -pg 1 -lvl 6 -x 1740 -y 510 -defaultsOSRD
preplace inst io_release -pg 1 -lvl 5 -x 1330 -y 370 -defaultsOSRD
preplace inst zero -pg 1 -lvl 2 -x 330 -y 510 -defaultsOSRD
preplace inst one -pg 1 -lvl 2 -x 330 -y 410 -defaultsOSRD
preplace inst compute -pg 1 -lvl 7 -x 2150 -y 150 -defaultsOSRD
preplace inst link -pg 1 -lvl 6 -x 1740 -y 170 -defaultsOSRD
preplace netloc clk_audio_clk_out1 1 2 5 440 200 NJ 200 1180 80 1510 20 1940J
preplace netloc clk_audio_locked 1 2 3 460 210 840 530 NJ
preplace netloc clk_main_clk_out1 1 1 1 N 250
preplace netloc clk_main_clk_out2 1 1 6 210J 310 430J 220 830 300 NJ 300 1480 380 1960
preplace netloc clk_main_locked 1 1 1 220 230n
preplace netloc compute_draining 1 5 3 1550 330 NJ 330 2320
preplace netloc compute_feature_flags 1 5 3 1560 320 NJ 320 2340
preplace netloc compute_feature_pairs 1 5 3 1520 360 NJ 360 2350
preplace netloc compute_feature_valid 1 5 3 1540 340 NJ 340 2360
preplace netloc compute_pdm_clocks 1 7 1 NJ 80
preplace netloc compute_source_faults 1 5 3 1530 350 NJ 350 2330
preplace netloc core_release_dest_arst 1 6 1 1980 150n
preplace netloc core_reset_gate_Res 1 5 1 N 520
preplace netloc core_reset_peripheral_aresetn 1 4 1 1180 510n
preplace netloc io_release_dest_arst 1 5 2 1510 370 1970
preplace netloc io_reset_gate_Res 1 4 1 N 380
preplace netloc io_reset_peripheral_aresetn 1 3 1 N 370
preplace netloc link_feature_ready 1 6 1 1930 150n
preplace netloc link_irq 1 6 2 1930J 10 2380J
preplace netloc link_run_enable 1 6 1 N 170
preplace netloc link_servo_pwm 1 6 2 1940J 310 NJ
preplace netloc link_spi_miso 1 6 2 1950J 20 2370J
preplace netloc one_dout 1 2 2 470 690 NJ
preplace netloc pdm_data_0_1 1 0 7 0J 10 NJ 10 NJ 10 NJ 10 NJ 10 NJ 10 1920J
preplace netloc ps7_FCLK_CLK0 1 0 8 30 160 NJ 160 NJ 160 NJ 160 NJ 160 1490J 390 NJ 390 2320
preplace netloc ps7_FCLK_RESET1_N 1 0 8 20 350 NJ 350 450 230 820 790 NJ 790 NJ 790 NJ 790 2320
preplace netloc spi_cs_n_0_1 1 0 6 NJ 110 NJ 110 NJ 110 NJ 110 NJ 110 1560J
preplace netloc spi_mosi_0_1 1 0 6 NJ 170 NJ 170 NJ 170 NJ 170 NJ 170 1500J
preplace netloc spi_sck_0_1 1 0 6 NJ 140 NJ 140 NJ 140 NJ 140 NJ 140 NJ
preplace netloc zero_dout 1 2 2 480 710 NJ
preplace netloc processing_system7_0_DDR 1 7 1 2380J 640n
preplace netloc processing_system7_0_FIXED_IO 1 7 1 NJ 670
levelinfo -pg 1 -20 120 330 650 1010 1330 1740 2150 2400
pagesize -pg 1 -db -bbox -sgen -170 0 2560 810
"
}

  # Restore current instance
  current_bd_instance $oldCurInst

  validate_bd_design
  save_bd_design
}
# End of create_root_design()


##################################################################
# MAIN FLOW
##################################################################

create_root_design ""


