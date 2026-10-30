`timescale 1ns/1ps
module pcm_trial #(parameter W=24)(output reg done, output integer checks);
    reg signed [W-1:0] mic0_in,mic1_in,mic2_in,mic3_in;
    wire [127:0] pcm_packed;
    reg [31:0] rng=32'h76543210;
    integer i,k;
    reg [31:0] word_expected;
    longint signed value;
    pcm4_signext_pack #(.SAMPLE_WIDTH(W)) dut(.*);
    task check;
        begin
            #1;
            for(k=0;k<4;k=k+1) begin
                case(k)
                    0: value=$signed(mic0_in);
                    1: value=$signed(mic1_in);
                    2: value=$signed(mic2_in);
                    3: value=$signed(mic3_in);
                endcase
                word_expected=value; // signed integer interpretation, not DUT concatenation
                checks=checks+1;
                if(pcm_packed[k*32+:32] !== word_expected)
                    $fatal(1,"SKILL_FAIL sign_or_mapping width=%0d sample=%0d channel=%0d expected=%h actual=%h",W,i,k,word_expected,pcm_packed[k*32+:32]);
            end
        end
    endtask
    initial begin
        done=0; checks=0; i=0;
        mic0_in=0; mic1_in=-1; mic2_in=1; mic3_in={1'b1,{(W-1){1'b0}}}; check();
        mic0_in={1'b0,{(W-1){1'b1}}}; mic1_in=mic3_in; mic2_in=-1; mic3_in=0; check();
        for(i=0;i<64;i=i+1) begin
            rng=rng ^ (rng<<13); rng=rng ^ (rng>>17); rng=rng ^ (rng<<5);
            mic0_in=rng; mic1_in=~rng; mic2_in=rng>>1; mic3_in=rng<<1; check();
        end
        done=1;
    end
endmodule
module tb_pcm4_skill;
    wire d2,d24,d32;
    wire [31:0] c2,c24,c32;
    pcm_trial #(.W(2)) a(d2,c2);
    pcm_trial #(.W(24)) b(d24,c24);
    pcm_trial #(.W(32)) c(d32,c32);
    initial begin
        wait(d2 && d24 && d32);
        $display("SKILL_PASS cases=3 checks=%0d",c2+c24+c32);
        $finish;
    end
    initial begin #10000; $fatal(1,"SKILL_FAIL watchdog"); end
endmodule
