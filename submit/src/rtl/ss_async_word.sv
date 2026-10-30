// MIGRATION_MODULE_GUIDE
// 分组：跨时钟传输
// 用途：用官方 XPM 异步 FIFO 完整传递一组数据，禁止逐位同步多位数据。
// 接口：src_valid/ready 在写时钟域；dst_valid/ready 在读时钟域。
// 两端复位必须来自同一个冷复位原因，各自同步释放；普通 STOP 不复位 FIFO。
`timescale 1ns/1ps
`default_nettype none
module ss_async_word #(parameter integer WIDTH=97, CAPACITY=16)(
 input wire src_clk,src_rst_n,src_valid,output wire src_ready,
 input wire [WIDTH-1:0] src_data,
 input wire dst_clk,dst_rst_n,output wire dst_valid,input wire dst_ready,
 output wire [WIDTH-1:0] dst_data
);
 wire full,empty,wr_busy,rd_busy;
 wire [4:0] count;
 // XPM 的物理最小深度为16；CAPACITY=1时仅允许一个在途字，
 // 用于整帧交接，避免把通信快照的双槽偷偷扩成更多槽。
 assign src_ready=src_rst_n && !wr_busy && !full && count<CAPACITY;
 assign dst_valid=dst_rst_n && !rd_busy && !empty;
 xpm_fifo_async #(
  .FIFO_MEMORY_TYPE("distributed"),.FIFO_WRITE_DEPTH(16),
  .WRITE_DATA_WIDTH(WIDTH),.READ_DATA_WIDTH(WIDTH),
  .READ_MODE("fwft"),.FIFO_READ_LATENCY(0),.CDC_SYNC_STAGES(2),
  .WR_DATA_COUNT_WIDTH(5),.RD_DATA_COUNT_WIDTH(5),
  .PROG_FULL_THRESH(10),.PROG_EMPTY_THRESH(5),
  .DOUT_RESET_VALUE("0"),.FULL_RESET_VALUE(0),.ECC_MODE("no_ecc"),
  .USE_ADV_FEATURES("0404"),.SIM_ASSERT_CHK(1),.RELATED_CLOCKS(0),.WAKEUP_TIME(0)
 ) fifo (
  .rst(!src_rst_n),.wr_clk(src_clk),.rd_clk(dst_clk),
  .din(src_data),.wr_en(src_valid && src_ready),
  .rd_en(dst_valid && dst_ready),.dout(dst_data),
  .full(full),.empty(empty),.wr_rst_busy(wr_busy),.rd_rst_busy(rd_busy),
  .wr_data_count(count),.rd_data_count(),.almost_full(),.almost_empty(),
  .prog_full(),.prog_empty(),.overflow(),.underflow(),.wr_ack(),.data_valid(),
  .sleep(1'b0),.injectsbiterr(1'b0),.injectdbiterr(1'b0),.sbiterr(),.dbiterr()
 );
 initial begin
  if(CAPACITY<1 || CAPACITY>16)$fatal(1,"ss_async_word CAPACITY must be 1..16");
 end
endmodule
`default_nettype wire
