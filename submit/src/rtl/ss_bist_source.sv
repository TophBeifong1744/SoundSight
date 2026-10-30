// MIGRATION_MODULE_GUIDE
// 分组：07 SPI 与快照
// 用途：产生冻结的拒绝/0 度通过两组特征，只验证传输和软件求解。
// 接口要点：trigger/select_pass→valid/六对特征。BIST 不能给出实物运动资格。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 冻结 ABI 的两个诊断帧。仅生成原始特征，不代替真实 FFT/IFFT 数值验证。
module ss_bist_source (
    input wire clk, rst_n, trigger, select_pass,
    output reg valid,
    output reg [959:0] pairs
);
    integer i;
    reg signed [7:0] lag;
    reg [31:0] word0;
    always @(posedge clk) begin
        if(!rst_n) begin valid<=0;pairs<=0;end
        else begin
            valid<=trigger;
            if(trigger) for(i=0;i<6;i=i+1) begin
                if(select_pass) case(i)
                    0,1: lag=4;
                    2,3: lag=0;
                    default: lag=-4;
                endcase
                else case(i)
                    0:lag=5;1:lag=-3;2:lag=0;3:lag=1;4:lag=-1;default:lag=2;
                endcase
                word0=32'h664f1800 | (32'(i)<<8) | {24'b0,lag};
                pairs[i*160+:160]<={32'd100,(select_pass?32'd800:32'd600),32'd800,32'd1000,word0};
            end
        end
    end
endmodule
`default_nettype wire
