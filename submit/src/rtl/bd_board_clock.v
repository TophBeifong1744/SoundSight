// MIGRATION_MODULE_GUIDE
// 分组：BD 端口适配
// 用途：Vivado Module Reference 只接受 Verilog/VHDL 顶层；此层转接下方 SystemVerilog。
// 本模块不增加寄存器、延迟或控制状态。所有参数、位宽、握手和复位逐线原样传递。
// BD 里添加本模块；算法源码仍在 ss_board_clock.sv，修改算法时不需重写这里。
`timescale 1ns/1ps
`default_nettype none
module bd_board_clock (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 sys_clk CLK" *)
    (* X_INTERFACE_PARAMETER="FREQ_HZ 50000000" *) input wire sys_clk,
    input wire cold_reset_n,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER="FREQ_HZ 61440000,ASSOCIATED_RESET rst_n" *) output wire clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 rst_n RST" *)
    (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) output wire rst_n
);
 ss_board_clock u_core(
    .sys_clk(sys_clk),
    .cold_reset_n(cold_reset_n),
    .clk(clk),
    .rst_n(rst_n)
 );
endmodule
`default_nettype wire
