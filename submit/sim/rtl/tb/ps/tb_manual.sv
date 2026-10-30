`timescale 1ns/1ps
// Actual PS AXI/register/PWM path, no audio input. 1MHz parameter shortens the
// watchdog simulation while preserving 20ms PWM and 750ms lease in real time.
module tb_manual;
 reg clk=0; always #500 clk=~clk;
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0;reg [31:0] feature_flags=32'h10;
 reg [31:0] feature_level=0;reg feature_level_valid=0;reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm,servo_vertical_pwm;wire [31:0] fault_status;
 `include "axi_tasks.svh"
 bd_ps_link #(.LEVEL_ENABLE(1),.ACTUATOR_BOUND(1),.CLK_FREQ_HZ(1000000),
              .SERVO_MAX(360),.MECHANICAL_MIN(0),.MECHANICAL_MAX(360)) dut(.feature_meta(129'b0),.*);
 reg [31:0] value;integer count,rise,width;
 always @(posedge clk) if(rst_n) begin
   if(servo_vertical_pwm!==0) $fatal(1,"MANUAL_FAIL vertical output");
   if(run_enable && dut.u_core.regs.manual_active) $fatal(1,"MANUAL_FAIL modes overlap");
 end
 task reset_all;
   rst_n=0;aresetn=0;feature_valid=0;source_faults=0;repeat(5)tick();
   rst_n=1;aresetn=1;repeat(5)tick();
 endtask
 task setup_arm(input integer angle);
   put('h7c,(190<<16)|170);put('h78,angle);put('h74,1);expect_read('h74,1);
 endtask
 task command_and_pulse;
   put('h74,2);expect_read('h64,0);count=0;
   while(!servo_pwm && count<40000)begin tick();count=count+1;end
   check(servo_pwm,"manual PWM without audio");
 endtask
 initial begin
   reset_all();expect_read('h70,32'h4d534301);rd('h34,value,0);check(value[18],"manual capability");
   repeat(21000)begin tick();check(!servo_pwm,"boot no PWM");end
   // No limits yet: ARM rejected, not enabled.
   put('h74,1);rd('h64,value,0);check(value[7],"limits required");expect_read('h74,0);
   reset_all();setup_arm(180);repeat(21000)begin tick();check(!servo_pwm,"ARM no old command");end
   command_and_pulse();width=0;while(servo_pwm)begin width=width+1;tick();end
   check(width==1500,"180deg pulse=1500us with no sound");expect_read('h04,8);expect_read('h08,0);
   // Stop in the middle of a real pulse preserves its complete high width.
   while(!servo_pwm)tick();width=0;
   fork
     begin while(servo_pwm)begin width=width+1;tick();end end
     begin repeat(200)tick();put('h74,0);end
   join
   check(width==1500,"STOP finishes existing high pulse");
   repeat(21000)begin tick();check(!servo_pwm,"STOP blocks future pulse");end
   expect_read('h74,0);
   reset_all();setup_arm(191);put('h74,2);rd('h64,value,0);check(value[7],"out of range rejected");
   repeat(21000)begin tick();check(!servo_pwm,"no clamp into range");end
   reset_all();setup_arm(180);command_and_pulse();put('h7c,(360<<16));
   rd('h64,value,0);check(value[1],"live limit edit rejected");
   repeat(3000)tick();expect_read('h74,0);
   // Heartbeats extend the lease. Then deliberately stop renewing it.
   reset_all();setup_arm(180);put('h74,2);
   repeat(3)begin repeat(300000)tick();put('h74,2);expect_read('h74,1);end
   repeat(755000)tick();rd('h64,value,0);check(value[8],"manual watchdog expires");
   check(!servo_pwm,"watchdog output low after pulse drain");expect_read('h74,0);
   put('h74,2);expect_read('h74,0); // cannot auto-restart after expiry
   reset_all();setup_arm(180);put('h74,2);put('h04,9);
   rd('h64,value,0);check(value[1] && !run_enable,"capture start rejected while manual active");
   reset_all();put('h04,9);put('h7c,(190<<16)|170);put('h74,1);
   rd('h64,value,0);check(value[7],"manual arm rejected during capture");expect_read('h74,0);
   // Legacy follow path still requires a qualified frame, never bypassed.
   reset_all();put('h04,9);put('h60,100000);put('h58,1);put('h18,32'h400b4);put('h58,8);
   rd('h64,value,0);check(value[7],"sound COMMIT without frame rejected");
   reset_all();setup_arm(180);command_and_pulse();aresetn=0;repeat(3000)tick();aresetn=1;
   repeat(5)tick();expect_read('h74,0);check(!servo_pwm,"bus reset stops no restart");
   put('h64,32'h40);put('h74,1);rd('h64,value,0);check(value[7],"bus reset requires limits rewrite");
   reset_all();setup_arm(180);command_and_pulse();source_faults=1;repeat(3000)tick();
   expect_read('h74,0);check(!servo_pwm,"source fault stops manual");
   reset_all();setup_arm(180);command_and_pulse();put('h58,2);repeat(3000)tick();
   expect_read('h74,0);check(!servo_pwm,"global STOP stops manual");
   reset_all();setup_arm(180);command_and_pulse();rst_n=0;#1;
   check(!servo_pwm,"cold reset immediate low");
   $display("MANUAL_PASS checks=%0d audio_frames=0 manual_without_audio=1 range=1 watchdog=1 stop=1 mode_mutex=1",checks);
   $finish;
 end
 initial begin #3000000000.0;$fatal(1,"MANUAL_FAIL timeout");end
endmodule
