`timescale 1ns/1ps
// Real shared compute/audio control and XPM crossings. Raw PCM is a fixture;
// core_active is forced only for the explicit drain/re-arm interlock test.
module tb_audioctrl;
 reg clk=0,io_clk=0;
 always #5 clk=~clk;
 initial begin #2.3;forever #8.138 io_clk=~io_clk;end
 reg rst_n=0,io_rst_n=0,aresetn=0,dma_resetn=0;
 reg request_run=0,host_stop=0;
 wire enable=request_run && !host_stop;
 wire audio_run,audio_draining,audio_valid,audio_clip,audio_source_fault,audio_active;
 wire [95:0] audio_pcm;wire [63:0] audio_sample_index;wire [31:0] epoch;
 wire draining;wire [11:0] source_faults;
 ss_dual_compute #(.WARMUP_SAMPLES(16),.LEVEL_ENABLE(1),.AUDIO_ENABLE(1)) compute(
  .clk(clk),.rst_n(rst_n),.io_clk(io_clk),.io_rst_n(io_rst_n),.enable(enable),.pdm_data(4'b0),.pdm_clocks(),
  .audio_epoch(epoch),.audio_active(audio_active),.audio_run(audio_run),.audio_draining(audio_draining),
  .audio_valid(audio_valid),.audio_clip(audio_clip),.audio_source_fault(audio_source_fault),
  .audio_pcm(audio_pcm),.audio_sample_index(audio_sample_index),.feature_meta(),
  .feature_valid(),.feature_ready(1'b1),.feature_pairs(),.feature_flags(),.feature_level(),.feature_level_valid(),
  .draining(draining),.source_faults(source_faults),.debug_frontend(),.debug_backend());
 reg [6:0] address=0;reg commit=0,write_access=0;reg [31:0] write_data=0;
 wire [31:0] read_data,tdata;wire [3:0] tkeep;wire tvalid,tlast;
 ss_audio_capture audio(.clk(clk),.rst_n(rst_n),.aresetn(aresetn),.dma_resetn(dma_resetn),
  .run_enable(audio_run),.compute_draining(audio_draining),.pcm_valid(audio_valid),.pcm_clip(audio_clip),
  .pcm_fault(audio_source_fault),.pcm(audio_pcm),.sample_index(audio_sample_index),
  .address(address),.commit(commit),.write_access(write_access),.format_error(1'b0),.write_data(write_data),
  .read_data(read_data),.epoch(epoch),.active(audio_active),.m_axis_tdata(tdata),.m_axis_tkeep(tkeep),
  .m_axis_tvalid(tvalid),.m_axis_tready(1'b1),.m_axis_tlast(tlast));
 reg fixture_valid=0;reg [95:0] fixture_pcm=0;
 integer packets=0,beat=0,expected_epoch=1,checks=0,cycles=0;
 reg glitch_test=0,drain_glitch_test=0;
 always @(posedge clk)begin
  cycles=cycles+1;
  if(cycles>150000)$fatal(1,"AUDIOCTRL_FAIL timeout");
  if(glitch_test && audio_run)$fatal(1,"AUDIOCTRL_FAIL source glitch crossed");
  if(drain_glitch_test && audio_draining)$fatal(1,"AUDIOCTRL_FAIL drain glitch crossed");
  if(audio_run!==compute.core_enable)$fatal(1,"AUDIOCTRL_FAIL duplicated run state");
  if(tvalid)begin
   if(tkeep!=15 || tlast!==(beat==2055))$fatal(1,"AUDIOCTRL_FAIL framing");
   case(beat)
    0:if(tdata!=32'h43505353)$fatal(1,"AUDIOCTRL_FAIL magic");
    2:if(tdata!=expected_epoch)$fatal(1,"AUDIOCTRL_FAIL old epoch");
    3,4,5:if(tdata!=0)$fatal(1,"AUDIOCTRL_FAIL initial sequence/index");
    default:if(beat>=8 && tdata!=32'((beat-8)/4+1))$fatal(1,"AUDIOCTRL_FAIL first sample/order");
   endcase
   if(tlast)begin packets=packets+1;beat=0;end else beat=beat+1;
  end
 end
 task wr(input [6:0] a,input [31:0] v);
  @(negedge clk);address=a;write_data=v;write_access=1;commit=1;
  @(negedge clk);commit=0;write_access=0;
 endtask
 task settle;
  repeat(24)@(negedge io_clk);
 endtask
 task arm(input integer e);
  expected_epoch=e;wr('h08,e);wr('h04,1);repeat(20)@(negedge clk);
  if(!audio_active || audio.errors!=0)$fatal(1,"AUDIOCTRL_FAIL arm epoch %0d",e);
 endtask
 task stop_source;
  @(negedge io_clk);request_run=0;
  settle();
  if(audio_run || audio_draining || draining)$fatal(1,"AUDIOCTRL_FAIL stop propagation");
 endtask
 task one_packet;
  @(negedge io_clk);request_run=1;
  settle();
  if(!audio_run)$fatal(1,"AUDIOCTRL_FAIL run propagation");
  for(integer i=0;i<512;i=i+1)begin
   @(negedge io_clk);fixture_pcm={4{24'(i+1)}};fixture_valid=1;
   @(negedge io_clk);fixture_valid=0;repeat(18)@(negedge io_clk);
  end
  wait(tlast && tvalid);@(negedge clk);stop_source();
  if(audio.armed)$fatal(1,"AUDIOCTRL_FAIL automatic stop");checks=checks+1;
 endtask
 initial begin
  force compute.core.raw_valid=fixture_valid;force compute.core.raw_pcm=fixture_pcm;
  force compute.core.raw_clip=0;force compute.core.raw_channel_fault=0;
  settle();rst_n=1;io_rst_n=1;aresetn=1;dma_resetn=1;settle();
  // Pulses lie between source edges; sweep their overlap with destination edges.
  glitch_test=1;
  for(integer i=0;i<20;i=i+1)begin
   @(negedge io_clk);#1 request_run=1;#3 request_run=0;settle();checks=checks+1;
  end
  glitch_test=0;
  // With a real enable return present, a brief combinational STOP also makes
  // draining pulse. It must be sampled at the source edge before crossing.
  @(negedge io_clk);request_run=1;settle();drain_glitch_test=1;
  for(integer i=0;i<20;i=i+1)begin
   @(negedge io_clk);#1 request_run=0;#3 request_run=1;settle();checks=checks+1;
  end
  drain_glitch_test=0;stop_source();
  arm(1);one_packet();
  // Very short completed runs at many phases must terminate without stale state.
  for(integer i=0;i<8;i=i+1)begin
   arm(10+i);@(negedge io_clk);request_run=1;
   wait(audio_run);repeat(i+1)@(negedge clk);stop_source();
   if(audio.armed)$fatal(1,"AUDIOCTRL_FAIL fast stop");checks=checks+1;
  end
  arm(30);@(negedge io_clk);request_run=1;settle();
  force compute.core_active=1'b1;settle();
  @(negedge io_clk);request_run=0;settle();
  if(!audio_draining || !draining)$fatal(1,"AUDIOCTRL_FAIL lost drain");
  wr('h08,31);wr('h04,1);
  if(!audio.errors[4] || audio.armed)$fatal(1,"AUDIOCTRL_FAIL rearmed before drain");
  release compute.core_active;settle();
  if(audio_draining)$fatal(1,"AUDIOCTRL_FAIL drain stuck");checks=checks+1;
  arm(31);one_packet();
  // Bus reset requests source STOP, but does not reset the source window counter.
  arm(40);@(negedge io_clk);request_run=1;settle();
  @(negedge io_clk);host_stop=1;@(negedge clk);aresetn=0;settle();
  if(audio_run || audio.armed)$fatal(1,"AUDIOCTRL_FAIL bus reset run");
  request_run=0;host_stop=0;aresetn=1;settle();arm(41);one_packet();checks=checks+1;
  arm(50);@(negedge io_clk);request_run=1;settle();
  @(negedge clk);dma_resetn=0;repeat(8)@(negedge clk);
  if(audio.armed || !audio.errors[5])$fatal(1,"AUDIOCTRL_FAIL DMA reset");
  dma_resetn=1;stop_source();arm(51);one_packet();checks=checks+1;
  arm(60);@(negedge io_clk);request_run=1;settle();
  #1.7 io_rst_n=0;request_run=0;#2.1 rst_n=0;settle();
  rst_n=1;#3 io_rst_n=1;settle();
  if(audio_run || audio_draining || audio.armed)$fatal(1,"AUDIOCTRL_FAIL cold reset reactivation");
  arm(61);one_packet();checks=checks+1;
  if(packets!=5 || source_faults!=0)$fatal(1,"AUDIOCTRL_FAIL packets/faults %0d %h",packets,source_faults);
  $display("AUDIOCTRL_PASS checks=%0d packets=%0d shared_run=1 source_glitches=40 resets=bus_dma_cold",checks,packets);$finish;
 end
endmodule
