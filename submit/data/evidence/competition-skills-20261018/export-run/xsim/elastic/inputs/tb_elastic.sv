`timescale 1ns/1ps
module elastic_trial #(parameter W=8) (output reg done, output integer checks);
    reg clk=0, rst_n=0, in_valid=0, out_ready=0;
    reg [W-1:0] in_data=0;
    wire in_ready, out_valid;
    wire [W-1:0] out_data;
    reg [W-1:0] expected [0:2047];
    integer head=0, tail=0, cycle=0, i;
    integer sent=0, consumed=0, discarded=0;
    reg accepted=0, was_stalled=0;
    reg [W-1:0] held;
    reg [31:0] rng=32'h12345678;
    always #5 clk=~clk;
    elastic_stage #(.WIDTH(W)) dut(.*);

    // Accepted-transaction occupancy is independent of the DUT's valid state.
    // Check BOTH the old slot at the sampling edge and the new slot after NBA.
    task check_slot(input reg after_edge);
        integer occupancy;
        begin
            occupancy=tail-head;
            checks=checks+1;
            if (occupancy<0 || occupancy>1)
                $fatal(1,"SKILL_FAIL capacity width=%0d cycle=%0d after_edge=%0d occupancy=%0d",W,cycle,after_edge,occupancy);
            checks=checks+1;
            if (out_valid !== (occupancy==1))
                $fatal(1,"SKILL_FAIL one_edge_valid width=%0d cycle=%0d after_edge=%0d expected=%0d actual=%b",W,cycle,after_edge,occupancy==1,out_valid);
            // Reset specifies valid/data, not ready. Do not invent a reset-ready rule.
            if (rst_n) begin
                checks=checks+1;
                if (in_ready !== ((occupancy==0) || out_ready))
                    $fatal(1,"SKILL_FAIL slot_ready width=%0d cycle=%0d after_edge=%0d occupancy=%0d actual=%b",W,cycle,after_edge,occupancy,in_ready);
            end
            if (occupancy==1) begin
                checks=checks+1;
                if (out_data !== expected[head])
                    $fatal(1,"SKILL_FAIL one_edge_data width=%0d cycle=%0d after_edge=%0d transaction=%0d expected=%h actual=%h",W,cycle,after_edge,head,expected[head],out_data);
            end
            checks=checks+1;
            if (sent != consumed+discarded+occupancy)
                $fatal(1,"SKILL_FAIL accounting width=%0d cycle=%0d sent=%0d consumed=%0d discarded=%0d pending=%0d",W,cycle,sent,consumed,discarded,occupancy);
        end
    endtask

    task tick(input reg reset_ok, input reg valid_value,
              input reg [W-1:0] data_value, input reg ready_value);
        begin
            @(negedge clk);
            rst_n=reset_ok; in_valid=valid_value;
            in_data=data_value; out_ready=ready_value;
            @(posedge clk);
            cycle=cycle+1;
            accepted=0;
            if (!rst_n) begin
                discarded=discarded+tail-head;
                head=0; tail=0; was_stalled=0;
            end else begin
                check_slot(0);
                if (was_stalled) begin
                    checks=checks+1;
                    if (out_valid !== 1'b1 || out_data !== held)
                        $fatal(1,"SKILL_FAIL hold width=%0d cycle=%0d expected=%h actual=%h",W,cycle,held,out_data);
                end
                if ((out_valid !== 1'b0 && out_valid !== 1'b1) ||
                    (in_ready !== 1'b0 && in_ready !== 1'b1))
                    $fatal(1,"SKILL_FAIL unknown control width=%0d cycle=%0d",W,cycle);
                if (out_valid && out_ready) begin
                    checks=checks+1;
                    if (head>=tail)
                        $fatal(1,"SKILL_FAIL unexpected output width=%0d cycle=%0d",W,cycle);
                    if (out_data !== expected[head])
                        $fatal(1,"SKILL_FAIL data width=%0d cycle=%0d transaction=%0d expected=%h actual=%h",W,cycle,head,expected[head],out_data);
                    head=head+1;
                    consumed=consumed+1;
                end
                if (in_valid && in_ready) begin
                    if (tail>=2048) $fatal(1,"SKILL_FAIL scoreboard overflow");
                    expected[tail]=in_data; tail=tail+1; accepted=1;
                    sent=sent+1;
                end
                was_stalled=out_valid && !out_ready;
                held=out_data;
            end
            #1;
            check_slot(1);
            if (!rst_n) begin
                checks=checks+1;
                if (out_valid !== 1'b0 || out_data !== {W{1'b0}})
                    $fatal(1,"SKILL_FAIL reset width=%0d cycle=%0d",W,cycle);
            end
        end
    endtask

    initial begin
        done=0; checks=0;
        tick(0,0,0,0);
        tick(1,1,1,0); // empty stage must accept even when output is stalled
        if (!accepted) $fatal(1,"SKILL_FAIL empty acceptance width=%0d",W);
        repeat(4) tick(1,0,0,0);
        tick(0,0,0,0); // reset discards pending output
        for (i=0;i<32;i=i+1) begin
            tick(1,1,i,1);
            checks=checks+1;
            if (!accepted) $fatal(1,"SKILL_FAIL full rate width=%0d cycle=%0d",W,cycle);
        end
        tick(1,0,0,1);
        for(i=0;i<400;i=i+1) begin
            rng=rng ^ (rng<<13); rng=rng ^ (rng>>17); rng=rng ^ (rng<<5);
            if(in_valid && !accepted) tick(1,1,in_data,rng[1]);
            else tick(1,rng[0],rng[W-1:0],rng[1]);
        end
        // Finish a producer transaction already presented before draining.
        if(in_valid && !accepted) tick(1,1,in_data,1);
        repeat(4) tick(1,0,0,1);
        checks=checks+1;
        if(head!=tail) $fatal(1,"SKILL_FAIL undrained width=%0d sent=%0d received=%0d",W,tail,head);
        $display("ACCOUNTING width=%0d sent=%0d consumed=%0d discarded=%0d pending=%0d",W,sent,consumed,discarded,tail-head);
        $display("CASE_PASS width=%0d checks=%0d",W,checks);
        done=1;
    end
endmodule

module tb_elastic;
    wire d1,d8,d16;
    wire [31:0] c1,c8,c16;
    elastic_trial #(.W(1)) a(d1,c1);
    elastic_trial #(.W(8)) b(d8,c8);
    elastic_trial #(.W(16)) c(d16,c16);
    initial begin
        wait(d1 && d8 && d16);
        $display("SKILL_PASS cases=3 checks=%0d",c1+c8+c16);
        $finish;
    end
    initial begin #100000; $fatal(1,"SKILL_FAIL watchdog"); end
endmodule
