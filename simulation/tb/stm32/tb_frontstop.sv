`timescale 1ns/1ps
// 官方FFT/IFFT完整接合；PCM在CIC出口注入，未强制DUT状态。
module tb_frontstop;
 reg clk=0;always #8.138 clk=~clk;
 reg rst_n=0,enable=0;
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
 ss_clean_compute #(.WARMUP_SAMPLES(16)) dut(.feature_level(),.feature_level_valid(),.acq_clk(clk),.acq_rst_n(rst_n),.acq_enable(enable),.active(),.*);
 reg fixture_valid=0;
 reg [95:0] fixture_pcm=0;
 reg [31:0] random_state=32'h1765ca19;
 integer cycles=0,frames=0,checks=0,n,p,frame_start_cycle=0,fd;
 reg [31:0] word0;
 task samples(input integer count);
   for(integer i=0;i<count;i=i+1)begin
     repeat(16)@(negedge clk);
     random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
     fixture_pcm={4{{4{random_state[19]}},random_state[19:0]}};fixture_valid=1;
     @(negedge clk);fixture_valid=0;
   end
 endtask
 always @(posedge clk)begin
   cycles<=cycles+1;
   if(dut.begin_valid && dut.begin_ready)frame_start_cycle=cycles;
   if(cycles%50000==0)$display("FRONTSTOP_PROGRESS cycle=%0d frontend=%0d backend=%0d frames=%0d faults=%03x",cycles,debug_frontend,debug_backend,frames,source_faults);
   if(feature_valid && feature_ready)begin
     frames=frames+1;
     $display("FRONTSTOP_FRAME n=%0d cycles=%0d latency=%0d flags=%08x faults=%03x",frames,cycles,cycles-frame_start_cycle,feature_flags,source_faults);
     if(source_faults!=0)$fatal(1,"FRONTSTOP_FAIL source fault");
     if(frames==1)begin
       if(feature_flags!=32'h00100010)$fatal(1,"FRONTSTOP_FAIL cancellation flags");
     end else begin
       if(feature_flags!=32'h10)$fatal(1,"FRONTSTOP_FAIL normal flags");
       if(cycles-frame_start_cycle>=655360)$fatal(1,"FRONTSTOP_FAIL exceeds 512-sample hop budget");
       for(p=0;p<6;p=p+1)begin
         word0=feature_pairs[p*160+:32];checks=checks+1;
         if(word0[7:0]!=0 || word0[31:24]!=8'h11 || !word0[11] || !word0[13] || word0[10:8]!=p)
           $fatal(1,"FRONTSTOP_FAIL pair=%0d word0=%08x",p,word0);
         $fdisplay(fd,"%0d %0d %08x %08x %08x %08x %08x",frames,p,word0,feature_pairs[p*160+32+:32],feature_pairs[p*160+64+:32],feature_pairs[p*160+96+:32],feature_pairs[p*160+128+:32]);
       end
     end
   end
   if(cycles>1300000)$fatal(1,"FRONTSTOP_FAIL timeout");
 end
 initial begin
   fd=$fopen("frontstop_six_pairs.txt","w");
   force dut.sample_valid=fixture_valid;force dut.sample_pcm=fixture_pcm;force dut.sample_clipped=0;
   repeat(12)@(negedge clk);rst_n=1;repeat(12)@(negedge clk);enable=1;
   samples(1024);wait(debug_frontend==4 && dut.frontend.in_count>20);
   @(negedge clk);enable=0;
   wait(frames==1);wait(!draining);
   if(dut.frontend.in_count!=1024 || dut.frontend.out_count!=1024 || !dut.frontend.status_seen)
     $fatal(1,"FRONTSTOP_FAIL official forward FFT not drained");
   repeat(20)@(negedge clk);enable=1;
   samples(1024);wait(frames==2);@(negedge clk);enable=0;wait(!draining);
   $fclose(fd);$display("FRONTSTOP_PASS frames=%0d checks=%0d cycles=%0d official_fft_ifft=1 pcm_fixture=1",frames,checks,cycles);$finish;
 end
endmodule
