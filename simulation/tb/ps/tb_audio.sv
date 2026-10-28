`timescale 1ns/1ps
module tb_audio;
 reg src_clk=0,clk=0;
 always #8.138 src_clk=~src_clk;
 always #5 clk=~clk;
 reg rst_n=0,aresetn=0,dma_resetn=0,enable=0;
 reg raw_valid=0,raw_clip=0,raw_fault=0;reg [95:0] raw_pcm=0;
 wire pcm_valid,pcm_clip,pcm_fault;wire [95:0] pcm;wire [63:0] sample_index;
 ss_pcm_time_cdc crossing(.src_clk(src_clk),.src_rst_n(rst_n),.enable(enable),
 .raw_valid(raw_valid),.raw_clip(raw_clip),.raw_fault(raw_fault),.raw_pcm(raw_pcm),
 .clk(clk),.rst_n(rst_n),.sample_valid(pcm_valid),.sample_clip(pcm_clip),.sample_pcm(pcm),
 .sample_index(sample_index),.fault(pcm_fault));
 reg [6:0] address=0;reg commit=0,write_access=0;reg [31:0] write_data=0;
 wire [31:0] read_data,epoch,m_axis_tdata;wire active,m_axis_tvalid,m_axis_tlast;
 wire [3:0] m_axis_tkeep;reg m_axis_tready=0;
 wire run_enable;
 // Unit-test fixture supplies the new clk-domain control interface.
 xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(1),.INIT_SYNC_FF(1)) run_fixture(
 .src_clk(src_clk),.src_in(enable),.dest_clk(clk),.dest_out(run_enable));
 ss_audio_capture dut(.clk(clk),.rst_n(rst_n),.aresetn(aresetn),.dma_resetn(dma_resetn),
 .run_enable(run_enable),.compute_draining(1'b0),
 .pcm_valid(pcm_valid),.pcm_clip(pcm_clip),.pcm_fault(pcm_fault),.pcm(pcm),.sample_index(sample_index),
 .address(address),.commit(commit),.write_access(write_access),.format_error(1'b0),.write_data(write_data),
 .read_data(read_data),.epoch(epoch),.active(active),.*);
 function automatic [31:0] value(input integer n,input integer c);
  case(c)
   0:value=n==0 ? 32'hff800000 : n*4-5000;
   1:value=n==0 ? 32'h007fffff : 5000-n*4;
   2:value=32'hffffffff;
   3:value=n;
  endcase
 endfunction
 task automatic wr(input [6:0] a,input [31:0] v);
  @(negedge clk);address=a;write_data=v;write_access=1;commit=1;
  @(negedge clk);commit=0;write_access=0;
 endtask
 task automatic samples(input integer count,input bit use_clip);
  for(integer n=0;n<count;n=n+1)begin
   @(negedge src_clk);
   for(integer c=0;c<4;c=c+1)raw_pcm[c*24+:24]=24'(value(n,c));
   raw_clip=use_clip && n==513;raw_valid=1;
   @(negedge src_clk);raw_valid=0;raw_clip=0;
   repeat(39)@(negedge src_clk);
  end
 endtask
 integer beat=0,packets=0,expected_epoch=1,cycle=0;
 bit ready_mode=0,score=1,clip_expected=1;
 reg stalled=0;reg [36:0] held;
 reg [31:0] expected;
 always @(negedge clk)begin
  cycle=cycle+1;m_axis_tready=ready_mode && cycle%17>3;
 end
 always @(posedge clk)begin
  if(!rst_n || !aresetn || !dma_resetn)stalled<=0;
  else begin
   if(stalled && (!m_axis_tvalid || {m_axis_tlast,m_axis_tkeep,m_axis_tdata}!==held))
    $fatal(1,"AUDIO_FAIL AXIS changed under backpressure");
   stalled<=m_axis_tvalid && !m_axis_tready;
   held<={m_axis_tlast,m_axis_tkeep,m_axis_tdata};
   if(score && m_axis_tvalid && m_axis_tready)begin
    case(beat)
     0:expected=32'h43505353;
     1:expected=32'h00200001;
     2:expected=expected_epoch;
     3:expected=packets;
     4:expected=packets*512;
     5:expected=0;
     6:expected=(clip_expected && packets==1) ? 32'h00010200 : 32'h00000200;
     7:expected=8192;
     default:expected=value(packets*512+(beat-8)/4,(beat-8)%4);
    endcase
    if(m_axis_tdata!==expected || m_axis_tkeep!==4'hf || m_axis_tlast!==(beat==2055))
     $fatal(1,"AUDIO_FAIL packet=%0d beat=%0d actual=%h expected=%h last=%b",packets,beat,m_axis_tdata,expected,m_axis_tlast);
    if(beat==2055)begin beat=0;packets=packets+1;end else beat=beat+1;
   end
  end
 end
 // Independent window-start check: releases immediately; no FFT needed here.
 wire wvalid;wire wready=1'b1;wire [31:0] wframe;wire [63:0] wstart;
 integer windows=0;reg windows_check=1;reg wrelease=0;
 always @(posedge clk)wrelease<=wvalid;
 ss_pcm_windows #(.TIMING_ENABLE(1)) windows_dut(.clk(clk),.rst_n(rst_n),.enable(enable),
 .sample_valid(pcm_valid),.sample_pcm(pcm),.sample_clipped(1'b0),.sample_index(sample_index),
 .window_valid(wvalid),.window_ready(wready),.window_frame(wframe),.window_sample_start(wstart),
 .release_window(wrelease),.read_enable(1'b0),.read_index(10'b0),.read_valid(),.read_pcm(),
 .overflow(),.numeric_error(),.counter_exhausted());
 always @(posedge clk)if(wvalid && windows_check)begin
  if(wstart!==64'(windows*512))$fatal(1,"AUDIO_FAIL window sample association %d",wstart);
  windows=windows+1;
 end
 initial begin
  repeat(20)@(negedge clk);rst_n=1;aresetn=1;dma_resetn=1;
  repeat(30)@(negedge clk);
  wr('h08,1);wr('h04,1);repeat(30)@(negedge clk);
  if(!active)$fatal(1,"AUDIO_FAIL arm");
  ready_mode=1;enable=1;repeat(12)@(negedge src_clk);
  samples(1536,1);
  wait(packets==3);repeat(10)@(negedge clk);
  if(windows!=2)$fatal(1,"AUDIO_FAIL overlapping windows %0d",windows);
  enable=0;windows_check=0;repeat(40)@(negedge clk);
  if(active)$fatal(1,"AUDIO_FAIL stop");
  // A partial tail must not become a short or padded successful packet.
  packets=0;beat=0;expected_epoch=2;clip_expected=0;
  wr('h08,2);wr('h04,1);repeat(30)@(negedge clk);
  enable=1;repeat(12)@(negedge src_clk);samples(530,0);
  wait(packets==1);enable=0;repeat(80)@(negedge clk);
  if(packets!=1 || m_axis_tvalid)$fatal(1,"AUDIO_FAIL partial tail published");
  // Producer must fail-stop on full storage, not silently skip samples.
  packets=0;beat=0;expected_epoch=3;ready_mode=0;
  wr('h08,3);wr('h04,1);repeat(30)@(negedge clk);
  enable=1;repeat(12)@(negedge src_clk);samples(2500,0);
  if(active || !dut.errors[0] || dut.drop_count!=1)$fatal(1,"AUDIO_FAIL overflow not explicit");
  enable=0;ready_mode=1;wait(packets==4);repeat(50)@(negedge clk);
  // Same epoch is rejected, then a new epoch is accepted.
  wr('h04,1);repeat(8)@(negedge clk);
  if(active || !dut.errors[4])$fatal(1,"AUDIO_FAIL reused epoch accepted");
  packets=0;beat=0;expected_epoch=4;ready_mode=0;
  wr('h08,4);wr('h04,1);repeat(30)@(negedge clk);
  enable=1;repeat(12)@(negedge src_clk);samples(512,0);
  wait(m_axis_tvalid);repeat(5)@(negedge clk);
  dma_resetn=0;repeat(20)@(negedge clk);
  if(m_axis_tvalid || active || !dut.errors[5])$fatal(1,"AUDIO_FAIL DMA reset did not invalidate");
  enable=0;dma_resetn=1;repeat(40)@(negedge clk);
  packets=0;beat=0;expected_epoch=5;ready_mode=1;
  wr('h08,5);wr('h04,1);repeat(30)@(negedge clk);
  enable=1;repeat(12)@(negedge src_clk);samples(512,0);wait(packets==1);
  enable=0;repeat(50)@(negedge clk);
  $display("AUDIO_PASS: sign/channel/header/TLAST/stall/window/partial/overflow/epoch/DMA-reset");$finish;
 end
 initial begin #20000000;$fatal(1,"AUDIO_FAIL timeout");end
endmodule

