# STM32 target; Vivado 2025.2; 61.44 MHz acquisition/control, 100 MHz compute.
# Pure XDC: validation/control flow belongs in a separate Tcl script.
# 4 ns / 20 ns are design budgets, not measured board delays.
# PDM input: primary ports -> first synchronizer D pins only.
set pdm_first [get_pins -hier -regexp {.*acquisition/pdm_meta_reg\[[0-3]\]/D}]
set_max_delay -datapath_only 4.000 -from [get_ports {pdm_data[*]}] -to $pdm_first
set_min_delay 0.000 -from [get_ports {pdm_data[*]}] -to $pdm_first
# Explicit valid startpoints include clock-to-Q; endpoints remain external outputs.
set io_launch_pins [all_registers -clock_pins]
set_max_delay -datapath_only 4.000 -from $io_launch_pins -to [get_ports {pdm_clocks[*]}]
set_min_delay 0.000 -from $io_launch_pins -to [get_ports {pdm_clocks[*]}]
# SPI asynchronous oversampling inputs: constrain first stages individually.
set spi_cs_first [get_pins -hier -regexp {.*spi/cs_sync_reg\[0\]/D}]
set_max_delay -datapath_only 4.000 -from [get_ports spi_cs_n] -to $spi_cs_first
set_min_delay 0.000 -from [get_ports spi_cs_n] -to $spi_cs_first
set spi_ck_first [get_pins -hier -regexp {.*spi/ck_sync_reg\[0\]/D}]
set_max_delay -datapath_only 4.000 -from [get_ports spi_sck] -to $spi_ck_first
set_min_delay 0.000 -from [get_ports spi_sck] -to $spi_ck_first
set spi_di_first [get_pins -hier -regexp {.*spi/di_sync_reg\[0\]/D}]
set_max_delay -datapath_only 4.000 -from [get_ports spi_mosi] -to $spi_di_first
set_min_delay 0.000 -from [get_ports spi_mosi] -to $spi_di_first
# Register launch -> asynchronous output ports. No blanket clock-domain cuts.
set_max_delay -datapath_only 20.000 -from $io_launch_pins -to [get_ports {spi_miso irq servo_pwm}]
set_min_delay 0.000 -from $io_launch_pins -to [get_ports {spi_miso irq servo_pwm}]
# Clock/reset/XPM constraints remain supplied by the corresponding official IP.
