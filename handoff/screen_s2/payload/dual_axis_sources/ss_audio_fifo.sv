`timescale 1ns/1ps
`default_nettype none
// Synchronous bounded storage. This is not another PCM clock crossing.
module ss_audio_fifo #(parameter integer WIDTH=96,DEPTH=2048,parameter MEMORY="block")(
 input wire clk,reset,push,pop,input wire [WIDTH-1:0] din,
 output wire [WIDTH-1:0] dout,output wire full,empty
);
 wire f,e,wb,rb;
 assign full=f || wb;assign empty=e || rb;
 xpm_fifo_sync #(.FIFO_MEMORY_TYPE(MEMORY),.FIFO_WRITE_DEPTH(DEPTH),
 .WRITE_DATA_WIDTH(WIDTH),.READ_DATA_WIDTH(WIDTH),.READ_MODE("fwft"),.FIFO_READ_LATENCY(0),
 .WR_DATA_COUNT_WIDTH($clog2(DEPTH)+1),.RD_DATA_COUNT_WIDTH($clog2(DEPTH)+1),
 .PROG_FULL_THRESH(10),.PROG_EMPTY_THRESH(5),.DOUT_RESET_VALUE("0"),.FULL_RESET_VALUE(0),
 .ECC_MODE("no_ecc"),.USE_ADV_FEATURES("0000"),.SIM_ASSERT_CHK(1),.WAKEUP_TIME(0)) fifo(
 .rst(reset),.wr_clk(clk),.din(din),.wr_en(push && !full),.rd_en(pop && !empty),.dout(dout),
 .full(f),.empty(e),.wr_rst_busy(wb),.rd_rst_busy(rb),.wr_data_count(),.rd_data_count(),
 .almost_full(),.almost_empty(),.prog_full(),.prog_empty(),.overflow(),.underflow(),
 .wr_ack(),.data_valid(),.sleep(1'b0),.injectsbiterr(1'b0),.injectdbiterr(1'b0),.sbiterr(),.dbiterr());
endmodule
`default_nettype wire
