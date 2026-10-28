`timescale 1ns/1ps
module tb_queue;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame_valid=0;
    reg [959:0] frame_pairs=0;
    reg [31:0] frame_flags=0,frame_energy=0;
    reg frame_energy_valid=0;
    reg [2:0] command=0;
    wire locked,queued,occupied,locked_energy_valid,gap,exhausted,snapshot_error,overflow_pulse,counter_error;
    wire [959:0] locked_pairs;
    wire [31:0] locked_flags,locked_energy,locked_sequence,drop_count;
    ss_snapshot_queue dut(.frame_meta(129'b0),.locked_meta(),.*);
    integer states[0:1],sequences[0:1],payloads[0:1];
    integer seqno=0,drops=0,checks=0,seed=32'h31415926;
    task check(input bit okay,input string message);
        checks=checks+1;if(!okay) $fatal(1,"QUEUE_FAIL %s",message);
    endtask
    task step(input integer cmd,input bit arrival,input integer payload);
        integer li,chosen,free_slot;bit bad,overflow;
        begin
            @(negedge clk);command=3'(cmd);frame_valid=arrival;
            frame_pairs={30{32'(payload)}};frame_flags=32'(payload);frame_energy=32'(payload+1);frame_energy_valid=1;
            li=states[0]==2 ? 0 : states[1]==2 ? 1 : -1;chosen=-1;bad=0;overflow=0;
            case(cmd)
                0:;
                1: if(li<0) begin
                    if(states[0]==1 && states[1]==1) chosen=sequences[0]<sequences[1] ? 0 : 1;
                    else if(states[0]==1) chosen=0;else if(states[1]==1) chosen=1;
                    if(chosen>=0) states[chosen]=2;
                end
                2: if(li<0) bad=1;else states[li]=1;
                4: if(li<0) bad=1;else states[li]=0;
                default: bad=1;
            endcase
            if(arrival) begin
                seqno=seqno+1;free_slot=states[0]==0 ? 0 : states[1]==0 ? 1 : -1;
                if(free_slot<0) begin drops=drops+1;overflow=1;end
                else begin states[free_slot]=1;sequences[free_slot]=seqno;payloads[free_slot]=payload;end
            end
            @(posedge clk);#1;
            li=states[0]==2 ? 0 : states[1]==2 ? 1 : -1;
            check(locked==(li>=0),"locked");check(queued==(states[0]==1 || states[1]==1),"queued");
            check(occupied==(states[0]!=0 || states[1]!=0),"occupied");
            check(drop_count==drops && gap==(drops!=0),"drop/gap");
            check(snapshot_error==bad && overflow_pulse==overflow,"errors");
            if(li>=0) begin
                check(locked_sequence==sequences[li],"sequence");
                check(locked_pairs=={30{32'(payloads[li])}},"whole frame stable");
                check(locked_flags==payloads[li] && locked_energy==payloads[li]+1 && locked_energy_valid,"metadata");
            end else check(locked_pairs==0 && locked_flags==0 && locked_sequence==0,"empty reads zero");
        end
    endtask
    integer i,r;
    initial begin
        states[0]=0;states[1]=0;sequences[0]=0;sequences[1]=0;
        repeat(3) @(negedge clk);rst_n=1;
        step(0,1,10);step(1,0,0);step(0,1,20);step(0,1,30);
        step(1,0,0);step(2,0,0);step(1,0,0);step(4,1,40);step(1,0,0);
        for(i=0;i<1500;i=i+1) begin r=$random(seed);step(r&7,(r>>3)&1,i+100);end
        // 定向注入只用于无法跑 2^32 次的计数边界；正常队列流程未 force。
        @(negedge clk);dut.sequence_count=32'hfffffffe;command=0;frame_valid=1;
        @(posedge clk);#1;check(exhausted && counter_error,"sequence exhaustion");
        @(negedge clk);dut.drop_count=32'hffffffff;dut.exhausted=0;dut.state[0]=1;dut.state[1]=1;
        @(posedge clk);#1;check(drop_count==32'hffffffff && overflow_pulse,"drop saturation");
        @(negedge clk);rst_n=0;@(posedge clk);#1;check(!occupied && drop_count==0 && !gap,"cold reset");
        $display("QUEUE_PASS random_steps=1500 checks=%0d",checks);$finish;
    end
endmodule
