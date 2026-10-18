`timescale 1ns/1ps
// One registered slot. WIDTH >= 1; synchronous active-low reset discards data.
// Ready is combinational: this is not a CDC FIFO or ready-path timing buffer.
module inner_stage #(parameter WIDTH = 8) (
    input wire clk, input wire rst_n,
    input wire in_valid, output wire in_ready,
    input wire [WIDTH-1:0] in_data,
    output reg out_valid, input wire out_ready,
    output reg [WIDTH-1:0] out_data
);
    assign in_ready = !out_valid || out_ready;
    always @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_data <= {WIDTH{1'b0}};
        end else if (in_ready) begin
            out_valid <= in_valid;
            if (in_valid) out_data <= in_data;
        end
    end
endmodule

module elastic_stage #(parameter WIDTH=8)(
    input wire clk, rst_n, in_valid, output wire in_ready,
    input wire [WIDTH-1:0] in_data,
    output wire out_valid, input wire out_ready,
    output wire [WIDTH-1:0] out_data
);
    wire mid_valid, mid_ready;
    wire [WIDTH-1:0] mid_data;
    inner_stage #(.WIDTH(WIDTH)) a(
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(in_ready),
        .in_data(in_data), .out_valid(mid_valid), .out_ready(mid_ready), .out_data(mid_data));
    inner_stage #(.WIDTH(WIDTH)) b(
        .clk(clk), .rst_n(rst_n), .in_valid(mid_valid), .in_ready(mid_ready),
        .in_data(mid_data), .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data));
endmodule
