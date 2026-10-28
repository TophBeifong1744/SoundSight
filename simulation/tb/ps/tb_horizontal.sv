`timescale 1ns/1ps
// Real wrapper/AXI/queue/actuator at the actual 61.44 MHz counter configuration.
// Expected pulse widths derive from 500 + round(angle*2000/360), not DUT ROM.
module tb_horizontal;
 reg clk=0; always #8.138 clk=~clk;
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0; reg [31:0] feature_flags=32'h10;
 reg [31:0] feature_level=10000; reg feature_level_valid=1;
 reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm,servo_vertical_pwm;
 wire [31:0] fault_status;
 `include "axi_tasks.svh"
 bd_ps_link #(.LEVEL_ENABLE(1),.ACTUATOR_BOUND(1),.CLK_FREQ_HZ(61440000),
              .SERVO_MAX(360),.MECHANICAL_MIN(0),.MECHANICAL_MAX(360)) dut(.feature_meta(129'b0),.*);
 reg [31:0] value;
 integer cycles=0, rise_cycle, width_cycles, timeout_count;
 always @(posedge clk) begin
   cycles=cycles+1;
   if(rst_n && servo_vertical_pwm!==0) $fatal(1,"HORIZONTAL_FAIL vertical moved");
 end
 task publish;
   tick();
   for(integer p=0;p<6;p=p+1)
     feature_pairs[p*160+:160]={32'd100,32'd800,32'd800,32'd1000,32'h11202800|(32'(p)<<8)};
   feature_valid=1;tick();feature_valid=0;repeat(4)tick();put('h38,1);
 endtask
 task arm;
   put('h58,4);put('h60,32'd46080000);put('h58,1);expect_read('h58,1);
 endtask
 task command_angle(input integer angle);
   put('h18,32'h40000|angle);put('h58,8);expect_read('h64,0);
 endtask
 task pulse(input integer microseconds);
   timeout_count=0;
   while(!servo_pwm && timeout_count<3000000)begin tick();timeout_count=timeout_count+1;end
   check(servo_pwm,"fresh command produces pulse");rise_cycle=cycles;
   while(servo_pwm)tick();width_cycles=cycles-rise_cycle;
   check(width_cycles>=(microseconds*6144)/100-1 && width_cycles<=(microseconds*6144+99)/100+1,
         $sformatf("width got %0d cycles for %0d us",width_cycles,microseconds));
 endtask
 initial begin
   repeat(8)tick();rst_n=1;aresetn=1;repeat(6)tick();
   expect_read('h6c,32'h10001);rd('h34,value,0);check(value[19] && value[17],"capabilities");
   repeat(200)tick();check(!servo_pwm,"no motion at boot");
   put(4,9);publish();arm();check(!servo_pwm,"arming alone never opens PWM");
   command_angle(180);pulse(1500);
   put('h38,4);publish();command_angle(270);pulse(2000);
   // Normal STOP during high must finish that pulse, then suppress future ones.
   while(!servo_pwm)tick();rise_cycle=cycles;repeat(200)tick();put('h58,2);
   check(servo_pwm,"STOP must not truncate pulse");
   while(servo_pwm)tick();width_cycles=cycles-rise_cycle;
   check(width_cycles>=122879 && width_cycles<=122881,"STOP preserves 2000us high");
   repeat(1300000)begin tick();check(!servo_pwm,"STOP blocks subsequent pulses");end
   put(4,8);put('h38,4);put('h64,32'h40);put(4,9);publish();arm();command_angle(90);pulse(1000);
   put('h38,4);publish();command_angle(0);pulse(500);
   put('h38,4);publish();command_angle(360);pulse(2500);
   // Bus reset drops permit and retains the currently locked real frame.
   aresetn=0;repeat(8)tick();aresetn=1;repeat(8)tick();expect_read('h08,5);
   expect_read('h58,0);check(!servo_pwm,"bus reset no automatic restart");
   put(4,8);put('h38,4);put('h64,32'h40);put(4,9);publish();
   put('h60,100);put('h58,1);command_angle(180);repeat(150)tick();
   rd('h64,value,0);check(value[8],"hardware watchdog fault");check(!servo_pwm,"watchdog stops PWM");
   rst_n=0;#1;check(!servo_pwm && !servo_vertical_pwm,"cold reset low");
   $display("HORIZONTAL_PASS real_AXI=1 clock=61440000 widths_us=500,1000,1500,2000,2500 STOP=full_pulse reset=retain watchdog=checked vertical=LOW checks=%0d",checks);
   $finish;
 end
 initial begin #300000000;$fatal(1,"HORIZONTAL_FAIL timeout");end
endmodule
