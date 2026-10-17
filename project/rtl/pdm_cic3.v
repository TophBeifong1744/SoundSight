// MIGRATION_MODULE_GUIDE
// 分组：03 采集与分帧
// 用途：单路三级CIC，bit_valid每到64次产生一次S24 PCM。
// 接口要点：clk为61.44MHz处理时钟；bit_valid是PDM采样使能，不是独立时钟。pdm_bit输入，pcm_valid/pcm/clipped输出。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
// Diagnostic CIC3, R=64, differential delay=1. One clock domain.
// Input bit maps to -1/+1. Modulo 32-bit integrators are intentional.
// Gain=64^3=262144; output scales by 32, saturates to signed24.
module pdm_cic3(input wire clk, input wire rst_n,
 input wire bit_valid, input wire pdm_bit,
 output reg pcm_valid, output reg signed [23:0] pcm,
 output reg clipped);
 reg signed [31:0] i1,i2,i3,d1,d2,d3;
 reg [5:0] phase;
 wire signed [31:0] n1=i1+(pdm_bit ? 32'sd1 : -32'sd1);
 wire signed [31:0] n2=i2+n1;
 wire signed [31:0] n3=i3+n2;
 wire signed [31:0] c1=n3-d1;
 wire signed [31:0] c2=c1-d2;
 wire signed [31:0] c3=c2-d3;
 always @(posedge clk) begin
  if (!rst_n) begin
   i1<=0;i2<=0;i3<=0;d1<=0;d2<=0;d3<=0;phase<=0;
   pcm_valid<=0;pcm<=0;clipped<=0;
  end else begin
   pcm_valid<=0;
   if(bit_valid) begin
    i1<=n1;i2<=n2;i3<=n3;phase<=phase+1'b1;
    if(phase==63) begin
     d1<=n3;d2<=c1;d3<=c2;pcm_valid<=1;clipped<=0;
     if(c3>32'sd262143) begin pcm<=24'sh7fffff;clipped<=1;end
     else if(c3 < -32'sd262144) begin pcm<=24'sh800000;clipped<=1;end
     else pcm<=c3 <<< 5;
    end
   end
  end
 end
endmodule
