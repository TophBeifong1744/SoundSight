`timescale 1ns/1ps
// 原发布槽的音量元数据必须与六对同时锁存，背压/丢新不覆盖旧记录。
module tb_levelstore;
 reg clk=0;always #5 clk=~clk;
 reg cold_rst_n=0,frame_start=0,frame_start_bist=0,pair_event=0,frame_finish=0,frame_cancelled=0;
 reg [2:0] pair_index=0;reg [159:0] pair_words=0;reg [7:0] first_error=0;
 reg [23:0] phat_stages=24'h111111,ifft_stages=24'h111111;
 reg [31:0] frame_level=0;reg frame_level_valid=1,feature_ready=0;
 wire accepting,feature_valid,drop_pulse,gap,counter_exhausted,source_protocol_error,feature_level_valid;
 wire [31:0] feature_frame_id,feature_frame_flags,drop_count,feature_level;wire [959:0] feature_pairs;
 f1a_frame_store #(.LEVEL_ENABLE(1)) dut(.frame_meta(129'b0),.feature_meta(),.*);
 task tick;@(negedge clk);endtask
 task publish(input integer value,input bit cancelled);
  tick();frame_level=value;frame_cancelled=cancelled;frame_start=1;tick();frame_start=0;
  for(integer p=0;p<6;p=p+1)begin pair_index=p;pair_words=160'(value+p);pair_event=1;tick();end
  pair_event=0;frame_finish=1;tick();frame_finish=0;tick();
 endtask
 initial begin
  repeat(5)tick();cold_rst_n=1;
  publish(100,0);
  if(!feature_valid || !feature_level_valid || feature_level!=100)$fatal(1,"LEVELSTORE_FAIL first");
  publish(900,0);
  if(feature_level!=100 || feature_pairs[31:0]!=100 || drop_count!=1)$fatal(1,"LEVELSTORE_FAIL overwritten");
  feature_ready=1;tick();feature_ready=0;
  publish(300,1);
  if(!feature_valid || feature_level_valid || !feature_frame_flags[20])$fatal(1,"LEVELSTORE_FAIL cancel");
  feature_ready=1;tick();feature_ready=0;
  publish(400,0);
  if(feature_level!=400 || !feature_level_valid || feature_frame_id!=4)$fatal(1,"LEVELSTORE_FAIL recovery");
  $display("LEVELSTORE_PASS held_old=100 dropped_new=900 cancelled_invalid=1 recovered=400");$finish;
 end
 initial begin #10000;$fatal(1,"LEVELSTORE_FAIL timeout");end
endmodule
