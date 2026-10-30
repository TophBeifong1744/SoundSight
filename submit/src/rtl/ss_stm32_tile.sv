// MIGRATION_MODULE_GUIDE
// 分组：01 总接合
// 用途：把精简计算链和 STM32 通信控制层组合成一个内部组件。
// 接口要点：clk=61.44 MHz；rst_n 为冷复位。PDM/SPI 为外部引脚；feature_* 在内部连接。BD 使用独立 compute/link 时不再添加本 tile。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// STM32版整层接合。compute只产生六对特征，link只负责传输/快照/动作保护。
// 默认ACTUATOR_BOUND=0，接口调试不会让实物舵机转动。
module ss_stm32_tile #(
 parameter integer WARMUP_SAMPLES=4096,ACTUATOR_BOUND=0,CLK_FREQ_HZ=61440000,
 parameter integer SERVO_MAX=180,MECHANICAL_MIN=0,MECHANICAL_MAX=180,
 parameter HANN_FILE="hann-u18f17.mem"
)(
 input wire clk,rst_n,input wire [3:0] pdm_data,output wire [3:0] pdm_clocks,
 input wire spi_cs_n,spi_sck,spi_mosi,output wire spi_miso,irq,servo_pwm,
 output wire [31:0] fault_status,output wire [3:0] debug_frontend,output wire [4:0] debug_backend
);
 wire feature_valid,feature_ready,enable,draining;
 wire [959:0] feature_pairs;
 wire [31:0] feature_flags;
 wire [11:0] source_faults;
 ss_clean_compute #(.WARMUP_SAMPLES(WARMUP_SAMPLES),.HANN_FILE(HANN_FILE)) compute(
   .clk(clk),.rst_n(rst_n),.enable(enable),.pdm_data(pdm_data),.pdm_clocks(pdm_clocks),
   .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_pairs(feature_pairs),.feature_flags(feature_flags),
   .draining(draining),.source_faults(source_faults),.debug_frontend(debug_frontend),.debug_backend(debug_backend));
 ss_stm32_link #(.ACTUATOR_BOUND(ACTUATOR_BOUND),.CLK_FREQ_HZ(CLK_FREQ_HZ),
   .SERVO_MAX(SERVO_MAX),.MECHANICAL_MIN(MECHANICAL_MIN),.MECHANICAL_MAX(MECHANICAL_MAX)) link(
   .clk(clk),.rst_n(rst_n),.spi_cs_n(spi_cs_n),.spi_sck(spi_sck),.spi_mosi(spi_mosi),
   .spi_miso(spi_miso),.irq(irq),.servo_pwm(servo_pwm),
   .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_pairs(feature_pairs),.feature_flags(feature_flags),
   .compute_draining(draining),.source_faults(source_faults),.run_enable(enable),.stop_pulse(),
   .fault_status(fault_status),.motion_permit(),.counter_exhausted());
endmodule
`default_nettype wire
