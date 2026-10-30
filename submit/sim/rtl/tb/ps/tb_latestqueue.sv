`timescale 1ns/1ps
// Directed ownership tests use externally observable sequence/payload values.
module tb_latestqueue;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,frame_valid=0,replace_enable=1,frame_energy_valid=1;
 reg [128:0] frame_meta=0;
 reg [959:0] frame_pairs=0;
 reg [31:0] frame_flags=0,frame_energy=0;
 reg [2:0] command=0;
 wire [128:0] locked_meta; wire [959:0] locked_pairs;
 wire [31:0] locked_flags,locked_energy,locked_sequence,drop_count;
 wire locked,queued,occupied,locked_energy_valid,gap,exhausted,snapshot_error,overflow_pulse,counter_error;
 ss_snapshot_queue #(.META_ENABLE(1),.LATEST_WINS(1)) dut(.*);
 integer checks=0,i;
 task check(input bit okay,input string why);
   checks++; if(!okay)$fatal(1,"LATESTQUEUE_FAIL %s",why);
 endtask
 task step(input integer cmd,input bit arrival,input integer value);
   @(negedge clk); command=3'(cmd); frame_valid=arrival;
   frame_pairs={30{32'(value)}};frame_flags=value;frame_energy=value+100;frame_meta=129'(value+200);
   @(posedge clk);#1;
 endtask
 task reset_all;
   @(negedge clk);rst_n=0;frame_valid=0;command=0;replace_enable=1;
   repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
 endtask
 task expect_locked(input integer seqno,input integer value);
   check(locked && locked_sequence==seqno,"locked sequence");
   check(locked_pairs=={30{32'(value)}} && locked_flags==value,"whole locked payload");
   check(locked_energy==value+100 && locked_energy_valid && locked_meta==value+200,"locked level/meta");
 endtask
 initial begin
   reset_all();step(0,1,10);step(0,1,20);step(0,1,30);
   check(drop_count==1 && gap && !overflow_pulse,"replace oldest READY without hard overflow");
   step(1,0,0);expect_locked(2,20);
   for(i=4;i<=100;i++)begin
     step(0,1,i*10);expect_locked(2,20);
     check(!overflow_pulse && !snapshot_error,"locked reader never disrupted");
   end
   check(drop_count==98,"all overwritten READY frames accounted");
   step(4,1,1010);check(drop_count==98 && !overflow_pulse,"same-cycle consume is free space");
   step(1,0,0);expect_locked(100,1000);
   step(2,1,1020);check(drop_count==99,"release returns ownership for eviction");
   step(1,0,0);expect_locked(101,1010);
   reset_all();step(0,1,10);step(0,1,20);step(1,1,30);expect_locked(1,10);
   check(drop_count==1 && !overflow_pulse,"acquire locks before eviction");
   step(4,0,0);step(1,0,0);expect_locked(3,30);
   reset_all();step(0,1,10);step(0,1,20);replace_enable=0;step(0,1,30);
   check(drop_count==1 && overflow_pulse,"replacement disabled preserves both slots");
   step(1,0,0);expect_locked(1,10);step(4,0,0);step(1,0,0);expect_locked(2,20);
   reset_all();step(0,1,10);step(0,1,20);step(3,1,30);
   check(snapshot_error && overflow_pulse,"invalid command cannot evict evidence");
   step(1,0,0);expect_locked(1,10);
   reset_all();step(0,1,10);step(0,1,20);
   // Direct deposit only for 2^32 boundaries, not ordinary queue expectations.
   @(negedge clk);dut.drop_count=32'hffffffff;frame_valid=0;
   step(0,1,30);check(drop_count==32'hffffffff && !overflow_pulse,"drop saturation");
   @(negedge clk);dut.sequence_count=32'hfffffffe;frame_valid=0;
   step(0,1,40);check(exhausted && counter_error,"sequence exhaustion");
   step(0,1,50);check(counter_error,"exhausted refuses new write");
   step(1,0,0);expect_locked(3,30);step(4,0,0);step(1,0,0);
   check(locked_sequence==32'hffffffff && locked_pairs=={30{32'd40}},"no wrap or exhausted replacement");
   reset_all();check(!occupied && drop_count==0 && !gap,"cold reset");
   $display("LATESTQUEUE_PASS checks=%0d",checks);$finish;
 end
 initial begin #100000;$fatal(1,"LATESTQUEUE_FAIL timeout");end
endmodule
