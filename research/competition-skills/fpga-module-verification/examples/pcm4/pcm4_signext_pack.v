`timescale 1ns/1ps
// C-RTL-003 v1.0: independent signed PCM slots, mic0 in the low word.
// SAMPLE_WIDTH is a compile-time parameter with supported range 2..32.
module pcm4_signext_pack #(
    parameter SAMPLE_WIDTH = 24
) (
    input  wire signed [SAMPLE_WIDTH-1:0] mic0_in,
    input  wire signed [SAMPLE_WIDTH-1:0] mic1_in,
    input  wire signed [SAMPLE_WIDTH-1:0] mic2_in,
    input  wire signed [SAMPLE_WIDTH-1:0] mic3_in,
    output wire [127:0] pcm_packed
);
    // At width 32 each replication has length zero; the full input remains.
    assign pcm_packed[31:0]   = {{(32-SAMPLE_WIDTH){mic0_in[SAMPLE_WIDTH-1]}}, mic0_in};
    assign pcm_packed[63:32]  = {{(32-SAMPLE_WIDTH){mic1_in[SAMPLE_WIDTH-1]}}, mic1_in};
    assign pcm_packed[95:64]  = {{(32-SAMPLE_WIDTH){mic2_in[SAMPLE_WIDTH-1]}}, mic2_in};
    assign pcm_packed[127:96] = {{(32-SAMPLE_WIDTH){mic3_in[SAMPLE_WIDTH-1]}}, mic3_in};
endmodule

