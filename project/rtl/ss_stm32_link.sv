// MIGRATION_MODULE_GUIDE
// 分组：06 寄存器与快照
// 用途：仅把SPI传输层和独立寄存器层接起来，避免重复一套控制逻辑。
// 接口要点：SPI Mode0、1 MHz、每片选40位；STM32独占快照与动作；MISO空闲主动输出0，只用于独占点对点连接。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// STM32用SPI入口；公共寄存器和保护逻辑统一由ss_control_regs实现。
module ss_stm32_link #(
    parameter integer ACTUATOR_BOUND=0, CLK_FREQ_HZ=61440000,
    parameter integer SERVO_MAX=180, MECHANICAL_MIN=0, MECHANICAL_MAX=180
)(
    input wire clk, rst_n,
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
    wire [6:0] address;
    wire commit,write_access,format_error;
    wire [31:0] write_data,read_data;
    ss_spi_mode0 spi(.clk(clk),.rst_n(rst_n),.cs_n(spi_cs_n),.sck(spi_sck),.mosi(spi_mosi),
      .miso(spi_miso),.address(address),.read_data(read_data),.commit(commit),
      .write_access(write_access),.write_data(write_data),.format_error(format_error));
    ss_control_regs #(.ACTUATOR_BOUND(ACTUATOR_BOUND),.CLK_FREQ_HZ(CLK_FREQ_HZ),
      .SERVO_MAX(SERVO_MAX),.MECHANICAL_MIN(MECHANICAL_MIN),.MECHANICAL_MAX(MECHANICAL_MAX)) registers (
      .clk(clk),.rst_n(rst_n),.address(address),.commit(commit),.write_access(write_access),
      .format_error(format_error),.write_data(write_data),.read_data(read_data),
      .irq(irq),.servo_pwm(servo_pwm),.feature_valid(feature_valid),.feature_ready(feature_ready),
      .feature_pairs(feature_pairs),.feature_flags(feature_flags),.compute_draining(compute_draining),
      .source_faults(source_faults),.run_enable(run_enable),.stop_pulse(stop_pulse),
      .fault_status(fault_status),.motion_permit(motion_permit),.counter_exhausted(counter_exhausted));
endmodule
`default_nettype wire
