// MIGRATION_MODULE_GUIDE
// 分组：BD 端口适配
// 用途：Vivado Module Reference 只接受 Verilog/VHDL 顶层；此层转接下方 SystemVerilog。
// 本模块不增加寄存器、延迟或控制状态。所有参数、位宽、握手和复位逐线原样传递。
// BD 里添加本模块；算法源码仍在 ss_stm32_link.sv，修改算法时不需重写这里。
`timescale 1ns/1ps
`default_nettype none
module bd_stm32_link #(
    parameter integer ACTUATOR_BOUND=0, CLK_FREQ_HZ=61440000,
    parameter integer SERVO_MAX=180, MECHANICAL_MIN=0, MECHANICAL_MAX=180
)(
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
 (* X_INTERFACE_PARAMETER="FREQ_HZ 61440000, ASSOCIATED_RESET rst_n" *)
 input wire clk,
    input wire rst_n,
    input wire spi_cs_n, spi_sck, spi_mosi,
    output wire spi_miso, irq, servo_pwm,
    input wire feature_valid,
    output wire feature_ready,
    input wire [959:0] feature_pairs,
    input wire [31:0] feature_flags,
    input wire compute_draining,
    input wire [11:0] source_faults,
    output wire run_enable,
    output wire stop_pulse,
    output wire [31:0] fault_status,
    output wire motion_permit,
    output wire counter_exhausted
);
 ss_stm32_link #(
    .ACTUATOR_BOUND(ACTUATOR_BOUND),
    .CLK_FREQ_HZ(CLK_FREQ_HZ),
    .SERVO_MAX(SERVO_MAX),
    .MECHANICAL_MIN(MECHANICAL_MIN),
    .MECHANICAL_MAX(MECHANICAL_MAX)
 ) u_core(
    .clk(clk),
    .rst_n(rst_n),
    .spi_cs_n(spi_cs_n),
    .spi_sck(spi_sck),
    .spi_mosi(spi_mosi),
    .spi_miso(spi_miso),
    .irq(irq),
    .servo_pwm(servo_pwm),
    .feature_valid(feature_valid),
    .feature_ready(feature_ready),
    .feature_pairs(feature_pairs),
    .feature_flags(feature_flags),
    .compute_draining(compute_draining),
    .source_faults(source_faults),
    .run_enable(run_enable),
    .stop_pulse(stop_pulse),
    .fault_status(fault_status),
    .motion_permit(motion_permit),
    .counter_exhausted(counter_exhausted)
 );
endmodule
`default_nettype wire
