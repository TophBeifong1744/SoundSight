// MIGRATION_MODULE_GUIDE
// 分组：07 SPI 与快照
// 用途：同步过采样 Mode0 事务；仅在 CS 释放且恰好 40 位时提交副作用。
// 接口要点：异步 CS/SCK/MOSI；内部 address/read_data/write_data/commit。MISO 空闲驱动 0，当前用于独占点对点总线。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// Mode0 从机：异步针脚仅进入同步器，内部全部使用 61.44 MHz。
// 读值在头字节结束时冻结；写入/读错误仅在合法 40 位事务释放 CS 后提交。
module ss_spi_mode0 (
    input wire clk, rst_n,
    input wire cs_n, sck, mosi,
    output reg miso,
    output reg [6:0] address,
    input wire [31:0] read_data,
    output reg commit, write_access,
    output reg [31:0] write_data,
    output reg format_error
);
    (* ASYNC_REG="TRUE" *) reg [2:0] cs_sync, ck_sync, di_sync;
    reg cs_q, ck_q;
    reg active, malformed, read_pending;
    reg [5:0] bits_seen;
    reg [7:0] header;
    reg [31:0] rx, tx;
    reg [3:0] edge_age, idle_age;
    wire rise=ck_sync[2] && !ck_q;
    wire fall=!ck_sync[2] && ck_q;
    wire select_fall=!cs_sync[2] && cs_q;
    wire select_rise=cs_sync[2] && !cs_q;
    always @(posedge clk) begin
        if(!rst_n) begin
            cs_sync<=7;ck_sync<=0;di_sync<=0;cs_q<=1;ck_q<=0;
            active<=0;malformed<=0;read_pending<=0;bits_seen<=0;
            header<=0;rx<=0;tx<=0;address<=0;write_access<=0;
            write_data<=0;commit<=0;format_error<=0;miso<=0;
            edge_age<=15;idle_age<=15;
        end else begin
            cs_sync<={cs_sync[1:0],cs_n};ck_sync<={ck_sync[1:0],sck};
            di_sync<={di_sync[1:0],mosi};cs_q<=cs_sync[2];ck_q<=ck_sync[2];
            commit<=0;format_error<=0;
            if(edge_age!=15) edge_age<=edge_age+1'b1;
            if(cs_sync[2] && idle_age!=15) idle_age<=idle_age+1'b1;
            if(read_pending) begin tx<=read_data;read_pending<=0;end
            if(select_fall) begin
                active<=1;bits_seen<=0;header<=0;rx<=0;tx<=0;miso<=0;
                malformed<=ck_sync[2] || (idle_age<7);edge_age<=0;idle_age<=0;
            end else if(select_rise) begin
                if(active) begin
                    if(bits_seen==40 && !malformed && !ck_sync[2] && !rise && edge_age>=7) begin
                        commit<=1;write_data<=rx;
                    end else format_error<=1;
                end
                active<=0;miso<=0;read_pending<=0;idle_age<=0;
            end else if(active && !cs_sync[2]) begin
                if(rise || fall) begin
                    edge_age<=0;
                    if(edge_age<7) malformed<=1;
                end
                if(rise) begin
                    if(bits_seen<41) bits_seen<=bits_seen+1'b1;
                    if(bits_seen>=40) malformed<=1;
                    if(bits_seen<8) begin
                        header<={header[6:0],di_sync[2]};
                        if(bits_seen==7) begin
                            write_access<=header[6];address<={header[5:0],di_sync[2]};
                            read_pending<=1;
                        end
                    end else rx<={rx[30:0],di_sync[2]};
                end
                if(fall && bits_seen>=8 && bits_seen<40) begin
                    miso<=tx[31];tx<={tx[30:0],1'b0};
                end
            end
        end
    end
endmodule
`default_nettype wire
