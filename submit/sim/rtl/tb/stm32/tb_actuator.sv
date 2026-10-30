`timescale 1ns/1ps
module tb_actuator;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,enabled=0,bist=0,fault=0,control_write=0,locked=0,result_qualified=0;
    reg [3:0] control=0;
    reg [19:0] shadow=20'h4005a;
    reg [31:0] watchdog_ticks=0,frame_id=0;
    wire permit,configured,pwm,accepted,rejected,watchdog_expired,unbound_error,draining;
    ss_actuator_control #(.ACTUATOR_BOUND(1),.CLK_FREQ_HZ(1000000)) dut(.*);
    integer checks=0;
    task check(input bit okay,input string message);
        checks=checks+1;if(!okay) $fatal(1,"ACTUATOR_FAIL %s",message);
    endtask
    task ticks(input integer n);repeat(n) @(negedge clk);endtask
    task send(input reg[3:0] value);
        @(negedge clk);control=value;control_write=1;
        @(negedge clk);control_write=0;
    endtask
    integer waiting,tail_count;
    reg [31:0] old_remaining;
    initial begin
        ticks(5);rst_n=1;ticks(5);check(!permit && !pwm && configured,"reset");
        send(1);check(rejected && !permit,"disabled denies");enabled=1;
        send(1);check(rejected && !permit,"zero watchdog denies");watchdog_ticks=100000;
        bist=1;send(1);check(rejected && !permit,"BIST denies");bist=0;
        send(1);check(permit,"permit granted");send(8);check(rejected,"no locked result");
        locked=1;result_qualified=1;frame_id=1;shadow=20'h4005a;
        send(8);check(accepted && dut.remaining==100000,"new action accepted");
        old_remaining=dut.remaining;send(8);check(rejected && dut.remaining<old_remaining,"duplicate cannot renew");
        waiting=0;
        while(!pwm && waiting<50000) begin ticks(1);waiting=waiting+1;end
        check(pwm,"fresh command opens at safe period boundary");ticks(100);
        send(2);check(!permit && pwm && draining,"STOP keeps active high pulse");
        tail_count=0;while(pwm && tail_count<2000) begin ticks(1);tail_count=tail_count+1;end
        check(!pwm && tail_count>1000 && tail_count<1500,"STOP drains full 1500 us pulse");
        ticks(21000);check(!pwm,"no subsequent pulse");
        send(1);send(8);check(rejected,"regrant does not allow old frame");
        frame_id=2;shadow=20'h4b45a;send(8);check(accepted,"invalid vertical axis ignored, fresh horizontal frame accepted");
        waiting=0;while(!pwm && waiting<50000) begin ticks(1);waiting=waiting+1;end
        check(pwm,"second motion");rst_n=0;#1;check(!pwm,"cold reset immediate low");ticks(2);rst_n=1;
        watchdog_ticks=20;send(1);frame_id=3;send(8);check(accepted,"watchdog setup");ticks(21);
        check(!permit && !pwm,"watchdog revokes");
        send(1);shadow=20'h400b5;frame_id=4;send(8);check(rejected,"angle range");
        shadow=20'hc005a;send(8);check(rejected,"vertical invalid");
        shadow=20'h4005a;fault=1;send(1);check(rejected && !permit,"fault denies");
        $display("ACTUATOR_PASS checks=%0d stop_tail_cycles=%0d",checks,tail_count);$finish;
    end
    initial begin #2000000;$fatal(1,"ACTUATOR_FAIL timeout");end
endmodule
