`timescale 1ns/1ps
// 官方 MMCM 原语的有界启动/外部冷复位测试；不模拟板上抖动或布线延迟。
module tb_clock;
    reg sys_clk=0; always #10 sys_clk=~sys_clk;
    reg cold_reset_n=0;
    wire clk,rst_n;
    ss_board_clock dut(.*);
    realtime t0,period_ns;
    integer i;
    initial begin
        #1000;cold_reset_n=1;
        wait(rst_n===1'b1);
        @(posedge clk);t0=$realtime;
        repeat(100) @(posedge clk);
        period_ns=($realtime-t0)/100.0;
        if(period_ns<16.26 || period_ns>16.29) $fatal(1,"CLOCK_FAIL period %f",period_ns);
        @(negedge clk);#1;cold_reset_n=0;
        #0.01;if(rst_n!==0) $fatal(1,"CLOCK_FAIL asynchronous assertion");
        repeat(5) @(negedge clk);cold_reset_n=1;
        for(i=0;i<2;i=i+1) begin
            @(posedge clk);#0.01;if(rst_n!==0) $fatal(1,"CLOCK_FAIL early release");
        end
        @(posedge clk);#0.01;if(rst_n!==1) $fatal(1,"CLOCK_FAIL missing release");
        $display("CLOCK_PASS period_ns=%f reset_release_cycles=3",period_ns);$finish;
    end
    initial begin #200000;$fatal(1,"CLOCK_FAIL timeout");end
endmodule
