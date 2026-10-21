`timescale 1ns/1ps
module tb_preprocess;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,frame_start=0,unit_start=0,domain=0;
 reg [1:0] channel=0;
 wire read_enable,read_valid,copy_done,unit_ready,unit_done,out_valid,out_last,numeric_error;
 wire [9:0] read_index;
 wire [95:0] read_pcm;
 reg out_ready=0;
 wire signed [28:0] out_real;
 reg [95:0] sample_memory[0:1023];
 reg [28:0] expected[0:8191];
 reg [95:0] response;
 reg response_valid=0;
 assign read_pcm=response;assign read_valid=response_valid;
 ss_preprocess dut(.frame_level(),.frame_level_valid(),.*);
 always @(posedge clk)begin response_valid<=read_enable;if(read_enable)response<=sample_memory[read_index];end
 integer cycle=0,outputs=0,unit_no,copy_events=0,checks=0;
 reg held=0;
 reg [29:0] held_word;
 always @(negedge clk)begin cycle=cycle+1;out_ready=(cycle%7!=0 && cycle%11!=0);end
 always @(posedge clk)if(rst_n)begin
   if(copy_done)copy_events=copy_events+1;
   if(held && (!out_valid || {out_last,out_real}!==held_word))$fatal(1,"PREPROCESS_FAIL unstable backpressure");
   held=out_valid && !out_ready;held_word={out_last,out_real};
   if(out_valid && out_ready)begin
     if(out_real!==expected[outputs] || out_last!=(outputs%1024==1023))
       $fatal(1,"PREPROCESS_FAIL point=%0d actual=%08x expected=%08x",outputs,out_real,expected[outputs]);
     outputs=outputs+1;checks=checks+1;
   end
 end
 initial begin
   $readmemh("pcm_vectors.mem",sample_memory);$readmemh("preprocess_gold.mem",expected);
   repeat(5)@(negedge clk);rst_n=1;@(negedge clk);frame_start=1;
   @(negedge clk);frame_start=0;wait(unit_ready);
   for(unit_no=0;unit_no<8;unit_no=unit_no+1)begin
     @(negedge clk);domain=unit_no/4;channel=unit_no%4;unit_start=1;
     @(negedge clk);unit_start=0;wait(unit_done);@(negedge clk);
   end
   if(outputs!=8192 || numeric_error || copy_events!=1)$fatal(1,"PREPROCESS_FAIL totals");
   $display("PREPROCESS_PASS exact_points=%0d checks=%0d copied_frames=%0d",outputs,checks,copy_events);$finish;
 end
 initial begin #2000000;$fatal(1,"PREPROCESS_FAIL timeout");end
endmodule
