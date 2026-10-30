# 最新三维工程的两个官方 FFT，参数逐项来自用户实际 XCI。
# 仅创建配置；输出产品由主重建入口生成，不运行综合。
proc ss_create_ps_3d_fft {destination} {
    file mkdir [file join $destination ip]
    create_ip -name xfft -vendor xilinx.com -library ip -version 9.1 -module_name ss_fft29 -dir [file join $destination ip]
    set_property -dict [list \
        CONFIG.channels {1} \
        CONFIG.transform_length {1024} \
        CONFIG.target_clock_frequency {100} \
        CONFIG.implementation_options {radix_2_burst_io} \
        CONFIG.target_data_throughput {50} \
        CONFIG.run_time_configurable_transform_length {false} \
        CONFIG.data_format {fixed_point} \
        CONFIG.input_width {29} \
        CONFIG.phase_factor_width {24} \
        CONFIG.scaling_options {scaled} \
        CONFIG.rounding_modes {convergent_rounding} \
        CONFIG.aclken {false} \
        CONFIG.aresetn {true} \
        CONFIG.ovflo {true} \
        CONFIG.xk_index {true} \
        CONFIG.throttle_scheme {nonrealtime} \
        CONFIG.output_ordering {natural_order} \
        CONFIG.cyclic_prefix_insertion {false} \
        CONFIG.memory_options_data {block_ram} \
        CONFIG.memory_options_phase_factors {block_ram} \
        CONFIG.memory_options_reorder {block_ram} \
        CONFIG.number_of_stages_using_block_ram_for_data_and_phase_factors {0} \
        CONFIG.memory_options_hybrid {false} \
        CONFIG.complex_mult_type {use_mults_resources} \
        CONFIG.butterfly_type {use_luts} \
        CONFIG.super_sample_rates {1} \
        CONFIG.systolicfft_inv {false} \
        CONFIG.blocking_run_time_configuration {false} \
    ] [get_ips ss_fft29]
    create_ip -name xfft -vendor xilinx.com -library ip -version 9.1 -module_name ss_ifft25 -dir [file join $destination ip]
    set_property -dict [list \
        CONFIG.channels {1} \
        CONFIG.transform_length {1024} \
        CONFIG.target_clock_frequency {100} \
        CONFIG.implementation_options {radix_2_burst_io} \
        CONFIG.target_data_throughput {50} \
        CONFIG.run_time_configurable_transform_length {false} \
        CONFIG.data_format {fixed_point} \
        CONFIG.input_width {25} \
        CONFIG.phase_factor_width {24} \
        CONFIG.scaling_options {scaled} \
        CONFIG.rounding_modes {convergent_rounding} \
        CONFIG.aclken {false} \
        CONFIG.aresetn {true} \
        CONFIG.ovflo {true} \
        CONFIG.xk_index {true} \
        CONFIG.throttle_scheme {nonrealtime} \
        CONFIG.output_ordering {natural_order} \
        CONFIG.cyclic_prefix_insertion {false} \
        CONFIG.memory_options_data {block_ram} \
        CONFIG.memory_options_phase_factors {block_ram} \
        CONFIG.memory_options_reorder {block_ram} \
        CONFIG.number_of_stages_using_block_ram_for_data_and_phase_factors {0} \
        CONFIG.memory_options_hybrid {false} \
        CONFIG.complex_mult_type {use_mults_resources} \
        CONFIG.butterfly_type {use_luts} \
        CONFIG.super_sample_rates {1} \
        CONFIG.systolicfft_inv {false} \
        CONFIG.blocking_run_time_configuration {false} \
    ] [get_ips ss_ifft25]
}
