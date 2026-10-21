// MIGRATION_MODULE_GUIDE
// 分组：BD 端口适配
// 用途：Vivado Module Reference 只接受 Verilog/VHDL 顶层；此层转接下方 SystemVerilog。
// 本模块不增加寄存器、延迟或控制状态。所有参数、位宽、握手和复位逐线原样传递。
// BD 里添加本模块；算法源码仍在 ss_ps_link.sv，修改算法时不需重写这里。
`timescale 1ns/1ps
`default_nettype none
module bd_ps_link #(
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
 (* X_INTERFACE_INFO="xilinx.com:signal:interrupt:1.0 irq INTERRUPT" *)
 (* X_INTERFACE_PARAMETER="SENSITIVITY LEVEL_HIGH" *) output wire irq,
 output wire servo_pwm,output wire [31:0] fault_status
);
 ss_ps_link #(
    .ACTUATOR_BOUND(ACTUATOR_BOUND),.LEVEL_ENABLE(LEVEL_ENABLE),
    .CLK_FREQ_HZ(CLK_FREQ_HZ),
    .SERVO_MAX(SERVO_MAX),
    .MECHANICAL_MIN(MECHANICAL_MIN),
    .MECHANICAL_MAX(MECHANICAL_MAX)
 ) u_core(
    .clk(clk),
    .rst_n(rst_n),
    .aresetn(aresetn),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_awprot(s_axi_awprot),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp),
    .s_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_arprot(s_axi_arprot),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata),
    .s_axi_rresp(s_axi_rresp),
    .s_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .feature_valid(feature_valid),
    .feature_ready(feature_ready),
    .feature_pairs(feature_pairs),
    .feature_flags(feature_flags),
    .feature_level(feature_level),.feature_level_valid(feature_level_valid),
    .compute_draining(compute_draining),
    .source_faults(source_faults),
    .run_enable(run_enable),
    .irq(irq),
    .servo_pwm(servo_pwm),
    .fault_status(fault_status)
 );
endmodule
`default_nettype wire
