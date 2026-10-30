// MIGRATION_MODULE_GUIDE
// 分组：07 SPI 与快照
// 用途：两槽 FREE/READY/LOCKED；锁最老完整帧；满时丢新，已锁内容不动。
// 接口要点：整帧输入；ACQUIRE/RELEASE/CONSUME；锁帧内容、序号、gap/drop/错误。与新帧同拍消费优先释放槽。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 两槽各存整帧；序号在发布尝试时分配，满时只丢新帧。读者只看 LOCKED。
// 同拍先消费，再写新帧，因此恰好释放的槽可以立即使用，不制造假溢出。
module ss_snapshot_queue #(parameter integer META_ENABLE=0) (
    input wire clk, rst_n,
    input wire frame_valid,
    input wire [128:0] frame_meta,output wire [128:0] locked_meta,
    input wire [959:0] frame_pairs,
    input wire [31:0] frame_flags, frame_energy,
    input wire frame_energy_valid,
    input wire [2:0] command,
    output wire locked, queued, occupied,
    output wire [959:0] locked_pairs,
    output wire [31:0] locked_flags, locked_energy, locked_sequence,
    output wire locked_energy_valid,
    output reg gap, exhausted,
    output reg [31:0] drop_count,
    output reg snapshot_error, overflow_pulse, counter_error
);
    localparam [1:0] FREE=0, READY=1, LOCKED=2;
    reg [1:0] state[0:1], next_state[0:1];
    reg [959:0] pairs[0:1];reg [128:0] meta[0:1];
    reg [31:0] flags[0:1], energy[0:1], seq[0:1];
    reg energy_valid[0:1];
    reg [31:0] sequence_count;
    integer wr_slot, choose;
    reg bad_command;
    wire lock_index=(state[1]==LOCKED);
    assign locked=(state[0]==LOCKED || state[1]==LOCKED);
    assign queued=(state[0]==READY || state[1]==READY);
    assign occupied=locked || queued;
    assign locked_meta=locked && META_ENABLE ? meta[lock_index] : 129'b0;
    assign locked_pairs=locked ? pairs[lock_index] : 960'b0;
    assign locked_flags=locked ? flags[lock_index] : 32'b0;
    assign locked_energy=locked ? energy[lock_index] : 32'b0;
    assign locked_energy_valid=locked && energy_valid[lock_index];
    assign locked_sequence=locked ? seq[lock_index] : 32'b0;
    always @* begin
        next_state[0]=state[0];next_state[1]=state[1];bad_command=0;choose=-1;
        case(command)
            0: ;
            1: if(!locked) begin
                if(state[0]==READY && state[1]==READY) choose=seq[0]<seq[1] ? 0 : 1;
                else if(state[0]==READY) choose=0;
                else if(state[1]==READY) choose=1;
                if(choose>=0) next_state[choose]=LOCKED;
            end
            2: if(locked) next_state[lock_index]=READY; else bad_command=1;
            4: if(locked) next_state[lock_index]=FREE; else bad_command=1;
            default: bad_command=1;
        endcase
        wr_slot=-1;
        if(frame_valid && !exhausted) begin
            if(next_state[0]==FREE) wr_slot=0;
            else if(next_state[1]==FREE) wr_slot=1;
            if(wr_slot>=0) next_state[wr_slot]=READY;
        end
    end
    integer i;
    always @(posedge clk) begin
        if(!rst_n) begin
            for(i=0;i<2;i=i+1) begin
                state[i]<=FREE;pairs[i]<=0;meta[i]<=0;flags[i]<=0;energy[i]<=0;seq[i]<=0;energy_valid[i]<=0;
            end
            sequence_count<=0;drop_count<=0;gap<=0;exhausted<=0;
            snapshot_error<=0;overflow_pulse<=0;counter_error<=0;
        end else begin
            for(i=0;i<2;i=i+1) state[i]<=next_state[i];
            snapshot_error<=bad_command;overflow_pulse<=0;counter_error<=0;
            if(frame_valid) begin
                if(exhausted) counter_error<=1;
                else begin
                    sequence_count<=sequence_count+1'b1;
                    if(sequence_count==32'hfffffffe) begin exhausted<=1;counter_error<=1;end
                    if(wr_slot>=0) begin
                        pairs[wr_slot]<=frame_pairs;flags[wr_slot]<=frame_flags;
                        meta[wr_slot]<=META_ENABLE ? frame_meta : 129'b0;
                        energy[wr_slot]<=frame_energy;energy_valid[wr_slot]<=frame_energy_valid;
                        seq[wr_slot]<=sequence_count+1'b1;
                    end else begin
                        gap<=1;overflow_pulse<=1;
                        if(drop_count!=32'hffffffff) drop_count<=drop_count+1'b1;
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
