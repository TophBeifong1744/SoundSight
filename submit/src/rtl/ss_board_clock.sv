// MIGRATION_MODULE_GUIDE
// 分组：01 总接合
// 用途：50 MHz转换为61.44 MHz，并在锁定后同步释放冷复位。
// 接口要点：sys_clk/cold_reset_n 输入，clk/rst_n 输出。BD默认冷复位请求接常量1，依配置/失锁复位；未臆造外部按钮管脚。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 板级时钟：复用既有 50 -> 96 -> 61.44 MHz 原语配置。
// 外部冷复位或失锁立即拉低，解除后等三个处理时钟才同步释放。
module ss_board_clock (
    input wire sys_clk, cold_reset_n,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER="FREQ_HZ 61440000,ASSOCIATED_RESET rst_n" *) output wire clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 rst_n RST" *)
    (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) output wire rst_n
);
    wire clock_reset_n;
    sound_servo_clock clocks(.sys_clk(sys_clk),.clk50(),.clk_pcm(clk),.rst50_n(),.rst_pcm_n(clock_reset_n));
    wire async_ok=clock_reset_n && cold_reset_n;
    (* ASYNC_REG="TRUE" *) reg [2:0] release_sync;
    always @(posedge clk or negedge async_ok)
        if(!async_ok) release_sync<=0;else release_sync<={release_sync[1:0],1'b1};
    assign rst_n=release_sync[2];
endmodule
`default_nettype wire
