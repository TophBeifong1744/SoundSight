`timescale 1ns/1ps
module tb_pair;
reg clk=0,rst_n=0,begin_valid=0,s_valid=0,end_valid=0,cancel=0;
reg [31:0] begin_frame=0,s_frame=0,end_frame=0;
reg [1:0] s_channel=0;
reg [9:0] s_bin=0;
reg signed [24:0] s_real=0,s_imag=0;
reg s_numeric_valid=1,end_cancelled=0;
reg [7:0] end_error=0;
wire begin_ready,s_ready,end_ready,busy,ip_obligation;
wire feature_valid,feature_drop_pulse,feature_gap,feature_counter_exhausted,feature_source_protocol_error;
reg feature_ready=0;
wire [31:0] feature_frame_id,feature_frame_flags,feature_drop_count;
wire [959:0] feature_pairs;
wire [4:0] debug_state;
ss_pair_engine dut(.*);

integer cycle=0,checks=0,frames=0,drops=0,handshakes=0,pair_events=0;
integer mi=0,mo=0,mp=-1,mode=0,n,p,lane,bin,token=0,fd;
reg ma=0,ms=0;
reg [959:0] saved_pairs,expected_work;
reg [5:0] expected_seen=0;
reg [1023:0] held_frame;
reg was_held=0;
reg [31:0] w;
integer wanted_lag[0:5];
always #5 clk=~clk;
task tick; begin @(negedge clk);#1;end endtask
task check(input bit ok,input string why);begin checks=checks+1;if(!ok)$fatal(1,"PAIR_FAIL %s cycle=%0d state=%0d pair=%0d",why,cycle,debug_state,dut.pair_id);end endtask
function automatic integer corr(input integer pair_no,input integer ix);
 integer lag_here,lim;
 begin
 lag_here=ix>512?ix-1024:ix;lim=(pair_no==1 || pair_no==4)?8:6;
 corr=-20-pair_no;
 if(lag_here==wanted_lag[pair_no])corr=1000+pair_no*100;
 else if(lag_here==wanted_lag[pair_no]-1)corr=800+pair_no*11;
 else if(lag_here==wanted_lag[pair_no]+1)corr=600+pair_no*13;
 else if(lag_here==lim)corr=200+pair_no*7;
 if(mode==4)begin
 corr=-16777215;
 if(lag_here==wanted_lag[pair_no])corr=16777215;
 else if(lag_here==wanted_lag[pair_no]-1)corr=-16777216;
 else if(lag_here==wanted_lag[pair_no]+1)corr=-1234567;
 else if(lag_here==lim)corr=-9;
 end
 end
endfunction
// 明确为 IFFT 接口刺激器：回放预置相关值，不模拟或宣称官方 IFFT 数值。
always @* begin
 force dut.ip_event_unexpected_last=0;force dut.ip_event_missing_last=0;force dut.ip_event_overflow=0;
 force dut.ip_config_ready=(cycle%7!=0);
 force dut.ip_input_ready=ma && mi<1024 && cycle%5!=0;
 force dut.ip_output_valid=ma && mi==1024 && mo<1024;
 force dut.ip_output_index=mo;force dut.ip_output_last=(mo==1023);
 force dut.ip_output_data={39'b0,25'(corr(mp,mo))};
 force dut.ip_status_valid=ma && mo==1024 && !ms;
 force dut.ip_status_data=(mode==2 && mp==2)?8'h1:0;
end
always @(posedge clk) begin
 cycle<=cycle+1;
 if(!rst_n)begin mi<=0;mo<=0;mp<=-1;ma<=0;ms<=0;was_held<=0;expected_seen<=0;expected_work<=0;end
 else begin
 if(begin_valid && begin_ready)begin mp<=-1;expected_seen<=0;expected_work<=0;end
 if(dut.ip_config_valid && dut.ip_config_ready)begin mi<=0;mo<=0;mp<=mp+1;ma<=1;ms<=0;end
 if(dut.ip_input_valid && dut.ip_input_ready)mi<=mi+1;
 if(dut.ip_output_valid && dut.ip_output_ready)mo<=mo+1;
 if(dut.ip_status_valid && dut.ip_status_ready)begin ms<=1;ma<=0;end
 if(was_held)check(feature_valid && {feature_frame_id,feature_frame_flags,feature_pairs}===held_frame,"backpressure payload changed");
 was_held<=feature_valid && !feature_ready;
 held_frame<={feature_frame_id,feature_frame_flags,feature_pairs};
 if(feature_valid && feature_ready)handshakes<=handshakes+1;
 if(feature_drop_pulse)drops<=drops+1;
 for(integer j=0;j<6;j=j+1)if(expected_seen[j])check(dut.feature_store.work_pairs[j*160+:160]===expected_work[j*160+:160],"earlier pair overwritten");
 if(debug_state==12)begin
   pair_events<=pair_events+1;
   expected_work[dut.pair_id*160+:160]<=dut.raw_words;expected_seen[dut.pair_id]<=1;
 end
 end
end
task start_frame(input integer scenario,input bit bad_front);
 begin
 mode=scenario;token=token+1;begin_frame=token;
 while(!begin_ready)tick();
 begin_frame=token;s_frame=token;end_frame=token;begin_valid=1;
 s_numeric_valid=1;end_error=0;end_cancelled=0;tick();begin_valid=0;
 if(!bad_front)begin
   for(lane=0;lane<4;lane=lane+1)for(bin=0;bin<513;bin=bin+1)begin
     s_valid=1;s_channel=lane;s_bin=bin;s_real=scenario==3?0:104+lane;s_imag=0;
     check(s_ready,"source unexpectedly backpressured");tick();
   end
 end else end_error=(scenario==5)?3:4;
 s_valid=0;end_valid=1;check(end_ready,"terminal not ready");tick();end_valid=0;
 end
endtask
task wait_done;
 begin
 n=0;while(busy && n<2000000)begin tick();n=n+1;end
 check(!busy,"backend timeout");tick();
 end
endtask
task inspect(input integer id,input integer good_pairs,input bit cancelled,input integer error_code);
 begin
 check(feature_valid,"missing full frame");check(feature_frame_id==id,"frame sequence");
 check(feature_frame_flags[4] && feature_frame_flags[20]==cancelled && feature_frame_flags[31:24]==error_code,"frame flags");
 for(p=0;p<6;p=p+1)begin
 w=feature_pairs[p*160+:32];
 check(w[10:8]==p && w[23]==0,"pair echo/reserved bit");
 check(w[27:24]!=0 && w[31:28]!=0,"pending stage escaped");
 if(p<good_pairs)begin
 check(w[11] && w[12] && w[13] && w[27:24]==1 && w[31:28]==1,"raw flags");
 check($signed(w[7:0])==wanted_lag[p],"lag/sign");check(w[22:16]==79,"mask_count");
 check($signed(feature_pairs[p*160+32+:32])==(mode==4?16777215:1000+100*p),"peak");
 check($signed(feature_pairs[p*160+64+:32])==(mode==4?-16777216:800+11*p),"left");
 check($signed(feature_pairs[p*160+96+:32])==(mode==4?-1234567:600+13*p),"right");
 check($signed(feature_pairs[p*160+128+:32])==(mode==4?-9:200+7*p),"last margin update missing");
 end else check(!w[11] && !w[12] && !w[13] && w[7:0]==0 && w[22:16]==0 && feature_pairs[p*160+32+:128]==0,"invalid payload not zero");
 $fdisplay(fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",id,p,$signed(w[7:0]),$signed(feature_pairs[p*160+32+:32]),$signed(feature_pairs[p*160+64+:32]),$signed(feature_pairs[p*160+96+:32]),$signed(feature_pairs[p*160+128+:32]),w[22:16],w[11],w[27:24],w[31:28],w[14],w[15],feature_frame_flags[31:24]);
 end
 frames=frames+1;
 end
endtask
task consume;
 begin feature_ready=1;tick();feature_ready=0;check(!feature_valid,"not single-consumed");repeat(3)tick();end
endtask
initial begin
 fd=$fopen("six-pair-output.csv","w");
 $fdisplay(fd,"frame,pair,lag,peak,left,right,second,mask,raw_valid,phat,ifft,cancelled,numeric_error,first_error");
 wanted_lag[0]=-5;wanted_lag[1]=2;wanted_lag[2]=0;wanted_lag[3]=-2;wanted_lag[4]=-7;wanted_lag[5]=4;
 repeat(4)tick();rst_n=1;tick();
 start_frame(0,0);wait_done();inspect(1,6,0,0);
 saved_pairs=feature_pairs;repeat(61)tick();
 // 输出槽被占用仍跑完整六对、排空 IFFT，整帧丢新，旧载荷不动。
 start_frame(0,0);wait_done();check(feature_drop_count==1 && feature_gap,"drop missing");
 check(feature_pairs===saved_pairs && feature_frame_id==1,"blocked frame overwritten");consume();
 start_frame(0,0);wait_done();inspect(3,6,0,0);consume();
 // 第三对 RUN_IP 中 STOP，必须把已启动的 1024/1024/status 排空。
 start_frame(1,0);
 while(!(debug_state==8 && dut.pair_id==2 && mi>33))tick();
 cancel=1;tick();cancel=0;wait_done();inspect(4,2,1,0);
 check(mi==1024 && mo==1024 && ms,"cancel did not drain IP");consume();
 start_frame(2,0);wait_done();inspect(5,2,0,8);consume();
 start_frame(3,0);wait_done();inspect(6,0,0,0);consume();
 start_frame(0,1);wait_done();inspect(7,0,0,4);consume();
 // LAG_MARGIN 最后沿取消：不能泄漏本对 raw_valid。
 start_frame(0,0);
 while(!(debug_state==22 && dut.pair_id==0 && dut.lag==6))tick();
 cancel=1;tick();cancel=0;wait_done();inspect(8,0,1,0);consume();
 // STOP 一直保持至终态，也不能把原内部 report 卡住。
 start_frame(0,0);
 while(!(debug_state==8 && dut.pair_id==0 && mi>19))tick();
 cancel=1;wait_done();inspect(9,0,1,0);cancel=0;consume();
 start_frame(4,0);wait_done();inspect(10,6,0,0);consume();
 start_frame(5,1);wait_done();inspect(11,0,0,4);consume();
 check(!feature_source_protocol_error,"unexpected collector protocol error");
 check(handshakes==10 && drops==1,"handoff/drop accounting");
 $fclose(fd);$display("PAIR_PASS frames=%0d handshakes=%0d drops=%0d pair_events=%0d checks=%0d cycles=%0d",frames,handshakes,drops,pair_events,checks,cycle);$finish;
end
initial begin #200000000;$fatal(1,"TEST_TIMEOUT");end
endmodule
module ifft25_official (
    input wire clk,cold_rst_n,
    input wire [23:0] config_data, input wire config_valid, output wire config_ready,
    input wire [63:0] input_data, input wire input_valid,input_last,
    output wire input_ready,
    output wire [63:0] output_data, output wire [9:0] output_index,
    output wire output_valid,output_last, input wire output_ready,
    output wire [7:0] status_data, output wire status_valid,input wire status_ready,
    output wire unexpected_last,missing_last,overflow,
    output wire frame_started,status_halt,input_halt,output_halt
);
endmodule
