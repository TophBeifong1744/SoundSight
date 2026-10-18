`timescale 1ns/1ps
// One registered slot. WIDTH >= 1; synchronous active-low reset discards data.
// Ready is combinational: this is not a CDC FIFO or ready-path timing buffer.
module elastic_stage #(parameter WIDTH = 8) (
    input wire clk, input wire rst_n,
    input wire in_valid, output wire in_ready,
    input wire [WIDTH-1:0] in_data,
    output reg out_valid, input wire out_ready,
    output reg [WIDTH-1:0] out_data
);
    assign in_ready = out_ready;
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
