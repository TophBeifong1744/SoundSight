# Requires the audited routed design open. No programming/debug connection.
write_checkpoint -force [file join $root output screen-ps-i2c-s2-routed.dcp]
set run_bit [file join [get_property DIRECTORY [get_runs impl_1]] soundsight_stm32_bd_wrapper.bit]
write_bitstream -force $run_bit
file copy -force $run_bit [file join $root output soundsight.bit]
write_hw_platform -fixed -include_bit -force -file [file join $root output soundsight.xsa]
set hwh [file join $root payload SoundSight_PS_3D.gen sources_1 bd soundsight_stm32_bd hw_handoff soundsight_stm32_bd.hwh]
if {![file exists $hwh]} {error "Missing generated HWH: $hwh"}
file copy -force $hwh [file join $root output soundsight.hwh]
puts {SCREEN_PS_I2C_S2_BUILD_COMPLETE NO_HARDWARE_ACCESS=1 BOARD_TEST=NOT_RUN}
