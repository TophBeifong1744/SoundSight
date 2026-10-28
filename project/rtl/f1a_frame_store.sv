// MIGRATION_MODULE_GUIDE
// 分组：06 六对特征
// 用途：六个工作槽加一个稳定输出槽；前一对不会被后一对覆盖。
// 接口要点：pair_event/index/160 位字组；frame_finish 后 feature_valid。背压保持整帧；满则丢新，不堵物理采集。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
// 中文用途：六个工作槽串行采入；独立保持一份完整输出，满时丢新帧而不阻塞采集。
// 这是 F1a 工作集和交接寄存器，不是 F2 的 FREE/READY/LOCKED 两槽队列。
module f1a_frame_store #(parameter integer LEVEL_ENABLE=0,META_ENABLE=0) (
    input wire clk, cold_rst_n,
    input wire [128:0] frame_meta,output reg [128:0] feature_meta,
    input wire frame_start, frame_start_bist,
    input wire pair_event, input wire [2:0] pair_index,
    input wire [159:0] pair_words,
    input wire frame_finish, frame_cancelled,
    input wire [31:0] frame_level, input wire frame_level_valid,
    output reg [31:0] feature_level, output reg feature_level_valid,
    input wire [7:0] first_error,
    input wire [23:0] phat_stages, ifft_stages,
    output wire accepting,
    output reg feature_valid, input wire feature_ready,
    output reg [31:0] feature_frame_id, feature_frame_flags,
    output reg [959:0] feature_pairs,
    output reg drop_pulse, output reg [31:0] drop_count,
    output reg gap, counter_exhausted,
    output reg source_protocol_error
);
    reg [959:0] work_pairs;reg [128:0] work_meta;
    reg [5:0] seen;
    reg [2:0] expected_pair;
    reg active, local_error, work_bist;
    reg [31:0] sequence_count;
    reg [959:0] sealed_pairs;
    reg [31:0] sealed_flags, missing_word;
    reg [3:0] ps, fs;
    integer i;
    assign accepting=!counter_exhausted;
    // 未运行对沿后端真实最终阶段补齐，避免把 PENDING 发布为 ALL_TERMINAL。
    always @* begin
        sealed_pairs=work_pairs;
        sealed_flags={first_error,24'b0} | 32'h10 | (work_bist ? 32'h8 : 0) |
                     (frame_cancelled ? 32'h00100000 : 0);
        if(local_error && first_error==0) sealed_flags[31:24]=8'd2; // 原 ERR_ORDER
        for(i=0;i<6;i=i+1) begin
            ps=phat_stages[i*4+:4]; fs=ifft_stages[i*4+:4];
            if(ps==0) ps=frame_cancelled ? 4'd5 : 4'd6;
            if(fs==0) fs=frame_cancelled ? 4'd5 : 4'd6;
            if(!seen[i]) begin
                missing_word={fs,ps,13'b0,3'(i),8'b0};
                missing_word[14]=frame_cancelled;
                missing_word[15]=(ps==3 || fs==3);
                sealed_pairs[i*160+:160]={128'b0,missing_word};
            end
        end
    end
    always @(posedge clk) begin
        if(!cold_rst_n) begin
            work_pairs<=0;seen<=0;expected_pair<=0;active<=0;local_error<=0;work_bist<=0;
            sequence_count<=0;feature_valid<=0;feature_frame_id<=0;work_meta<=0;feature_meta<=0;
            feature_frame_flags<=0;feature_pairs<=0;drop_pulse<=0;feature_level<=0;feature_level_valid<=0;
            drop_count<=0;gap<=0;counter_exhausted<=0;source_protocol_error<=0;
        end else begin
            drop_pulse<=0;
            if(feature_valid && feature_ready) feature_valid<=0;
            if(frame_start && accepting) begin
                work_meta<=META_ENABLE ? frame_meta : 129'b0;
                work_pairs<=0;seen<=0;expected_pair<=0;active<=1;local_error<=0;work_bist<=frame_start_bist;
                if(active) begin local_error<=1;source_protocol_error<=1;end
            end
            if(pair_event) begin
                if(!active || pair_index>5 || pair_index!=expected_pair || seen[pair_index]) begin
                    local_error<=1;source_protocol_error<=1;
                end else begin
                    work_pairs[pair_index*160+:160]<=pair_words;
                    seen[pair_index]<=1;expected_pair<=expected_pair+1;
                end
            end
            if(frame_finish && active) begin
                active<=0;
                if(!counter_exhausted) begin
                    sequence_count<=sequence_count+1;
                    if(sequence_count==32'hfffffffe) counter_exhausted<=1;
                    if(!feature_valid || feature_ready) begin
                        feature_valid<=1;feature_frame_id<=sequence_count+1;
                        feature_meta<=META_ENABLE ? {work_meta[128] && !frame_cancelled && first_error==0 && !local_error,work_meta[127:0]} : 129'b0;
                        feature_frame_flags<=sealed_flags;feature_pairs<=sealed_pairs;
                        // 与六对在同一发布分支锁存；满时保留旧音量，不被下一帧覆盖。
                        feature_level<=LEVEL_ENABLE ? frame_level : 0;
                        feature_level_valid<=LEVEL_ENABLE && frame_level_valid && !frame_cancelled && first_error==0 && !local_error;
                    end else begin
                        drop_pulse<=1;gap<=1;
                        if(drop_count!=32'hffffffff) drop_count<=drop_count+1;
                    end
                end
            end
        end
    end
endmodule
