// MIGRATION_MODULE_GUIDE
// 分组：04 预处理与FFT
// 用途：调度8个官方FFT，检查1024个输入、1024个输出及独立status；转发域1的四路513点半谱。
// 接口要点：begin/s/end 均带同一真实32位帧号。STOP 后排完已配置FFT，再发 end_cancelled；不借 STOP 冷复位 IP。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 一帧只分配一个32位帧号。保留原8个FFT单元（两域×四路）和各自真实status。
// 域0仍计算并检查，不把原本可能出现的数值错误藏掉；仅域1半谱送六对引擎。
// STOP后不启动下一个单元，已提交配置的FFT继续收满1024点并排空output/status。
module ss_fft_frontend #(parameter integer LEVEL_ENABLE=0, parameter HANN_FILE="hann-u18f17.mem")(
 input wire clk,rst_n,enable,input wire source_bad,
 input wire window_valid,output wire window_ready,input wire [31:0] window_frame,
 output wire release_window,output wire read_enable,output wire [9:0] read_index,
 input wire read_valid,input wire [95:0] read_pcm,
 output wire begin_valid,input wire begin_ready,output wire [31:0] begin_frame,
 output wire s_valid,input wire s_ready,output wire [31:0] s_frame,
 output wire [1:0] s_channel,output wire [9:0] s_bin,
 output wire signed [24:0] s_real,s_imag,output wire s_numeric_valid,
 output wire end_valid,input wire end_ready,output wire [31:0] end_frame,
 output wire end_cancelled,output wire [7:0] end_error,
 input wire backend_busy,output wire busy,
 output wire [3:0] debug_state,
 output wire [31:0] frame_level, output wire frame_level_valid,
 output wire audit_valid,output wire audit_domain,output wire [1:0] audit_channel,
 output wire [9:0] audit_bin,output wire signed [28:0] audit_real,audit_imag
);
 localparam [3:0] IDLE=0,COPY=1,UNIT=2,CONFIG=3,RUN=4,NEXT=5,END_FRAME=6,WAIT_BACKEND=7;
 reg [3:0] state;
 reg [31:0] frame;
 reg [2:0] unit_index;
 reg cancelled;
 reg [7:0] error_code;
 reg [10:0] in_count,out_count;
 reg status_seen;
 wire accepting=window_valid && window_ready;
 assign busy=state!=IDLE;
 assign debug_state=state;
 assign begin_valid=state==IDLE && enable && !source_bad && window_valid;
 assign begin_frame=window_frame;
 assign window_ready=state==IDLE && enable && !source_bad && begin_ready;
 assign s_frame=frame;
 assign s_channel=unit_index[1:0];
 assign end_valid=state==END_FRAME;
 assign end_frame=frame;
 assign end_cancelled=cancelled || !enable;
 assign end_error=error_code;
 wire np_ready,np_done,np_valid,np_out_ready,np_last,np_numeric_error;
 wire signed [28:0] np_real;
 ss_preprocess #(.LEVEL_ENABLE(LEVEL_ENABLE),.HANN_FILE(HANN_FILE)) preprocess(
   .clk(clk),.rst_n(rst_n),.frame_start(accepting),.read_enable(read_enable),.read_index(read_index),
   .read_valid(read_valid),.read_pcm(read_pcm),.copy_done(release_window),
   .unit_start(state==UNIT && np_ready && !cancelled && enable && !source_bad && error_code==0),
   .domain(unit_index[2]),.channel(unit_index[1:0]),.unit_ready(np_ready),.unit_done(np_done),
   .out_valid(np_valid),.out_ready(np_out_ready),.out_real(np_real),.out_last(np_last),.numeric_error(np_numeric_error),
   .frame_level(frame_level),.frame_level_valid(frame_level_valid));
 wire cfg_ready,fft_in_ready,fft_valid,fft_ready,fft_last,status_valid;
 wire signed [28:0] fft_real,fft_imag;
 wire [9:0] fft_index;
 wire [7:0] status_data;
 wire [6:0] events;
 fft29_official forward(
   .clk(clk),.cold_rst_n(rst_n),.config_valid(state==CONFIG),.config_ready(cfg_ready),
   .data_valid(state==RUN && np_valid),.data_ready(fft_in_ready),.data_real(np_real),.data_imag(29'sd0),.data_last(np_last),
   .out_valid(fft_valid),.out_ready(fft_ready),.out_real(fft_real),.out_imag(fft_imag),
   .out_index(fft_index),.out_last(fft_last),.status_valid(status_valid),.status_ready(state==RUN && !status_seen),
   .status_raw(status_data),.events(events));
 assign np_out_ready=state==RUN && fft_in_ready;
 // S29→S25完全沿用原fixed4的floor+余数RNE；先保留30位检测越界，再缩窄。
 function automatic signed [29:0] fixed4(input signed [28:0] value);
   reg signed [29:0] q;reg add_one;
   begin q=$signed({value[28],value})>>>4;
     add_one=(value[3:0]>8) || (value[3:0]==8 && q[0]);
     fixed4=q+$signed({29'b0,add_one});
   end
 endfunction
 wire signed [29:0] rounded_re=fixed4(fft_real);
 wire signed [29:0] rounded_im=fixed4(fft_imag);
 wire numeric_good=rounded_re>=-30'sd16777216 && rounded_re<=30'sd16777215 &&
                   rounded_im>=-30'sd16777216 && rounded_im<=30'sd16777215;
 wire forward_point=state==RUN && unit_index[2] && fft_index<=512 && !cancelled && enable;
 assign fft_ready=state==RUN && (!forward_point || s_ready);
 assign s_valid=fft_valid && forward_point;
 assign s_bin=fft_index;
 assign s_real=rounded_re[24:0];assign s_imag=rounded_im[24:0];
 assign s_numeric_valid=numeric_good;
 assign audit_valid=fft_valid && fft_ready;
 assign audit_domain=unit_index[2];assign audit_channel=unit_index[1:0];assign audit_bin=fft_index;
 assign audit_real=fft_real;assign audit_imag=fft_imag;
 always @(posedge clk)begin
   if(!rst_n)begin
     state<=IDLE;frame<=0;unit_index<=0;cancelled<=0;error_code<=0;
     in_count<=0;out_count<=0;status_seen<=0;
   end else begin
     if(state!=IDLE && !enable)cancelled<=1;
     if(state!=IDLE && source_bad && error_code==0)error_code<=4;
     if(state!=IDLE && state!=COPY && np_numeric_error && error_code==0)error_code<=3;
     case(state)
       IDLE:if(accepting)begin frame<=window_frame;unit_index<=0;cancelled<=0;error_code<=0;state<=COPY;end
       COPY:if(np_ready)state<=UNIT;
       UNIT:begin
         if(cancelled || !enable || source_bad || error_code!=0)state<=END_FRAME;
         else if(np_ready)state<=CONFIG;
       end
       CONFIG:if(cfg_ready)begin in_count<=0;out_count<=0;status_seen<=0;state<=RUN;end
       RUN:begin
         if(np_valid && np_out_ready)begin
           in_count<=in_count+1'b1;
           if(np_last!=(in_count==1023) && error_code==0)error_code<=4;
         end
         if(fft_valid && fft_ready)begin
           out_count<=out_count+1'b1;
           if((fft_index!=out_count[9:0] || fft_last!=(out_count==1023)) && error_code==0)error_code<=4;
           if(fft_index<=512 && !numeric_good && error_code==0)error_code<=3;
         end
         if(status_valid && !status_seen)begin
           status_seen<=1;if(status_data!=0 && error_code==0)error_code<=3;
         end
         if((events[1] || events[2] || events[6]) && error_code==0)error_code<=events[6]?3:4;
         if(in_count==1024 && out_count==1024 && status_seen)state<=NEXT;
       end
       NEXT:begin
         if(unit_index==7 || cancelled || !enable || source_bad || error_code!=0)state<=END_FRAME;
         else begin unit_index<=unit_index+1'b1;state<=UNIT;end
       end
       END_FRAME:if(end_ready)state<=WAIT_BACKEND;
       WAIT_BACKEND:if(!backend_busy)state<=IDLE;
       default:begin error_code<=4;state<=END_FRAME;end
     endcase
   end
 end
endmodule
`default_nettype wire
