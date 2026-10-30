// MIGRATION_MODULE_GUIDE
// 分组：PS实验版
// 用途：AXI4-Lite总线转换，AW/W分开保存，B/R背压保持。
// 接口要点：clk、aresetn与五个AXI通道；address/commit/write_access/write_data/read_data为寄存器内接口。无效对齐/范围/字节写返回SLVERR。
// 主方案仍由STM32独占控制，本模块只在独立PS版本使用。
`timescale 1ns/1ps
`default_nettype none
// 片内AXI4-Lite到单次寄存器操作。每个方向最多一个在途事务。
// AW和W各自保存，先后顺序任意；B/R在对端背压时保持不变。
// 仅接收0x000..0x07f中的4字节对齐、全字写入；其他事务SLVERR且不触发寄存器副作用。
module ss_axi_lite_regs #(parameter integer ADDRESS_BITS=7) (
 input wire clk, aresetn,
 input wire [11:0] s_axi_awaddr,input wire [2:0] s_axi_awprot,
 input wire s_axi_awvalid,output wire s_axi_awready,
 input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,
 input wire s_axi_wvalid,output wire s_axi_wready,
 output reg [1:0] s_axi_bresp,output reg s_axi_bvalid,input wire s_axi_bready,
 input wire [11:0] s_axi_araddr,input wire [2:0] s_axi_arprot,
 input wire s_axi_arvalid,output wire s_axi_arready,
 output reg [31:0] s_axi_rdata,output reg [1:0] s_axi_rresp,
 output reg s_axi_rvalid,input wire s_axi_rready,
 output wire [ADDRESS_BITS-1:0] address,output wire commit,write_access,format_error,
 output wire [31:0] write_data,input wire [31:0] read_data
);
 reg aw_full,w_full,ar_full,cooldown;
 reg [11:0] aw,ar;
 reg [31:0] wd;
 reg [3:0] ws;
 assign s_axi_awready=aresetn && !aw_full && !s_axi_bvalid;
 assign s_axi_wready=aresetn && !w_full && !s_axi_bvalid;
 assign s_axi_arready=aresetn && !ar_full && !s_axi_rvalid;
 wire execute_write=aresetn && aw_full && w_full && !s_axi_bvalid && !cooldown;
 wire execute_read=aresetn && ar_full && !s_axi_rvalid && !execute_write && !cooldown;
 wire write_ok=(aw >> ADDRESS_BITS)==0 && aw[1:0]==0 && ws==4'hf;
 wire read_ok=(ar >> ADDRESS_BITS)==0 && ar[1:0]==0;
 assign address=execute_write?aw[ADDRESS_BITS-1:0]:ar[ADDRESS_BITS-1:0];
 assign write_data=wd;
 assign write_access=execute_write;
 assign commit=(execute_write && write_ok) || (execute_read && read_ok);
 assign format_error=(execute_write && !write_ok) || (execute_read && !read_ok);
 always @(posedge clk)begin
   if(!aresetn)begin
     aw_full<=0;w_full<=0;ar_full<=0;cooldown<=0;aw<=0;ar<=0;wd<=0;ws<=0;
     s_axi_bvalid<=0;s_axi_bresp<=0;s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;
   end else begin
     cooldown<=0;
     if(s_axi_awvalid && s_axi_awready)begin aw<=s_axi_awaddr;aw_full<=1;end
     if(s_axi_wvalid && s_axi_wready)begin wd<=s_axi_wdata;ws<=s_axi_wstrb;w_full<=1;end
     if(s_axi_arvalid && s_axi_arready)begin ar<=s_axi_araddr;ar_full<=1;end
     if(s_axi_bvalid && s_axi_bready)s_axi_bvalid<=0;
     if(s_axi_rvalid && s_axi_rready)s_axi_rvalid<=0;
     if(execute_write)begin
       aw_full<=0;w_full<=0;s_axi_bvalid<=1;s_axi_bresp<=write_ok?2'b00:2'b10;cooldown<=1;
     end
     if(execute_read)begin
       ar_full<=0;s_axi_rvalid<=1;s_axi_rresp<=read_ok?2'b00:2'b10;
       s_axi_rdata<=read_ok?read_data:32'hdeadbeef;cooldown<=1;
     end
     // 一拍间隔让SNAP_CMD等寄存器产生的内部脉冲先落地，再处理下一次访问。
   end
 end
 // PROT不提供安全域隔离；本实验要求单一PS软件所有者，不可多进程同时控制。
endmodule
`default_nettype wire
