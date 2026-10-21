// MIGRATION_MODULE_GUIDE
// 分组：PS实验版
// 用途：片内CPU控制入口，组合AXI转换和PS寄存器层。
// 接口要点：S_AXI为32位AXI4-Lite、12位局部地址；clk61.44MHz。rst_n为PL冷复位，aresetn为PS总线复位。
// 主方案仍由STM32独占控制，本模块只在独立PS版本使用。
`timescale 1ns/1ps
`default_nettype none
// 无STM32实验版的唯一CPU入口。总线复位只停用/撤许可，冷复位才清快照。
module ss_ps_link #(
 parameter integer ACTUATOR_BOUND=0,LEVEL_ENABLE=0,CLK_FREQ_HZ=61440000,
 parameter integer SERVO_MAX=180,MECHANICAL_MIN=0,MECHANICAL_MAX=180
)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
 (* X_INTERFACE_PARAMETER="FREQ_HZ 61440000,ASSOCIATED_BUSIF S_AXI,ASSOCIATED_RESET aresetn" *) input wire clk,
 input wire rst_n,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST" *)
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR" *) (* X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE,DATA_WIDTH 32,ADDR_WIDTH 12,READ_WRITE_MODE READ_WRITE,NUM_READ_OUTSTANDING 1,NUM_WRITE_OUTSTANDING 1" *) input wire [11:0] s_axi_awaddr,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input wire [2:0] s_axi_awprot,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input wire s_axi_awvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input wire [31:0] s_axi_wdata,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input wire [3:0] s_axi_wstrb,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input wire s_axi_wvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output wire [1:0] s_axi_bresp,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output wire s_axi_bvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input wire s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input wire [11:0] s_axi_araddr,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input wire [2:0] s_axi_arprot,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input wire s_axi_arvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output wire [31:0] s_axi_rdata,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output wire [1:0] s_axi_rresp,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output wire s_axi_rvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire s_axi_rready,
 input wire feature_valid,output wire feature_ready,input wire [959:0] feature_pairs,input wire [31:0] feature_flags,
 input wire [31:0] feature_level,input wire feature_level_valid,
 input wire compute_draining,input wire [11:0] source_faults,output wire run_enable,
 output wire irq,servo_pwm,output wire [31:0] fault_status
);
 wire [6:0] address;
 wire commit,write_access,format_error;
 wire [31:0] write_data,read_data;
 ss_axi_lite_regs bus(.*);
 ss_ps_control_regs #(.ACTUATOR_BOUND(ACTUATOR_BOUND),.LEVEL_ENABLE(LEVEL_ENABLE),.CLK_FREQ_HZ(CLK_FREQ_HZ),
   .SERVO_MAX(SERVO_MAX),.MECHANICAL_MIN(MECHANICAL_MIN),.MECHANICAL_MAX(MECHANICAL_MAX)) regs(
   .clk(clk),.rst_n(rst_n),.host_stop(!aresetn),.address(address),.commit(commit),.write_access(write_access),
   .format_error(format_error),.write_data(write_data),.read_data(read_data),.irq(irq),.servo_pwm(servo_pwm),
   .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_pairs(feature_pairs),.feature_flags(feature_flags),
    .feature_level(feature_level),.feature_level_valid(feature_level_valid),
   .compute_draining(compute_draining),.source_faults(source_faults),.run_enable(run_enable),.stop_pulse(),
   .fault_status(fault_status),.motion_permit(),.counter_exhausted());
endmodule
`default_nettype wire
