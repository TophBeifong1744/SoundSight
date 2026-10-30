`timescale 1ns/1ps
module tb_axi;
 reg clk=0;always #5 clk=~clk;
 reg aresetn=0;
 `include "axi_tasks.svh"
 wire [6:0] address;
 wire commit,write_access,format_error;
 wire [31:0] write_data;
 reg [31:0] memory[0:31];
 wire [31:0] read_data=memory[address[6:2]];
 ss_axi_lite_regs dut(.*);
 integer writes=0,reads=0,errors=0;
 always @(posedge clk)if(aresetn)begin
   if(commit && write_access)begin memory[address[6:2]]<=write_data;writes=writes+1;end
   if(commit && !write_access)reads=reads+1;
   if(format_error)errors=errors+1;
 end
 reg [31:0] value;
 initial begin
   for(integer i=0;i<32;i=i+1)memory[i]=0;
   repeat(5)tick();aresetn=1;
   for(integer i=0;i<32;i=i+1)begin
     wr(i*4,32'ha5100000+i,i%4,(31-i)%4,15,0);expect_read(i*4,32'ha5100000+i);
   end
   wr(0,32'hffffffff,0,3,3,2);expect_read(0,32'ha5100000);
   wr(1,32'hffffffff,3,0,15,2);wr('h800,32'hffffffff,0,0,15,2);
   rd(2,value,2);check(value==32'hdeadbeef,"unaligned read");rd('h100,value,2);
   // 半个写事务遇到复位：不得在恢复后把旧AW与新W拼成写。
   tick();s_axi_awaddr=4;s_axi_awvalid=1;do @(posedge clk);while(!s_axi_awready);tick();s_axi_awvalid=0;
   aresetn=0;repeat(3)tick();aresetn=1;repeat(3)tick();
   check(!s_axi_bvalid && !s_axi_rvalid,"response survived reset");
   wr(8,32'h76543210,4,0,15,0);expect_read(8,32'h76543210);
   check(writes==33 && reads==34 && errors==5,"commit exactly once/error count");
   $display("AXI_PASS checks=%0d writes=%0d reads=%0d errors=%0d",checks,writes,reads,errors);$finish;
 end
 initial begin #2000000;$fatal(1,"AXI_FAIL timeout");end
endmodule
