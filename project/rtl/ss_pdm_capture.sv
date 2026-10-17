// MIGRATION_MODULE_GUIDE
// 分组：03 采集与分帧
// 用途：四路 PDM 同步采样，复用原 CIC 抽取；麦克风时钟连续运行。
// 接口要点：pdm_data[3:0] 经同步器；四个 S24 PCM 按通道0在最低24位拼成96位；sample_valid 一拍。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 四路CIC沿用原数值与采样相位。PDM物理时钟一直运行，软件STOP只关新窗口。
// 这里没有会话票据/诊断包；每组PCM只携带有效与削顶标记。
module ss_pdm_capture #(parameter integer WARMUP_SAMPLES=4096)(
 input wire clk,rst_n,input wire [3:0] pdm_data,
 output wire [3:0] pdm_clocks,output wire sample_valid,
 output wire [95:0] pcm,output wire sample_clipped,output wire warm,
 output wire channel_fault
);
 reg [4:0] phase;
 reg pdm_clock;
 (* ASYNC_REG="TRUE" *) reg [3:0] pdm_meta,pdm_sync;
 reg [31:0] warmup;
 wire [3:0] pv,clip;
 assign pdm_clocks={4{pdm_clock}};
 assign warm=warmup>=WARMUP_SAMPLES;
 assign sample_valid=&pv && warm;
 assign sample_clipped=|clip;
 assign channel_fault=(|pv) && !(&pv);
 always @(posedge clk)begin
   if(!rst_n)begin phase<=0;pdm_clock<=0;pdm_meta<=0;pdm_sync<=0;warmup<=0;end
   else begin
     pdm_meta<=pdm_data;pdm_sync<=pdm_meta;
     if(phase==19)begin phase<=0;pdm_clock<=0;end
     else begin phase<=phase+1'b1;if(phase==9)pdm_clock<=1;end
     if(&pv && !warm)warmup<=warmup+1'b1;
   end
 end
 genvar c;
 generate for(c=0;c<4;c=c+1)begin:mic
   pdm_cic3 cic(.clk(clk),.rst_n(rst_n),.bit_valid(phase==9),.pdm_bit(pdm_sync[c]),
     .pcm_valid(pv[c]),.pcm(pcm[c*24+:24]),.clipped(clip[c]));
 end endgenerate
endmodule
`default_nettype wire
