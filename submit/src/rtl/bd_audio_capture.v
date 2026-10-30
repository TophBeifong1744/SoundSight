`timescale 1ns/1ps
`default_nettype none
// BD adapter only. All audio logic is in ss_audio_capture.
module bd_audio_capture (
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
 (* X_INTERFACE_PARAMETER="FREQ_HZ 100000000,ASSOCIATED_BUSIF S_AXI:M_AXIS,ASSOCIATED_RESET aresetn" *) input wire clk,
 input wire rst_n,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST" *)
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR" *) (* X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE,DATA_WIDTH 32,ADDR_WIDTH 12,READ_WRITE_MODE READ_WRITE,NUM_READ_OUTSTANDING 1,NUM_WRITE_OUTSTANDING 1" *) input wire [11:0] s_axi_awaddr,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input wire [2:0] s_axi_awprot,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input wire s_axi_awvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input wire [31:0] s_axi_wdata,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input wire [3:0] s_axi_wstrb,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input wire s_axi_wvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output wire [1:0] s_axi_bresp,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output wire s_axi_bvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input wire s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input wire [11:0] s_axi_araddr,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input wire [2:0] s_axi_arprot,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input wire s_axi_arvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output wire [31:0] s_axi_rdata,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output wire [1:0] s_axi_rresp,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output wire s_axi_rvalid,(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire s_axi_rready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TDATA" *) output wire [31:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *) output wire [3:0] m_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TLAST" *) output wire m_axis_tlast,
 input wire dma_resetn,run_enable,compute_draining,
 input wire pcm_valid,pcm_clip,pcm_fault,input wire [95:0] pcm,
 input wire [63:0] sample_index,
 output wire [31:0] epoch,output wire active
);
 wire [6:0] address;
 wire commit,write_access,format_error;
 wire [31:0] write_data,read_data;
 ss_axi_lite_regs bus(
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
 .clk(clk),.aresetn(aresetn),.address(address),.commit(commit),.write_access(write_access),
 .format_error(format_error),.write_data(write_data),.read_data(read_data));
 ss_audio_capture core(
 .clk(clk),
 .rst_n(rst_n),
 .aresetn(aresetn),
 .dma_resetn(dma_resetn),
 .run_enable(run_enable),
 .compute_draining(compute_draining),
 .pcm_valid(pcm_valid),
 .pcm_clip(pcm_clip),
 .pcm_fault(pcm_fault),
 .pcm(pcm),
 .sample_index(sample_index),
 .address(address),
 .commit(commit),
 .write_access(write_access),
 .format_error(format_error),
 .write_data(write_data),
 .read_data(read_data),
 .epoch(epoch),
 .active(active),
 .m_axis_tdata(m_axis_tdata),
 .m_axis_tkeep(m_axis_tkeep),
 .m_axis_tvalid(m_axis_tvalid),
 .m_axis_tready(m_axis_tready),
 .m_axis_tlast(m_axis_tlast));
endmodule
`default_nettype wire
