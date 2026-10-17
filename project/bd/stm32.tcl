create_bd_design soundsight_stm32_bd
create_bd_cell -type module -reference bd_clean_compute compute
create_bd_cell -type module -reference bd_stm32_link link
source [file join $ss_root project ip create_platform_clock.tcl]
set_property CONFIG.PCW_USE_M_AXI_GP0 0 [get_bd_cells ps7]
connect_bd_net [get_bd_pins clk_audio/clk_out1] [get_bd_pins link/clk]
connect_bd_net [get_bd_pins io_release/dest_arst] [get_bd_pins link/rst_n]
foreach pin {feature_valid feature_pairs feature_flags source_faults} {connect_bd_net [get_bd_pins compute/$pin] [get_bd_pins link/$pin]}
connect_bd_net [get_bd_pins link/feature_ready] [get_bd_pins compute/feature_ready]
connect_bd_net [get_bd_pins link/run_enable] [get_bd_pins compute/enable]
connect_bd_net [get_bd_pins compute/draining] [get_bd_pins link/compute_draining]
foreach pin {spi_cs_n spi_sck spi_mosi} {connect_bd_net [create_bd_port -dir I $pin] [get_bd_pins link/$pin]}
foreach pin {spi_miso irq servo_pwm} {connect_bd_net [create_bd_port -dir O $pin] [get_bd_pins link/$pin]}
foreach item {{pdm_data I} {pdm_clocks O}} {
    lassign $item pin direction
    connect_bd_net [create_bd_port -dir $direction -from 3 -to 0 $pin] [get_bd_pins compute/$pin]
}
