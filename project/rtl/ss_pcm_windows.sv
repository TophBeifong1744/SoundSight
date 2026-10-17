// MIGRATION_MODULE_GUIDE
// 分组：03 采集与分帧
// 用途：2048组四通道环形缓存；每1024点形成一窗，以512点为步进。
// 接口要点：window_valid/ready 移交一个真实32位窗口帧号；read_enable/index 请求同步读，下一拍 read_valid/pcm；release_window 释放窗口。拥塞报错并停止新增，物理采集时钟不停。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 2048组环形采样RAM，1024点窗、512点步进。一次只借出一个窗口。
// 借出的base/frame保持到release；读方先拷走窗口再做FFT，因此处理期间不占采样RAM。
// 过慢导致待交窗口拥塞或写指针追上借出窗时，报告故障并停止新增，不默默改旧数据。
module ss_pcm_windows (
 input wire clk,rst_n,enable,sample_valid,input wire [95:0] sample_pcm,
 input wire sample_clipped,
 output wire window_valid,input wire window_ready,output reg [31:0] window_frame,
 input wire release_window,
 input wire read_enable,input wire [9:0] read_index,
 output reg read_valid,output reg [95:0] read_pcm,
 output reg overflow,numeric_error,counter_exhausted
);
 (* ram_style="block" *) reg [95:0] ring[0:2047];
 reg [10:0] write_index,base;
 reg [9:0] fill;
 reg [8:0] hop;
 reg complete_first,pending,owned;
 reg [31:0] sequence_count;
 wire sample_fire=enable && sample_valid && !overflow && !counter_exhausted;
 wire boundary=(!complete_first && fill==1023) || (complete_first && hop==511);
 assign window_valid=pending && enable && !overflow && !counter_exhausted;
 always @(posedge clk)begin
   read_valid<=read_enable && owned;
   if(read_enable && owned)read_pcm<=ring[11'(base+read_index)];
   if(sample_fire)ring[write_index]<=sample_pcm;
   if(!rst_n)begin
     write_index<=0;base<=0;fill<=0;hop<=0;complete_first<=0;
     pending<=0;owned<=0;window_frame<=0;sequence_count<=0;
     overflow<=0;numeric_error<=0;counter_exhausted<=0;read_valid<=0;read_pcm<=0;
   end else begin
     if(release_window)owned<=0;
     if(window_valid && window_ready)begin pending<=0;owned<=1;end
     if(!enable)begin
       fill<=0;hop<=0;complete_first<=0;pending<=0;
       // 运行中取消只撤销未交出的窗口；已借出窗口仍由读方release收尾。
       if(!owned || release_window)begin overflow<=0;numeric_error<=0;end
     end else if(sample_fire)begin
       write_index<=write_index+1'b1;
       if(sample_clipped)numeric_error<=1;
       if((pending || owned) && write_index==base)overflow<=1;
       if(!complete_first)begin
         if(fill==1023)begin complete_first<=1;hop<=0;end
         else fill<=fill+1'b1;
       end else hop<=hop+1'b1;
       if(boundary)begin
         if(pending || (owned && !release_window))overflow<=1;
         else if(sequence_count==32'hffffffff)counter_exhausted<=1;
         else begin
           sequence_count<=sequence_count+1'b1;window_frame<=sequence_count+1'b1;
           base<=write_index-11'd1023;pending<=1;
         end
       end
     end
   end
 end
endmodule
`default_nettype wire
