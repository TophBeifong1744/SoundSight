// MIGRATION_MODULE_GUIDE
// 分组：BD 端口适配
// 用途：Vivado Module Reference 只接受 Verilog/VHDL 顶层；此层转接下方 SystemVerilog。
// 本模块不增加寄存器、延迟或控制状态。所有参数、位宽、握手和复位逐线原样传递。
// BD 里添加本模块；算法源码仍在 ss_dual_compute.sv，修改算法时不需重写这里。
`timescale 1ns/1ps
`default_nettype none
module bd_clean_compute #(parameter integer WARMUP_SAMPLES=4096,AUDIO_ENABLE=0,LEVEL_ENABLE=0,parameter HANN_FILE="hann-u18f17.mem")(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
 (* X_INTERFACE_PARAMETER="FREQ_HZ 100000000, ASSOCIATED_RESET rst_n" *)
 input wire clk,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 io_clk CLK" *)
 (* X_INTERFACE_PARAMETER="FREQ_HZ 61440000, ASSOCIATED_RESET io_rst_n" *)
 input wire io_clk,
 input wire io_rst_n,
 input wire rst_n,enable,input wire [3:0] pdm_data,
 output wire [3:0] pdm_clocks,
 input wire [31:0] audio_epoch,input wire audio_active,
 output wire audio_valid,audio_clip,audio_source_fault,
 output wire audio_run,audio_draining,
 output wire [95:0] audio_pcm,output wire [63:0] audio_sample_index,
 output wire [128:0] feature_meta,
 output wire feature_valid,input wire feature_ready,
 output wire [959:0] feature_pairs,output wire [31:0] feature_flags,
 output wire [31:0] feature_level,output wire feature_level_valid,
 output wire draining,output wire [11:0] source_faults,
 output wire [3:0] debug_frontend,output wire [4:0] debug_backend
);
 ss_dual_compute #(
    .WARMUP_SAMPLES(WARMUP_SAMPLES),.LEVEL_ENABLE(LEVEL_ENABLE),.AUDIO_ENABLE(AUDIO_ENABLE),
    .HANN_FILE(HANN_FILE)
 ) u_core(
    .clk(clk),
    .rst_n(rst_n),
    .io_clk(io_clk),
    .io_rst_n(io_rst_n),
    .enable(enable),
    .pdm_data(pdm_data),
    .pdm_clocks(pdm_clocks),
    .audio_epoch(audio_epoch),.audio_active(audio_active),.audio_valid(audio_valid),.audio_clip(audio_clip),
    .audio_run(audio_run),.audio_draining(audio_draining),
    .audio_source_fault(audio_source_fault),.audio_pcm(audio_pcm),.audio_sample_index(audio_sample_index),.feature_meta(feature_meta),
    .feature_valid(feature_valid),
    .feature_ready(feature_ready),
    .feature_pairs(feature_pairs),
    .feature_flags(feature_flags),
    .feature_level(feature_level),.feature_level_valid(feature_level_valid),
    .draining(draining),
    .source_faults(source_faults),
    .debug_frontend(debug_frontend),
    .debug_backend(debug_backend)
 );
endmodule
`default_nettype wire
