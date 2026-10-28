`timescale 1ns/1ps
module tb_audiotime;
 reg src_clk=0,clk=0,read_clock=1;
 always #8.138 src_clk=~src_clk;
 always #5 if(read_clock)clk=~clk;
 reg src_rst_n=0,rst_n=0,enable=0,raw_valid=0,raw_clip=0,raw_fault=0;
 reg [95:0] raw_pcm=0;
 wire sample_valid,sample_clip,fault;wire [95:0] sample_pcm;wire [63:0] sample_index;
 ss_pcm_time_cdc dut(.*);
 integer received=0;reg check_time=1;
 always @(posedge clk)if(sample_valid && check_time)begin
  if(sample_index!==64'h00000000fffffe00+received || sample_pcm!==96'(received))
   $fatal(1,"AUDIOTIME_FAIL time=%h sample=%h n=%0d",sample_index,sample_pcm,received);
  received=received+1;
 end
 task send(input integer n);
  @(negedge src_clk);raw_valid=1;raw_pcm=n;
  @(negedge src_clk);raw_valid=0;repeat(19)@(negedge src_clk);
 endtask
 initial begin
  repeat(20)@(negedge src_clk);src_rst_n=1;rst_n=1;
  wait(dut.ready);@(negedge src_clk);enable=1;
  // Deliberately seed the source register to exercise carry without 2^32 clocks.
  dut.count=64'h00000000fffffe00;
  for(integer n=0;n<514;n=n+1)send(n);
  wait(received==514);if(fault)$fatal(1,"AUDIOTIME_FAIL unexpected fault");
  check_time=0;
  @(negedge clk);read_clock=0;
  for(integer n=0;n<40;n=n+1)send(n);
  if(!dut.failed)$fatal(1,"AUDIOTIME_FAIL full crossing did not fault");
  if(dut.count!==64'h000000010000002a)$fatal(1,"AUDIOTIME_FAIL source time stopped on full");
  read_clock=1;repeat(40)@(negedge clk);
  if(!fault)$fatal(1,"AUDIOTIME_FAIL fault did not cross");
  enable=0;repeat(40)@(negedge src_clk);
  if(fault)$fatal(1,"AUDIOTIME_FAIL disabled recovery");
  $display("AUDIOTIME_PASS low32_carry=1 source_advances_on_full=1 explicit_fault=1");$finish;
 end
 initial begin #1000000;$fatal(1,"AUDIOTIME_FAIL timeout received=%0d src=%h fault=%b rdclk=%b",received,dut.count,fault,read_clock);end
endmodule
