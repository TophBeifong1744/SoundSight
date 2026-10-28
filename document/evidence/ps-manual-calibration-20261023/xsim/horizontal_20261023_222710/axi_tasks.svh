// 主机模型独立安排AW、W；响应通道有意施加背压。
reg [11:0] s_axi_awaddr=0,s_axi_araddr=0;
reg [2:0] s_axi_awprot=0,s_axi_arprot=0;
reg s_axi_awvalid=0,s_axi_wvalid=0,s_axi_bready=0,s_axi_arvalid=0,s_axi_rready=0;
reg [31:0] s_axi_wdata=0;
reg [3:0] s_axi_wstrb=15;
wire s_axi_awready,s_axi_wready,s_axi_bvalid,s_axi_arready,s_axi_rvalid;
wire [1:0] s_axi_bresp,s_axi_rresp;
wire [31:0] s_axi_rdata;
integer checks=0;
task tick;@(negedge clk);endtask
task check(input bit okay,input string why);checks=checks+1;if(!okay)$fatal(1,"AXI_FAIL %s",why);endtask
task wr(input reg[11:0] a,input reg[31:0] d,input integer ad,input integer dd,input reg[3:0] st,input reg[1:0] expected);
 reg [1:0] held;
 fork
   begin repeat(ad)tick();s_axi_awaddr=a;s_axi_awvalid=1;
     do @(posedge clk);while(!s_axi_awready);tick();s_axi_awvalid=0;end
   begin repeat(dd)tick();s_axi_wdata=d;s_axi_wstrb=st;s_axi_wvalid=1;
     do @(posedge clk);while(!s_axi_wready);tick();s_axi_wvalid=0;end
 join
 while(!s_axi_bvalid)tick();held=s_axi_bresp;
 repeat(5)begin tick();check(s_axi_bvalid && s_axi_bresp==held,"B response unstable");end
 check(held==expected,"B response code");s_axi_bready=1;tick();s_axi_bready=0;repeat(2)tick();
endtask
task rd(input reg[11:0] a,output reg[31:0] d,input reg[1:0] expected);
 reg [1:0] held;
 tick();s_axi_araddr=a;s_axi_arvalid=1;
 do @(posedge clk);while(!s_axi_arready);tick();s_axi_arvalid=0;
 while(!s_axi_rvalid)tick();d=s_axi_rdata;held=s_axi_rresp;
 repeat(7)begin tick();check(s_axi_rvalid && s_axi_rdata===d && s_axi_rresp==held,"R response unstable");end
 check(held==expected,"R response code");s_axi_rready=1;tick();s_axi_rready=0;repeat(2)tick();
endtask
task put(input reg[11:0] a,input reg[31:0] d);wr(a,d,2,0,15,0);endtask
task expect_read(input reg[11:0] a,input reg[31:0] e);
 reg [31:0] d;rd(a,d,0);check(d===e,$sformatf("read %03x got=%08x expected=%08x",a,d,e));
endtask
