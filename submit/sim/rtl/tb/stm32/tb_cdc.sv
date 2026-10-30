`timescale 1ns/1ps
// 异步相位、满/空、持续背压、整字稳定、冷复位丢弃旧代数据。
module tb_cdc;
 reg src_clk=0,dst_clk=0,rst_n=0;
 always #8.138 src_clk=~src_clk;
 initial begin #2.31;forever #5 dst_clk=~dst_clk;end
 reg src_valid=0,dst_ready=0;
 wire src_ready,dst_valid;
 reg [991:0] src_data;
 wire [991:0] dst_data;
 integer sent=0,received=0,epoch=1,checks=0;
 reg held=0;reg [991:0] held_word;
 reg [31:0] random_state=32'h12345678;
 ss_async_word #(.WIDTH(992),.CAPACITY(1)) dut(.*,.src_rst_n(rst_n),.dst_rst_n(rst_n));
 function [991:0] word(input integer e,input integer n);
  for(integer k=0;k<31;k=k+1)word[k*32+:32]=(e<<24)^(n*257)^(k*32'h10203);
 endfunction
 always @(posedge src_clk)if(rst_n && src_valid && src_ready)sent=sent+1;
 always @(posedge dst_clk)begin
  if(!rst_n)held=0;
  else begin
   if(held && (!dst_valid || dst_data!==held_word))$fatal(1,"CDC_FAIL unstable stalled word");
   if(dst_valid && dst_ready)begin
    if(dst_data!==word(epoch,received))$fatal(1,"CDC_FAIL order/atomicity epoch=%0d word=%0d",epoch,received);
    received=received+1;checks=checks+1;
   end
   held=dst_valid && !dst_ready;held_word=dst_data;
  end
 end
 task feed(input integer count);
  for(integer n=0;n<count;n=n+1)begin
   @(negedge src_clk);src_data=word(epoch,n);src_valid=1;
   do @(posedge src_clk);while(!src_ready);
   @(negedge src_clk);src_valid=0;
  end
 endtask
 initial begin
  repeat(20)@(negedge src_clk);rst_n=1;
  // 第一代故意留在背压中再冷复位，第二代不能读出旧字。
  feed(1);wait(dst_valid);repeat(100)@(negedge dst_clk);
  if(src_ready)$fatal(1,"CDC_FAIL logical capacity is not one");
  @(negedge src_clk);rst_n=0;src_valid=0;sent=0;received=0;epoch=2;
  repeat(20)@(negedge src_clk);rst_n=1;
  fork
   feed(500);
   begin
    while(received<500)begin
     @(negedge dst_clk);
     random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
     dst_ready=random_state[0] && random_state[3];
    end
   end
  join
  repeat(30)@(negedge dst_clk);
  if(dst_valid || received!=500 || sent!=500)$fatal(1,"CDC_FAIL lost/duplicate word");
  $display("CDC_PASS checks=%0d words=%0d width=992 capacity=1 cold_flush=1",checks,received);$finish;
 end
 initial begin #2000000;$fatal(1,"CDC_FAIL timeout");end
endmodule
