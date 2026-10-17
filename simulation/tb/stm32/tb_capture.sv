`timescale 1ns/1ps
module tb_capture;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,enable=0,sample_valid=0,sample_clipped=0;
 reg [95:0] sample_pcm=0;
 wire window_valid,read_valid,overflow,numeric_error,counter_exhausted;
 reg window_ready=0,release_window=0,read_enable=0;
 wire [31:0] window_frame;
 reg [9:0] read_index=0;
 wire [95:0] read_pcm;
 ss_pcm_windows dut(.*);
 integer n,checks=0,base=0,received=0;
 reg reading=0;
 function automatic [95:0] sample(input integer index);
   sample={24'(index+30000),24'(index+20000),24'(index+10000),24'(index)};
 endfunction
 task tick;@(negedge clk);endtask
 task feed(input integer first,input integer count);
   for(integer k=first;k<first+count;k=k+1)begin sample_pcm=sample(k);sample_valid=1;tick();sample_valid=0;repeat(3)tick();end
 endtask
 task read_window(input integer start_index,input integer id);
   begin
     wait(window_valid);tick();if(window_frame!=id)$fatal(1,"CAPTURE_FAIL id");
     base=start_index;received=0;reading=1;window_ready=1;tick();window_ready=0;
     for(integer j=0;j<1024;j=j+1)begin read_enable=1;read_index=j;tick();end
     read_enable=0;repeat(2)tick();
     if(received!=1024)$fatal(1,"CAPTURE_FAIL reads=%0d",received);
     reading=0;release_window=1;tick();release_window=0;
   end
 endtask
 always @(posedge clk)if(read_valid)begin
   if(!reading || read_pcm!==sample(base+received))$fatal(1,"CAPTURE_FAIL overwritten index=%0d got=%024x",received,read_pcm);
   received=received+1;checks=checks+1;
 end
 initial begin
   repeat(4)tick();rst_n=1;enable=1;tick();
   // 采集与拷窗同时进行，检查1024/512的重叠位置而不是只看帧数。
   fork
     begin feed(0,2048);end
     begin read_window(0,1);read_window(512,2);read_window(1024,3);end
   join
   if(overflow || numeric_error)$fatal(1,"CAPTURE_FAIL normal faults");
   // 不领取下一窗：只允许一个待交描述，后续边界应报错而不替换原frame。
   feed(2048,1024);
   if(!overflow || window_frame!=4)$fatal(1,"CAPTURE_FAIL pending overwrite/overrun missing");
   enable=0;repeat(3)tick();if(window_valid || overflow)$fatal(1,"CAPTURE_FAIL disabled cleanup");
   $display("CAPTURE_PASS windows=3 exact_samples=%0d overflow_preserves_pending=1",checks);$finish;
 end
 initial begin #1000000;$fatal(1,"CAPTURE_FAIL timeout");end
endmodule
