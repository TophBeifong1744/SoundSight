`timescale 1ns/1ps
`default_nettype none
// Fixed v1 format: 32-byte header, 512 x 4 x S32 payload, 8224 bytes total.
// FIFO overflow is fail-stop. Completed packets drain; an incomplete tail is
// never published. A fresh epoch and idle acquisition are required to re-arm.
module ss_audio_capture (
 input wire clk,rst_n,aresetn,dma_resetn,
 // Already synchronized by ss_dual_compute; all inputs here belong to clk.
 input wire run_enable,compute_draining,
 input wire pcm_valid,pcm_clip,pcm_fault,input wire [95:0] pcm,
 input wire [63:0] sample_index,
 input wire [6:0] address,input wire commit,write_access,format_error,
 input wire [31:0] write_data,output reg [31:0] read_data,
 output wire [31:0] epoch,output wire active,
 output reg [31:0] m_axis_tdata,output wire [3:0] m_axis_tkeep,
 output wire m_axis_tvalid,input wire m_axis_tready,output wire m_axis_tlast
);
 wire run=run_enable;
 reg [31:0] configured_epoch,last_epoch,session_epoch,sequence_count,drop_count;
 reg armed,seen_run,clipped;
 reg [3:0] flush_count;wire flush=|flush_count;
 reg [7:0] errors;
 reg [8:0] fill;
 reg [63:0] block_start,progress;
 reg [1:0] state;
 reg [2:0] header_word;
 reg [10:0] payload_word;
 localparam IDLE=0,HEADER=1,PAYLOAD=2;
 wire reset_fifo=!rst_n || !aresetn || !dma_resetn || flush;
 wire data_full,data_empty,desc_full,desc_empty;
 wire [95:0] data_out;
 // Descriptor: sequence, first sample, flags (clip only for valid packets).
 wire [111:0] desc_out;
 wire stop_request=commit && write_access && address==7'h04 && write_data==2;
 wire sample=armed && errors==0 && run && pcm_valid && !pcm_fault && dma_resetn && !stop_request;
 wire wrong_start=fill==0 && sample_index!={23'b0,sequence_count,9'b0};
 wire rejected=sample && (data_full || (fill==511 && desc_full) || wrong_start || &sequence_count);
 wire push=sample && !rejected;
 wire desc_push=push && fill==511;
 wire handshake=m_axis_tvalid && m_axis_tready;
 wire last_payload=state==PAYLOAD && payload_word==2047;
 wire desc_pop=handshake && last_payload;
 ss_audio_fifo data_fifo(.clk(clk),.reset(reset_fifo),.push(push),
 .pop(handshake && state==PAYLOAD && payload_word[1:0]==3),.din(pcm),
 .dout(data_out),.full(data_full),.empty(data_empty));
 ss_audio_fifo #(.WIDTH(112),.DEPTH(16),.MEMORY("distributed")) descriptors(
 .clk(clk),.reset(reset_fifo),.push(desc_push),.pop(desc_pop),
 .din({sequence_count,block_start,15'b0,clipped || pcm_clip}),
 .dout(desc_out),.full(desc_full),.empty(desc_empty));
 assign epoch=session_epoch;
 assign active=armed && errors==0 && !reset_fifo && !data_full && !desc_full;
 assign m_axis_tkeep=4'hf;
 assign m_axis_tvalid=!reset_fifo && ((state==HEADER && !desc_empty) ||
                                            (state==PAYLOAD && !data_empty));
 assign m_axis_tlast=last_payload && m_axis_tvalid;
 wire signed [23:0] channel=data_out[payload_word[1:0]*24+:24];
 always @*begin
  m_axis_tdata=0;
  if(state==PAYLOAD)m_axis_tdata={{8{channel[23]}},channel};
  else case(header_word)
   0:m_axis_tdata=32'h43505353; // bytes "SSPC"
   1:m_axis_tdata=32'h00200001; // header bytes, format version
   2:m_axis_tdata=session_epoch;
   3:m_axis_tdata=desc_out[111:80];
   4:m_axis_tdata=desc_out[47:16];
   5:m_axis_tdata=desc_out[79:48];
   6:m_axis_tdata={desc_out[15:0],16'd512};
   7:m_axis_tdata=32'd8192;
  endcase
 end
 always @(posedge clk)begin
  if(reset_fifo)begin state<=IDLE;header_word<=0;payload_word<=0;end
  else case(state)
   IDLE:if(!desc_empty)begin state<=HEADER;header_word<=0;end
   HEADER:if(handshake)begin
    if(header_word==7)begin state<=PAYLOAD;payload_word<=0;end
    else header_word<=header_word+1'b1;
   end
   PAYLOAD:if(handshake)begin
    if(last_payload)state<=IDLE;else payload_word<=payload_word+1'b1;
   end
   default:state<=IDLE;
  endcase
 end
 wire idle=!armed && !run && !compute_draining && state==IDLE && desc_empty;
 reg known;
 always @*begin
  known=1;read_data=0;
  case(address)
   'h00:read_data=32'h00010001; // version 1, raw four-channel capability
   'h04:read_data={30'b0,seen_run,armed};
   'h08:read_data=configured_epoch;
   'h0c:read_data={16'b0,errors,2'b0,active,dma_resetn,idle,fill!=0,state!=IDLE || !desc_empty,armed};
   'h10:read_data=48000;
   'h14:read_data=32'h04201801; // channels=4, container=32, valid=24, interleaved LE
   'h18:read_data=512;
   'h1c:read_data=8224;
   'h20:read_data=drop_count;
   'h24:read_data=sequence_count;
   'h28:read_data=progress[31:0]; // stable only after explicit snapshot command
   'h2c:read_data=progress[63:32];
   'h30:read_data=session_epoch;
   default:known=0;
  endcase
 end
 always @(posedge clk)begin
  if(!rst_n || !aresetn)begin
   configured_epoch<=0;last_epoch<=0;session_epoch<=0;sequence_count<=0;drop_count<=0;
   armed<=0;seen_run<=0;clipped<=0;flush_count<=8;errors<=0;fill<=0;block_start<=0;progress<=0;
  end else begin
   if(flush_count!=0)flush_count<=flush_count-1'b1;
   if(errors!=0)armed<=0;
   if(armed && run)seen_run<=1;
   if(armed && seen_run && !run)armed<=0;
   if(commit && write_access)begin
    if(address=='h08 && idle)configured_epoch<=write_data;
    else if(address=='h04 && write_data==1 && idle && dma_resetn &&
            configured_epoch!=0 && configured_epoch!=last_epoch)begin
     armed<=1;seen_run<=0;session_epoch<=configured_epoch;last_epoch<=configured_epoch;
     sequence_count<=0;fill<=0;clipped<=0;errors<=0;drop_count<=0;progress<=0;flush_count<=8;
    end else if(address=='h04 && write_data==2)armed<=0;
    else if(address=='h04 && write_data==4)progress<=sample_index;
    else errors[4]<=1;
   end
   if(commit && !write_access && !known)errors[4]<=1;
   if(format_error)errors[4]<=1;
   if(push)begin
    if(fill==0)begin block_start<=sample_index;clipped<=pcm_clip;end
    else clipped<=clipped || pcm_clip;
    fill<=fill+1'b1;
    if(fill==511)begin sequence_count<=sequence_count+1'b1;clipped<=0;end
   end
   if(rejected)begin
    armed<=0;errors[0]<=data_full || desc_full;errors[1]<=wrong_start;errors[2]<=&sequence_count;
    if(drop_count!=32'hffffffff)drop_count<=drop_count+1'b1;
   end
   if(armed && pcm_fault)begin armed<=0;errors[3]<=1;end
   if(!dma_resetn)begin
    if(armed || state!=IDLE || !desc_empty)errors[5]<=1;
    armed<=0;fill<=0;
   end
  end
 end
endmodule
`default_nettype wire
