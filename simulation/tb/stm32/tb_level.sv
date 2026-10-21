`timescale 1ns/1ps
// 已知幅值/直流偏置/满量程边界与背压；不开FFT，不连接硬件。
module tb_level;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,frame_start=0,unit_start=0,domain=0,out_ready=0;
 reg [1:0] channel=0;
 wire read_enable,copy_done,unit_ready,unit_done,out_valid,out_last,numeric_error;
 wire [9:0] read_index;reg read_valid=0;reg [95:0] read_pcm=0;
 wire signed [28:0] out_real;wire [31:0] frame_level;wire frame_level_valid;
 integer pattern=0,cycle=0,units=0,checks=0;
 ss_preprocess #(.LEVEL_ENABLE(1)) dut(.*);
 // 同样的采样与背压送入旧模式：新增幅度旁路不得改变数值或握手拍数。
 wire ref_read_enable,ref_copy_done,ref_unit_ready,ref_unit_done;
 wire ref_out_valid,ref_out_last,ref_numeric_error;
 wire [9:0] ref_read_index;wire signed [28:0] ref_out_real;
 ss_preprocess #(.LEVEL_ENABLE(0)) legacy(
  .clk(clk),.rst_n(rst_n),.frame_start(frame_start),.unit_start(unit_start),
  .domain(domain),.channel(channel),.out_ready(out_ready),
  .read_valid(read_valid),.read_pcm(read_pcm),.read_enable(ref_read_enable),
  .read_index(ref_read_index),.copy_done(ref_copy_done),.unit_ready(ref_unit_ready),
  .unit_done(ref_unit_done),.out_valid(ref_out_valid),.out_last(ref_out_last),
  .out_real(ref_out_real),.numeric_error(ref_numeric_error),
  .frame_level(),.frame_level_valid());
 always @(posedge clk)if(rst_n)begin
  if({read_enable,read_index,copy_done,unit_ready,unit_done,out_valid,out_last,numeric_error}
    !== {ref_read_enable,ref_read_index,ref_copy_done,ref_unit_ready,ref_unit_done,
         ref_out_valid,ref_out_last,ref_numeric_error})$fatal(1,"LEVEL_FAIL legacy handshake changed");
  if(out_valid && out_real!==ref_out_real)$fatal(1,"LEVEL_FAIL legacy numeric changed");
 end
 function automatic signed [23:0] pcm(input integer index,ch,kind);
  case(kind)
   0:pcm=24'sd1000000; // 大直流不是声音，去均值后必须0。
   1:pcm=24'(100000+(index%2 ? 1:-1)*256*(ch+1)); // 四路幅值平均640。
   2:pcm=index%2 ? 24'sh7fffff : 24'sh800000; // 均值-0.5按RNE为0。
   default:pcm=24'(20000+(index%2 ? 1:-1)*4);
  endcase
 endfunction
 always @(posedge clk)begin
  read_valid<=read_enable;
  if(read_enable)for(integer c=0;c<4;c=c+1)read_pcm[c*24+:24]<=pcm(read_index,c,pattern);
 end
 always @(negedge clk)begin cycle=cycle+1;out_ready=(cycle%7!=0 && cycle%11!=0);end
 task start_frame(input integer kind);
  @(negedge clk);pattern=kind;frame_start=1;
  @(negedge clk);frame_start=0;
  if(frame_level_valid || frame_level!=0)$fatal(1,"LEVEL_FAIL stale measurement");
  wait(unit_ready);@(negedge clk);
 endtask
 task run_unit(input integer u);
  domain=u/4;channel=u%4;unit_start=1;@(negedge clk);unit_start=0;
  wait(unit_done);@(negedge clk);units=units+1;
 endtask
 task whole(input integer kind,expected);
  start_frame(kind);
  for(integer u=0;u<8;u=u+1)begin
   run_unit(u);
   if(u<3 && frame_level_valid)$fatal(1,"LEVEL_FAIL incomplete measurement");
   if(u>=3 && (!frame_level_valid || frame_level!==expected))
    $fatal(1,"LEVEL_FAIL kind=%0d unit=%0d actual=%0d expected=%0d",kind,u,frame_level,expected);
   if(numeric_error)$fatal(1,"LEVEL_FAIL numeric");checks=checks+1;
  end
 endtask
 initial begin
  repeat(5)@(negedge clk);rst_n=1;
  whole(0,0);whole(1,640);whole(2,8388607);
  // 部分帧后重新开始，旧部分累计不得污染新结果。
  start_frame(1);run_unit(0);whole(3,4);
  $display("LEVEL_PASS cases=4 unit_checks=%0d units=%0d backpressure=1 restart=1 legacy_cycle_equal=1",checks,units);$finish;
 end
 initial begin #6000000;$fatal(1,"LEVEL_FAIL timeout");end
endmodule
