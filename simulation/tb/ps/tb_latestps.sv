`timescale 1ns/1ps
// Real PS register/queue integration. No behavioral replacement of the queue.
module tb_latestps;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,host_stop=0,commit=0,write_access=0,format_error=0;
 reg [7:0] address=0;reg [31:0] write_data=0;
 reg feature_valid=0,feature_level_valid=1,compute_draining=0;
 reg [128:0] feature_meta=0;reg [959:0] feature_pairs=0;
 reg [31:0] feature_flags=32'h10,feature_level=20000;reg [11:0] source_faults=0;
 wire [31:0] read_data,fault_status;wire irq,servo_pwm,servo_vertical_pwm,feature_ready;
 wire run_enable,stop_pulse,motion_permit,counter_exhausted;
 ss_ps_control_regs #(.AUDIO_ENABLE(1),.LEVEL_ENABLE(1),.DUAL_AXIS_ENABLE(1)) dut(.*);
 integer checks=0,k;
 task check(input bit b,input string why);checks++;if(!b)$fatal(1,"LATESTPS_FAIL %s",why);endtask
 task tick;@(negedge clk);endtask
 task put(input [7:0] a,input [31:0] v);
   tick();address=a;write_data=v;write_access=1;commit=1;
   tick();commit=0;write_access=0;repeat(2)tick();
 endtask
 task rd(input [7:0] a,input [31:0] expected);
   address=a;#1;check(read_data==expected,$sformatf("read %x got %x expected %x",a,read_data,expected));
 endtask
 task payload(input integer v);
   for(integer p=0;p<6;p++)feature_pairs[p*160+:160]={32'd10,32'd800,32'd800,32'(v),32'h114f3800|(32'(p)<<8)};
   feature_meta=129'(v);feature_level=v+100;
 endtask
 task publish(input integer v);
   tick();payload(v);feature_valid=1;tick();feature_valid=0;repeat(2)tick();
 endtask
 task reset_all;
   tick();rst_n=0;host_stop=0;commit=0;write_access=0;format_error=0;
   feature_valid=0;feature_flags='h10;source_faults=0;compute_draining=0;
   repeat(3)tick();rst_n=1;repeat(2)tick();
 endtask
 initial begin
   reset_all();rd('h98,'h4c415431);put(4,9);
   publish(10);publish(20);publish(30);rd('h68,1);rd('h64,0);
   put('h38,1);rd(8,2);rd('h10,20);
   publish(40);rd('h68,2);rd('h64,0);rd(8,2);rd('h10,20);
   put('h38,4);put('h38,1);rd(8,4);rd('h10,40);
   check(run_enable && !servo_pwm && !servo_vertical_pwm,"continue without enabling motion");
   // STOP and errors on the exact arrival edge must retain the old two frames.
   for(k=0;k<12;k++)begin
     reset_all();put(4,9);publish(10);publish(20);
     tick();payload(30);feature_valid=1;
     case(k)
       0:begin address=4;write_data=8;write_access=1;commit=1;end
       1:host_stop=1;
       2:feature_flags=32'h00100010;
       3:source_faults=12'h20;
       4:format_error=1;
       5:compute_draining=1;
       6:begin address='h58;write_data=2;write_access=1;commit=1;end
       7:begin address='h38;write_data=3;write_access=1;commit=1;end
       8:begin address='h98;write_data=0;write_access=1;commit=1;end
       9:begin address='hfc;write_access=0;commit=1;end
       10:begin address='h38;write_data=2;write_access=1;commit=1;end
       11:feature_flags=32'h18; // BIST-marked arrival cannot evict real data.
     endcase
     tick();feature_valid=0;host_stop=0;commit=0;write_access=0;
     source_faults=0;format_error=0;compute_draining=0;feature_flags='h10;repeat(3)tick();
     check(fault_status[3],"disabled replacement reports original overflow");
     put('h38,1);rd(8,1);rd('h10,10);put('h38,4);put('h38,1);rd(8,2);rd('h10,20);
   end
   // Cancellation with a FREE slot is retained for diagnosis, not discarded.
   reset_all();put(4,9);feature_flags=32'h00100010;publish(70);
   put('h38,1);rd(8,1);rd('h10,70);rd('h68,0);
   reset_all();put('h98,0);check(fault_status[1],"capability is readonly");
   $display("LATESTPS_PASS checks=%0d",checks);$finish;
 end
 initial begin #100000;$fatal(1,"LATESTPS_FAIL timeout");end
endmodule
