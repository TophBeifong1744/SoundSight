`timescale 1ns/1ps
// 实际AXI接口读取两槽音量/valid/capability，包含总线复位保留与BIST兼容。
module tb_audiometa;
 reg clk=0;always #8.138 clk=~clk;
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0;reg [31:0] feature_flags=32'h10;
 reg [31:0] feature_level=0;reg feature_level_valid=1;
 reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm;wire [31:0] fault_status;
 `include "axi_tasks.svh"
 reg [128:0] feature_meta=0;
 ss_ps_link #(.LEVEL_ENABLE(1),.AUDIO_ENABLE(1)) dut(.servo_vertical_pwm(),.*);
 reg [31:0] value;
 task publish(input integer level,input bit valid);
  tick();feature_meta={1'b1,32'd23,32'h12345678,32'(level),32'(level+10)};feature_level=level;feature_level_valid=valid;
  for(integer p=0;p<6;p=p+1)feature_pairs[p*160+:160]={32'd100,32'd800,32'd800,32'd1000,32'h114f3800|(32'(p)<<8)};
  feature_valid=1;tick();feature_valid=0;repeat(3)tick();
 endtask
 initial begin
  repeat(8)tick();rst_n=1;aresetn=1;repeat(6)tick();
  expect_read('h80,32'h10001);expect_read('h6c,32'h10001);rd('h34,value,0);check(value[17],"capability");
  publish(640,1);put('h38,1);expect_read('h14,640);rd('h34,value,0);check(value[5],"valid");
  expect_read('h84,23);expect_read('h88,640);expect_read('h8c,32'h12345678);expect_read('h90,650);expect_read('h94,32'h10400);
  publish(4,1);expect_read('h14,640);expect_read('h88,640); // 下一帧不能改变锁帧音量。
  aresetn=0;repeat(6)tick();aresetn=1;repeat(6)tick();expect_read('h14,640);
  put('h38,4);put('h38,1);expect_read('h14,4);expect_read('h88,4);expect_read('h90,14);put('h38,4);
  publish(777,0);put('h38,1);rd('h34,value,0);check(!value[5],"invalid metadata");put('h38,4);
  put('h64,32'h40);put('h2c,1);put(4,11);put('h38,1);
  expect_read('h14,100000);expect_read('h84,0);expect_read('h94,1024);rd('h34,value,0);check(value[3] && value[5] && value[17],"BIST synthetic preserved");
  $display("AUDIOMETA_PASS ABI=00010001 slots=2 reset_retains=1 BIST=100000");$finish;
 end
 initial begin #200000;$fatal(1,"AUDIOMETA_FAIL timeout");end
endmodule
