`timescale 1ns/1ps
// 接口集成用例：真实AXI握手 + 完整寄存器/双槽/BIST；特征来自显式夹具。
module tb_ps;
 reg clk=0;always #8.138 clk=~clk;
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0;
 reg [31:0] feature_flags=32'h10;
 reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm;
 wire [31:0] fault_status;
 `include "axi_tasks.svh"
 ss_ps_link dut(.servo_vertical_pwm(),.feature_meta(129'b0),.feature_level(32'b0),.feature_level_valid(1'b0),.*);
 reg [31:0] value,status,seq;
 integer fd,which;
 task publish(input integer peak);
   tick();for(integer p=0;p<6;p=p+1)feature_pairs[p*160+:160]={32'd100,32'd800,32'd800,32'(peak),32'h114f3800|(32'(p)<<8)};
   feature_valid=1;tick();feature_valid=0;repeat(4)tick();
 endtask
 initial begin
   repeat(8)tick();rst_n=1;aresetn=1;repeat(6)tick();
   expect_read(0,32'h5a5a2026);expect_read('h6c,32'h10000);expect_read(4,8);
   for(which=0;which<2;which=which+1)begin
     put('h2c,which);put(4,11);put('h38,1);rd('h34,status,0);rd(8,seq,0);
     // 已发布手动扩展的STATUS bit18恒为1；BIST帧字段不变。
     check((status&32'hff1f7fff)==32'h57f39 && seq==which+1,
           $sformatf("BIST status/sequence status=%08x seq=%08x",status,seq));
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
   tick();aresetn=0;repeat(8)tick();check(!run_enable && !servo_pwm,"host reset stops new work");
   aresetn=1;repeat(5)tick();expect_read(4,8);expect_read(8,3);expect_read('h10,1000);
   check(fault_status[6],"host stop recorded");put('h38,4);put('h38,1);expect_read(8,4);expect_read('h10,2000);
   put('h38,4);put('h64,'hfff);check(!irq,"consumed then clear");
   // 无效总线写不能改变角度影子；上层格式错误可见。
   wr('h18,32'h4005a,0,3,3,2);expect_read('h18,0);check(fault_status[0],"AXI format error");
   put('h64,'hfff);put(4,9);publish(3000);tick();rst_n=0;aresetn=0;repeat(6)tick();rst_n=1;aresetn=1;
   repeat(6)tick();expect_read(8,0);check(!irq && !servo_pwm,"cold reset clears snapshots");
   $display("PS_PASS checks=%0d dual_bist=1 host_reset_preserves_two_slots=1",checks);$finish;
 end
 initial begin #5000000;$fatal(1,"PS_FAIL timeout");end
endmodule
