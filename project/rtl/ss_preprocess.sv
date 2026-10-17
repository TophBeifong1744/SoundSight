// MIGRATION_MODULE_GUIDE
// 分组：04 预处理与FFT
// 用途：先拷贝1024组PCM，然后串行计算两域四通道共8个FFT输入单元。
// 接口要点：域0去均值后乘Hann；域1直接乘Hann。U18F17系数、RNE舍入、DOA S24饱和并报错；输出S29=处理值乘16。out_valid/ready 背压时数据不变。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 精简预处理：先复制完整窗并求四路均值，再按指定domain/channel顺序给FFT送1024点。
// 沿用原算法：domain0=(PCM-均值)*Hann，domain1=PCM*Hann；不是两域都去均值。
// 均值/乘积均最近偶数舍入。每级运算隔拍，OUT在背压期间保持载荷。
module ss_preprocess #(parameter HANN_FILE="hann-u18f17.mem")(
 input wire clk,rst_n,frame_start,
 output wire read_enable,output wire [9:0] read_index,
 input wire read_valid,input wire [95:0] read_pcm,
 output reg copy_done,
 input wire unit_start,input wire domain,input wire [1:0] channel,
 output wire unit_ready,output reg unit_done,
 output wire out_valid,input wire out_ready,
 output reg signed [28:0] out_real,output wire out_last,
 output reg numeric_error
);
 localparam [3:0] IDLE=0,COPY=1,MEAN=2,READY=3,READ=4,SUBTRACT=5,MULTIPLY=6,ROUND=7,OUT=8;
 reg [3:0] state;
 reg [10:0] issued,received;
 reg [1:0] mean_channel,channel_q;
 reg domain_q;
 reg [9:0] index;
 reg signed [33:0] sums[0:3];
 reg signed [23:0] means[0:3];
 (* ram_style="block" *) reg [95:0] samples[0:1023];
 reg [17:0] hann[0:1023];
 reg [95:0] sample_q;
 reg [17:0] coefficient;
 reg signed [24:0] operand;
 reg signed [43:0] product;
 integer i;
 initial begin
   for(i=0;i<1024;i=i+1)hann[i]=18'h3ffff;
   $readmemh(HANN_FILE,hann);
 end
 function automatic signed [43:0] rne(input signed [43:0] value,input integer shift);
   reg signed [44:0] extended,q;
   reg [44:0] remn,half;
   begin
     extended={value[43],value};q=extended>>>shift;
     remn=$unsigned(extended)&((45'd1<<shift)-1'b1);half=45'd1<<(shift-1);
     if(remn>half || (remn==half && q[0]))q=q+1'b1;
     rne=q[43:0];
   end
 endfunction
 wire signed [43:0] mean_value=rne(44'($signed(sums[mean_channel])),10);
 wire signed [43:0] rounded=rne(product,17);
 wire signed [23:0] selected_pcm=$signed(sample_q[channel_q*24+:24]);
 assign read_enable=state==COPY && issued<1024;
 assign read_index=issued[9:0];
 assign unit_ready=state==READY;
 assign out_valid=state==OUT;
 assign out_last=index==1023;
 // RAM只在真实响应时写；不做2048字的运行期清零。
 always @(posedge clk)begin
   if(state==COPY && read_valid && received<1024)samples[received[9:0]]<=read_pcm;
   if(state==READ)begin sample_q<=samples[index];coefficient<=hann[index];end
 end
 always @(posedge clk)begin
   if(!rst_n)begin
     state<=IDLE;issued<=0;received<=0;mean_channel<=0;channel_q<=0;domain_q<=0;index<=0;
     copy_done<=0;unit_done<=0;numeric_error<=0;out_real<=0;operand<=0;product<=0;
     for(i=0;i<4;i=i+1)begin sums[i]<=0;means[i]<=0;end
   end else begin
     copy_done<=0;unit_done<=0;
     if(frame_start && (state==IDLE || state==READY))begin
       state<=COPY;issued<=0;received<=0;mean_channel<=0;numeric_error<=0;
       for(i=0;i<4;i=i+1)begin sums[i]<=0;means[i]<=0;end
     end else case(state)
       COPY:begin
         if(read_enable)issued<=issued+1'b1;
         if(read_valid)begin
           received<=received+1'b1;
           for(i=0;i<4;i=i+1)sums[i]<=sums[i]+34'($signed(read_pcm[i*24+:24]));
           if(received==1023)begin state<=MEAN;mean_channel<=0;copy_done<=1;end
         end
       end
       MEAN:begin
         means[mean_channel]<=mean_value[23:0];
         if(mean_value< -44'sd8388608 || mean_value>44'sd8388607)numeric_error<=1;
         if(mean_channel==3)state<=READY;else mean_channel<=mean_channel+1'b1;
       end
       READY:if(unit_start)begin domain_q<=domain;channel_q<=channel;index<=0;state<=READ;end
       READ:state<=SUBTRACT;
       SUBTRACT:begin
         operand<=domain_q?25'(selected_pcm):25'(selected_pcm)-25'($signed(means[channel_q]));
         state<=MULTIPLY;
       end
       MULTIPLY:begin product<=operand*$signed({1'b0,coefficient});state<=ROUND;end
       ROUND:begin
         if(coefficient>18'd131072 || (!domain_q && (rounded< -44'sd16777216 || rounded>44'sd16777215)) ||
           (domain_q && (rounded< -44'sd8388608 || rounded>44'sd8388607)))numeric_error<=1;
         if(domain_q && rounded< -44'sd8388608)out_real<={1'b1,24'h800000,4'b0};
         else if(domain_q && rounded>44'sd8388607)out_real<={1'b0,24'h7fffff,4'b0};
         else out_real<=domain_q?{rounded[23],rounded[23:0],4'b0}:{rounded[24:0],4'b0};
         state<=OUT;
       end
       OUT:if(out_ready)begin
         if(index==1023)begin unit_done<=1;state<=READY;end
         else begin index<=index+1'b1;state<=READ;end
       end
       default:state<=IDLE;
     endcase
   end
 end
endmodule
`default_nettype wire
