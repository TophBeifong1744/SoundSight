`timescale 1ns/1ps
// 接口集成用例：真实AXI握手 + 完整寄存器/双槽/BIST；特征来自显式夹具。
module tb_pscdc;
 reg clk=0;always #5 clk=~clk;
 reg io_clk=0;initial begin #2.3;forever #8.138 io_clk=~io_clk;end
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0;
 reg [31:0] feature_flags=32'h10;
 reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm;
 wire [31:0] fault_status;
 `include "axi_tasks.svh"
 wire [11 : 0] m_axi_awaddr;
 wire [2 : 0] m_axi_awprot;
 wire  m_axi_awvalid;
 wire  m_axi_awready;
 wire [31 : 0] m_axi_wdata;
 wire [3 : 0] m_axi_wstrb;
 wire  m_axi_wvalid;
 wire  m_axi_wready;
 wire [1 : 0] m_axi_bresp;
 wire  m_axi_bvalid;
 wire  m_axi_bready;
 wire [11 : 0] m_axi_araddr;
 wire [2 : 0] m_axi_arprot;
 wire  m_axi_arvalid;
 wire  m_axi_arready;
 wire [31 : 0] m_axi_rdata;
 wire [1 : 0] m_axi_rresp;
 wire  m_axi_rvalid;
 wire  m_axi_rready;
 soundsight_ps_bd_control_cdc_0 crossing(
  .s_axi_aclk(clk),
  .s_axi_aresetn(aresetn),
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
  .m_axi_aclk(io_clk),
  .m_axi_aresetn(aresetn),
  .m_axi_awaddr(m_axi_awaddr),
  .m_axi_awprot(m_axi_awprot),
  .m_axi_awvalid(m_axi_awvalid),
  .m_axi_awready(m_axi_awready),
  .m_axi_wdata(m_axi_wdata),
  .m_axi_wstrb(m_axi_wstrb),
  .m_axi_wvalid(m_axi_wvalid),
  .m_axi_wready(m_axi_wready),
  .m_axi_bresp(m_axi_bresp),
  .m_axi_bvalid(m_axi_bvalid),
  .m_axi_bready(m_axi_bready),
  .m_axi_araddr(m_axi_araddr),
  .m_axi_arprot(m_axi_arprot),
  .m_axi_arvalid(m_axi_arvalid),
  .m_axi_arready(m_axi_arready),
  .m_axi_rdata(m_axi_rdata),
  .m_axi_rresp(m_axi_rresp),
  .m_axi_rvalid(m_axi_rvalid),
  .m_axi_rready(m_axi_rready)
 );
 ss_ps_link dut(.clk(io_clk),.s_axi_awaddr(m_axi_awaddr),.s_axi_awprot(m_axi_awprot),.s_axi_awvalid(m_axi_awvalid),.s_axi_awready(m_axi_awready),.s_axi_wdata(m_axi_wdata),.s_axi_wstrb(m_axi_wstrb),.s_axi_wvalid(m_axi_wvalid),.s_axi_wready(m_axi_wready),.s_axi_bresp(m_axi_bresp),.s_axi_bvalid(m_axi_bvalid),.s_axi_bready(m_axi_bready),.s_axi_araddr(m_axi_araddr),.s_axi_arprot(m_axi_arprot),.s_axi_arvalid(m_axi_arvalid),.s_axi_arready(m_axi_arready),.s_axi_rdata(m_axi_rdata),.s_axi_rresp(m_axi_rresp),.s_axi_rvalid(m_axi_rvalid),.s_axi_rready(m_axi_rready),.*);
 reg [31:0] value,status,seq;
 integer fd,which;
 task publish(input integer peak);
   @(negedge io_clk);for(integer p=0;p<6;p=p+1)feature_pairs[p*160+:160]={32'd100,32'd800,32'd800,32'(peak),32'h114f3800|(32'(p)<<8)};
   feature_valid=1;@(negedge io_clk);feature_valid=0;repeat(4)@(negedge io_clk);
 endtask
 initial begin
   repeat(64)tick();rst_n=1;aresetn=1;repeat(64)tick();
   expect_read(0,32'h5a5a2026);expect_read('h6c,32'h10000);expect_read(4,8);
   for(which=0;which<2;which=which+1)begin
     put('h2c,which);put(4,11);put('h38,1);rd('h34,status,0);rd(8,seq,0);
     check((status&32'hff1f7fff)==32'h17f39 && seq==which+1,"BIST status/sequence");
     fd=$fopen(which?"ps_bist_pass.txt":"ps_bist_reject.txt","w");$fdisplay(fd,"%08x %08x",seq,status);
     for(integer p=0;p<6;p=p+1)begin
       put('h1c,p);
       rd('hc,value,0);check(value[10:8]==p && value[31:24]==8'h66,"pair echo/stages");$fwrite(fd,"%08x ",value);
       rd('h10,value,0);$fwrite(fd,"%08x ",value);rd('h20,value,0);$fwrite(fd,"%08x ",value);
       rd('h24,value,0);$fwrite(fd,"%08x ",value);rd('h28,value,0);$fdisplay(fd,"%08x",value);
     end
     $fclose(fd);put('h38,4);put(4,10);put('h64,'hfff);check(!servo_pwm,"BIST motion");
   end
   put(4,8);put(4,9);check(run_enable,"real start");publish(1000);put('h38,1);expect_read(8,3);
   put('h1c,0);expect_read('h10,1000);publish(2000);
   // 总线复位不是冷复位：控制立即停用，两个已保存槽都保留。
   tick();aresetn=0;repeat(64)tick();check(!run_enable && !servo_pwm,"host reset stops new work");
   aresetn=1;repeat(32)tick();expect_read(4,8);expect_read(8,3);expect_read('h10,1000);
   check(fault_status[6],"host stop recorded");put('h38,4);put('h38,1);expect_read(8,4);expect_read('h10,2000);
   put('h38,4);put('h64,'hfff);check(!irq,"consumed then clear");
   // 无效总线写不能改变角度影子；上层格式错误可见。
   wr('h18,32'h4005a,0,3,3,2);expect_read('h18,0);check(fault_status[0],"AXI format error");
   put('h64,'hfff);put(4,9);publish(3000);tick();rst_n=0;aresetn=0;repeat(64)tick();rst_n=1;aresetn=1;
   repeat(64)tick();expect_read(8,0);check(!irq && !servo_pwm,"cold reset clears snapshots");
   $display("PSCDC_PASS checks=%0d master_hz=100000000 endpoint_hz=61440000 official_clock_converter=1 dual_bist=1 host_reset_preserves_two_slots=1",checks);$finish;
 end
 initial begin #5000000;$fatal(1,"PSCDC_FAIL timeout");end
endmodule
