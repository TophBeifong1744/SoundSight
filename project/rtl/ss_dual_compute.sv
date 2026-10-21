// MIGRATION_MODULE_GUIDE
// 分组：双时钟总接合
// 用途：61.44MHz采集/公共控制与100MHz计算之间的明确边界。
// 公共feature_*、enable、draining、source_faults均属于io_clk域。
// STOP立即在公共控制域撤销运动；计算域收到同步后的enable再取消/排尾。
`timescale 1ns/1ps
`default_nettype none
module ss_dual_compute #(parameter integer WARMUP_SAMPLES=4096,LEVEL_ENABLE=0,parameter HANN_FILE="hann-u18f17.mem")(
 input wire clk,rst_n,io_clk,io_rst_n,enable,input wire [3:0] pdm_data,
 output wire [3:0] pdm_clocks,
 output wire feature_valid,input wire feature_ready,
 output wire [959:0] feature_pairs,output wire [31:0] feature_flags,
 output wire [31:0] feature_level,output wire feature_level_valid,
 output wire draining,output wire [11:0] source_faults,
 output wire [3:0] debug_frontend,output wire [4:0] debug_backend
);
 wire core_enable,core_active,core_valid,core_ready;
 wire [959:0] core_pairs;
 wire [31:0] core_flags;
 wire [31:0] core_level;wire core_level_valid;
 wire [11:0] core_faults;
 wire enable_return,busy_return;
 xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(0),.INIT_SYNC_FF(1)) enable_sync(
  .src_clk(io_clk),.src_in(enable && io_rst_n),.dest_clk(clk),.dest_out(core_enable));
 ss_clean_compute #(.WARMUP_SAMPLES(WARMUP_SAMPLES),.DUAL_CLOCK(1),.LEVEL_ENABLE(LEVEL_ENABLE),.HANN_FILE(HANN_FILE)) core(
  .clk(clk),.rst_n(rst_n),.enable(core_enable),.acq_clk(io_clk),.acq_rst_n(io_rst_n),.acq_enable(enable),
  .pdm_data(pdm_data),.pdm_clocks(pdm_clocks),
  .feature_valid(core_valid),.feature_ready(core_ready),.feature_pairs(core_pairs),.feature_flags(core_flags),
  .feature_level(core_level),.feature_level_valid(core_level_valid),
  .active(core_active),.draining(),.source_faults(core_faults),.debug_frontend(debug_frontend),.debug_backend(debug_backend));
 // 已发布帧即使遇到STOP也必须交到保存域。背压时整帧和标志保持稳定。
 generate if(LEVEL_ENABLE)begin: with_level
 ss_async_word #(.WIDTH(1025),.CAPACITY(1)) frames(
  .src_clk(clk),.src_rst_n(rst_n),.src_valid(core_valid),.src_ready(core_ready),.src_data({core_level_valid,core_level,core_flags,core_pairs}),
  .dst_clk(io_clk),.dst_rst_n(io_rst_n),.dst_valid(feature_valid),.dst_ready(feature_ready),.dst_data({feature_level_valid,feature_level,feature_flags,feature_pairs}));
 end else begin: legacy_frame
 assign feature_level=0;assign feature_level_valid=0;
 ss_async_word #(.WIDTH(992),.CAPACITY(1)) frames(
  .src_clk(clk),.src_rst_n(rst_n),.src_valid(core_valid),.src_ready(core_ready),.src_data({core_flags,core_pairs}),
  .dst_clk(io_clk),.dst_rst_n(io_rst_n),.dst_valid(feature_valid),.dst_ready(feature_ready),.dst_data({feature_flags,feature_pairs}));
 end endgenerate
 xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(0),.INIT_SYNC_FF(1)) enable_return_sync(
  .src_clk(clk),.src_in(core_enable),.dest_clk(io_clk),.dest_out(enable_return));
 xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(1),.INIT_SYNC_FF(1)) busy_sync(
  .src_clk(clk),.src_in(core_active || !core_ready),.dest_clk(io_clk),.dest_out(busy_return));
 // fault各位是独立的故障类别电平，允许逐位同步；不能用同一方法传递帧号或PCM。
 xpm_cdc_array_single #(.WIDTH(12),.DEST_SYNC_FF(2),.SRC_INPUT_REG(1),.INIT_SYNC_FF(1)) faults_sync(
  .src_clk(clk),.src_in(core_faults),.dest_clk(io_clk),.dest_out(source_faults));
 assign draining=!enable && (enable_return || busy_return || feature_valid);
endmodule
`default_nettype wire
