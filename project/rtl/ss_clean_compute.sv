// MIGRATION_MODULE_GUIDE
// 分组：02 计算总接合
// 用途：协调采样、窗口、预处理、FFT 和六对引擎；普通停用先排空再回到空闲。
// 接口要点：enable 只控制新工作；输出 valid/ready、960 位六对数据、32 位帧状态及 12 位故障。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 精简计算总接合：采集→窗口→预处理/FFT→六对特征。
// 内部只有一帧在计算，跨模块携带真实window_frame，不再复制725位身份和数千位诊断包。
module ss_clean_compute #(parameter integer WARMUP_SAMPLES=4096,DUAL_CLOCK=0,parameter HANN_FILE="hann-u18f17.mem")(
 input wire clk,rst_n,enable,input wire [3:0] pdm_data,
 // DUAL_CLOCK=1: 采集61.44MHz，计算100MHz；0保留单域算法复现入口。
 input wire acq_clk,acq_rst_n,acq_enable,
 output wire [3:0] pdm_clocks,
 output wire feature_valid,input wire feature_ready,
 output wire [959:0] feature_pairs,output wire [31:0] feature_flags,
 output wire draining,active,output wire [11:0] source_faults,
 output wire [3:0] debug_frontend,output wire [4:0] debug_backend
);
 wire sample_valid,sample_clipped,warm,channel_fault;
 wire [95:0] sample_pcm;
 wire capture_clk=DUAL_CLOCK ? acq_clk:clk;
 wire capture_rst_n=DUAL_CLOCK ? acq_rst_n:rst_n;
 wire raw_valid,raw_clip,raw_channel_fault;
 wire [95:0] raw_pcm;
 ss_pdm_capture #(.WARMUP_SAMPLES(WARMUP_SAMPLES)) acquisition(
   .clk(capture_clk),.rst_n(capture_rst_n),.pdm_data(pdm_data),.pdm_clocks(pdm_clocks),
   .sample_valid(raw_valid),.pcm(raw_pcm),.sample_clipped(raw_clip),.warm(warm),.channel_fault(raw_channel_fault));
 generate if(DUAL_CLOCK)begin: sample_crossing
   wire ready;
   reg acquisition_error=0;
   // 四路PCM和削顶标记一起写入。读端持续排空；STOP只停止窗口/新任务。
   ss_async_word #(.WIDTH(97),.CAPACITY(16)) samples(
    .src_clk(acq_clk),.src_rst_n(acq_rst_n),.src_valid(raw_valid && acq_enable),.src_ready(ready),.src_data({raw_clip,raw_pcm}),
    .dst_clk(clk),.dst_rst_n(rst_n),.dst_valid(sample_valid),.dst_ready(1'b1),.dst_data({sample_clipped,sample_pcm}));
   always @(posedge acq_clk)begin
    if(!acq_rst_n || !acq_enable)acquisition_error<=0;
    else if(raw_channel_fault || (raw_valid && !ready))acquisition_error<=1;
   end
   xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(0),.INIT_SYNC_FF(1)) error_sync(
    .src_clk(acq_clk),.src_in(acquisition_error),.dest_clk(clk),.dest_out(channel_fault));
 end else begin: single_clock
   assign sample_valid=raw_valid;
   assign sample_pcm=raw_pcm;
   assign sample_clipped=raw_clip;
   assign channel_fault=raw_channel_fault;
 end endgenerate
 wire window_valid,window_ready,release_window,read_enable,read_valid;
 wire [31:0] window_frame;
 wire [9:0] read_index;
 wire [95:0] read_pcm;
 wire overflow,numeric_error,window_exhausted;
 reg [11:0] faults;
 wire front_busy,backend_busy,backend_obligation;
 wire frame_drop,frame_gap,feature_exhausted,feature_protocol;
 wire [31:0] local_sequence,local_drop_count;
 wire capture_enable=enable && !(|faults) && !feature_exhausted;
 ss_pcm_windows windows(
   .clk(clk),.rst_n(rst_n),.enable(capture_enable),.sample_valid(sample_valid),.sample_pcm(sample_pcm),
   .sample_clipped(sample_clipped),.window_valid(window_valid),.window_ready(window_ready),.window_frame(window_frame),
   .release_window(release_window),.read_enable(read_enable),.read_index(read_index),.read_valid(read_valid),.read_pcm(read_pcm),
   .overflow(overflow),.numeric_error(numeric_error),.counter_exhausted(window_exhausted));
 wire begin_valid,begin_ready,s_valid,s_ready,s_numeric_valid,end_valid,end_ready,end_cancelled;
 wire [31:0] begin_frame,s_frame,end_frame;
 wire [1:0] s_channel;
 wire [9:0] s_bin;
 wire signed [24:0] s_real,s_imag;
 wire [7:0] end_error;
 ss_fft_frontend #(.HANN_FILE(HANN_FILE)) frontend(
   .clk(clk),.rst_n(rst_n),.enable(enable),.source_bad(|faults),
   .window_valid(window_valid),.window_ready(window_ready),.window_frame(window_frame),
   .release_window(release_window),.read_enable(read_enable),.read_index(read_index),.read_valid(read_valid),.read_pcm(read_pcm),
   .begin_valid(begin_valid),.begin_ready(begin_ready),.begin_frame(begin_frame),
   .s_valid(s_valid),.s_ready(s_ready),.s_frame(s_frame),.s_channel(s_channel),.s_bin(s_bin),
   .s_real(s_real),.s_imag(s_imag),.s_numeric_valid(s_numeric_valid),
   .end_valid(end_valid),.end_ready(end_ready),.end_frame(end_frame),.end_cancelled(end_cancelled),.end_error(end_error),
   .backend_busy(backend_busy),.busy(front_busy),.debug_state(debug_frontend),
   .audit_valid(),.audit_domain(),.audit_channel(),.audit_bin(),.audit_real(),.audit_imag());
 ss_pair_engine backend(
   .clk(clk),.rst_n(rst_n),.begin_valid(begin_valid),.begin_ready(begin_ready),.begin_frame(begin_frame),
   .s_valid(s_valid),.s_ready(s_ready),.s_frame(s_frame),.s_channel(s_channel),.s_bin(s_bin),
   .s_real(s_real),.s_imag(s_imag),.s_numeric_valid(s_numeric_valid),
   .end_valid(end_valid),.end_ready(end_ready),.end_frame(end_frame),.end_cancelled(end_cancelled),.end_error(end_error),
   .cancel(!enable),.busy(backend_busy),.ip_obligation(backend_obligation),
   .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_frame_id(local_sequence),
   .feature_frame_flags(feature_flags),.feature_pairs(feature_pairs),.feature_drop_pulse(frame_drop),
   .feature_drop_count(local_drop_count),.feature_gap(frame_gap),.feature_counter_exhausted(feature_exhausted),
   .feature_source_protocol_error(feature_protocol),.debug_state(debug_backend));
 assign draining=!enable && (front_busy || backend_busy || backend_obligation);
 assign active=front_busy || backend_busy || backend_obligation;
 assign source_faults=faults;
 always @(posedge clk)begin
   if(!rst_n)faults<=0;
   else begin
     if(!enable && !front_busy && !backend_busy)faults<=0;
     // 首错显示由已封存frame_flags承担，实时故障仅汇总类别，不附伪造证明包。
     if(channel_fault || overflow || frame_drop || feature_protocol)faults[4]<=1;
     if(numeric_error)faults[5]<=1;
     if(window_exhausted || feature_exhausted)faults[9]<=1;
     if(end_valid && end_ready && end_error!=0)begin
       if(end_error==3)faults[5]<=1;else faults[4]<=1;
     end
   end
 end
endmodule
`default_nettype wire
