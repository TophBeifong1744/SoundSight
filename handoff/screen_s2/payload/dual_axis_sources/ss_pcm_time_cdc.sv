`timescale 1ns/1ps
`default_nettype none
// One PCM crossing, with a time token before each group of 512 samples.
// The 64-bit source counter advances on physical samples, never on FIFO ready.
// A lost token/sample is fail-stop until acquisition is disabled and drained.
module ss_pcm_time_cdc (
 input wire src_clk,src_rst_n,enable,raw_valid,raw_clip,raw_fault,
 input wire [95:0] raw_pcm,
 input wire clk,rst_n,
 output wire sample_valid,output wire [95:0] sample_pcm,
 output wire sample_clip,output wire [63:0] sample_index,
 output wire fault
);
 reg [63:0] count;
 reg failed,pending;
 reg [96:0] held;
 wire ready,valid;
 wire [97:0] data;
 wire token=raw_valid && count[8:0]==0;
 wire send=enable && !failed && (pending || raw_valid);
 wire [97:0] word_in=pending ? {1'b0,held} :
                         token ? {1'b1,33'b0,count} : {1'b0,raw_clip,raw_pcm};
 ss_async_word #(.WIDTH(98),.CAPACITY(16)) crossing(
  .src_clk(src_clk),.src_rst_n(src_rst_n),.src_valid(send),.src_ready(ready),.src_data(word_in),
  .dst_clk(clk),.dst_rst_n(rst_n),.dst_valid(valid),.dst_ready(1'b1),.dst_data(data));
 always @(posedge src_clk) begin
  if(!src_rst_n)begin count<=0;failed<=0;pending<=0;held<=0;end
  else if(!enable)begin count<=0;failed<=0;pending<=0;end
  else begin
   if(raw_valid) begin
    if(&count)failed<=1;else count<=count+1'b1;
   end
   if(raw_fault || (send && !ready) || (pending && raw_valid))begin failed<=1;pending<=0;end
   else if(pending)pending<=0;
   else if(token && !failed)begin held<={raw_clip,raw_pcm};pending<=1;end
  end
 end
 reg [63:0] base;
 reg [8:0] offset;
 reg have_time;
 always @(posedge clk)begin
  if(!rst_n)begin base<=0;offset<=0;have_time<=0;end
  else if(valid)begin
   if(data[97])begin base<=data[63:0];offset<=0;have_time<=1;end
   else begin offset<=offset+1'b1;if(&offset)have_time<=0;end
  end
 end
 assign sample_valid=valid && !data[97] && have_time;
 assign sample_pcm=data[95:0];assign sample_clip=data[96];
 // Token base is a multiple of 512; concatenation avoids a 64-bit per-sample adder.
 assign sample_index={base[63:9],offset};
 xpm_cdc_single #(.DEST_SYNC_FF(2),.SRC_INPUT_REG(0),.INIT_SYNC_FF(1)) fault_sync(
  .src_clk(src_clk),.src_in(failed),.dest_clk(clk),.dest_out(fault));
endmodule
`default_nettype wire
