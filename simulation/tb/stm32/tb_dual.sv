`timescale 1ns/1ps
// 双时钟完整算法：原始PCM出口注入，经真实异步FIFO到100MHz计算，再整帧回61.44MHz。
// 正常、在途STOP取消、恢复；官方FFT/IFFT，数值与原单域判据相同。
module tb_dual;
 reg clk=0;always #5 clk=~clk;
 reg io_clk=0;initial begin #2.3;forever #8.138 io_clk=~io_clk;end
 reg rst_n=0,enable=0;
 wire io_rst_n=rst_n;
 reg [3:0] pdm_data=0;
 wire [3:0] pdm_clocks;
 wire feature_valid;
 reg feature_ready=1;
 wire [959:0] feature_pairs;
 wire [31:0] feature_flags;
 wire draining;
 wire [11:0] source_faults;
 wire [3:0] debug_frontend;
 wire [4:0] debug_backend;
 ss_dual_compute #(.WARMUP_SAMPLES(16)) dut(.feature_level(),.feature_level_valid(),.*);
 reg fixture_valid=0;
 reg [95:0] fixture_pcm=0;
 reg [31:0] random_state=32'h1765ca19;
 integer cycles=0,frames=0,checks=0,n,p,frame_start_cycle=0,fd;
 reg [31:0] word0;
 task samples(input integer count);
   for(integer i=0;i<count;i=i+1)begin
     repeat(16)@(negedge io_clk);
     random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
     fixture_pcm={4{{4{random_state[19]}},random_state[19:0]}};fixture_valid=1;
     @(negedge io_clk);fixture_valid=0;
   end
 endtask
 always @(posedge clk)begin
   cycles<=cycles+1;
   if(dut.core.begin_valid && dut.core.begin_ready)frame_start_cycle=cycles;
   if(cycles%50000==0)$display("DUAL_PROGRESS cycle=%0d frontend=%0d backend=%0d frames=%0d faults=%03x",cycles,debug_frontend,debug_backend,frames,source_faults);
   if(dut.core_valid && dut.core_ready && cycles-frame_start_cycle>=655360)$fatal(1,"DUAL_FAIL original cycle budget");
 end
 always @(posedge io_clk)begin
   if(feature_valid && feature_ready)begin
     frames=frames+1;
     $display("DUAL_FRAME n=%0d cycles=%0d latency=%0d flags=%08x faults=%03x",frames,cycles,cycles-frame_start_cycle,feature_flags,source_faults);
     if(source_faults!=0)$fatal(1,"DUAL_FAIL source fault");
     if(frames==2)begin
       if(feature_flags!=32'h00100010)$fatal(1,"DUAL_FAIL cancellation flags");
     end else begin
       if(feature_flags!=32'h10)$fatal(1,"DUAL_FAIL normal flags");
       if(cycles-frame_start_cycle>=655360)$fatal(1,"DUAL_FAIL exceeds 512-sample hop budget");
       for(p=0;p<6;p=p+1)begin
         word0=feature_pairs[p*160+:32];checks=checks+1;
         if(word0[7:0]!=0 || word0[31:24]!=8'h11 || !word0[11] || !word0[13] || word0[10:8]!=p)
           $fatal(1,"DUAL_FAIL pair=%0d word0=%08x",p,word0);
         $fdisplay(fd,"%0d %0d %08x %08x %08x %08x %08x",frames,p,word0,feature_pairs[p*160+32+:32],feature_pairs[p*160+64+:32],feature_pairs[p*160+96+:32],feature_pairs[p*160+128+:32]);
       end
     end
   end
   if(cycles>1300000)$fatal(1,"DUAL_FAIL timeout");
 end
 initial begin
   fd=$fopen("dual_six_pairs.txt","w");
   force dut.core.raw_valid=fixture_valid;force dut.core.raw_pcm=fixture_pcm;force dut.core.raw_clip=0;
   repeat(12)@(negedge io_clk);rst_n=1;repeat(12)@(negedge io_clk);enable=1;
   samples(1024);wait(frames==1);wait(!dut.core.front_busy && !dut.core.backend_busy);
   samples(512);wait(debug_backend==8);repeat(20)@(negedge io_clk);enable=0;
   wait(frames==2);wait(!draining);repeat(20)@(negedge io_clk);enable=1;
   samples(1024);wait(frames==3);@(negedge io_clk);enable=0;wait(!draining);
   $fclose(fd);$display("DUAL_PASS frames=%0d checks=%0d cycles=%0d official_fft_ifft=1 pcm_fixture=1",frames,checks,cycles);$finish;
 end
endmodule
