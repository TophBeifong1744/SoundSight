`timescale 1ns/1ps
module tb_link;
    reg clk=0;always #8.138 clk=~clk;
    reg rst_n=0,spi_cs_n=1,spi_sck=0,spi_mosi=0,feature_valid=0,compute_draining=0;
    reg [959:0] feature_pairs=0;
    reg [31:0] feature_flags=32'h10;
    reg [11:0] source_faults=0;
    wire spi_miso,irq,servo_pwm,feature_ready,run_enable,stop_pulse,motion_permit,counter_exhausted;
    wire [31:0] fault_status;
    ss_stm32_link dut(.*);
    integer checks=0,transactions=0;
    task check(input bit okay,input string message);
        checks=checks+1;if(!okay) $fatal(1,"LINK_FAIL %s",message);
    endtask
    task ticks(input integer n);repeat(n) @(negedge clk);endtask
    task reset;
        rst_n=0;spi_cs_n=1;spi_sck=0;spi_mosi=0;feature_valid=0;source_faults=0;
        ticks(8);rst_n=1;ticks(20);
    endtask
    // 外部引脚真实移位，不直接调用 RTL 寄存器。全事务在引脚释放前无写副作用。
    task exchange(input bit wr,input reg[6:0] addr,input reg[31:0] data,input integer nbits,output reg[31:0] result);
        reg [39:0] packet;integer k;
        begin
            packet={wr,addr,data};result=0;spi_cs_n=0;ticks(20);
            for(k=0;k<nbits;k=k+1) begin
                spi_mosi=k<40 ? packet[39-k] : 1'b1;ticks(31);spi_sck=1;
                if(k>=8 && k<40) result={result[30:0],spi_miso};
                ticks(31);spi_sck=0;
            end
            ticks(20);spi_cs_n=1;ticks(20);transactions=transactions+1;
        end
    endtask
    reg [31:0] tmp;
    task wr(input reg[6:0] addr,input reg[31:0] data);exchange(1,addr,data,40,tmp);endtask
    task rd(input reg[6:0] addr,output reg[31:0] data);exchange(0,addr,0,40,data);endtask
    task read_expect(input reg[6:0] addr,input reg[31:0] expected);
        reg [31:0] got;
        rd(addr,got);check(got===expected,$sformatf("addr=%02x got=%08x expected=%08x",addr,got,expected));
    endtask
    task publish(input integer payload);
        integer p;
        ticks(1);
        for(p=0;p<6;p=p+1) feature_pairs[p*160+:160]={32'(payload+3),32'(payload+2),32'(payload+1),32'(payload),32'h114f3800 | (32'(p)<<8)};
        feature_valid=1;ticks(1);feature_valid=0;ticks(4);
    endtask
    integer vector_id,i,k,fd,transaction_start;
    integer lags0[0:5]='{5,-3,0,1,-1,2};
    integer lags1[0:5]='{4,4,0,0,-4,-4};
    reg [31:0] words[0:4],status,sequence_value;
    initial begin
        reset();read_expect('h00,32'h5a5a2026);read_expect('h6c,32'h00010000);read_expect('h04,8);
        check(!irq && !servo_pwm,"reset quiet");
        exchange(1,'h18,32'h4005a,39,tmp);read_expect('h18,0);check(fault_status[0],"short frame error");
        reset();exchange(1,'h18,32'h4005a,47,tmp);read_expect('h18,0);check(fault_status[0],"long frame error");
        reset();read_expect('h30,32'hdeadbeef);check(fault_status[1],"unknown read");
        wr('h00,0);wr('h04,32'h18);read_expect('h04,8);wr('h1c,6);read_expect('h1c,0);
        wr('h64,32'hfff);check(fault_status==0,"disabled W1C");
        for(vector_id=0;vector_id<2;vector_id=vector_id+1) begin
            reset();wr('h2c,vector_id);wr('h04,11);check(irq && !run_enable,"BIST published");
            transaction_start=transactions;wr('h38,1);rd('h34,status);rd('h08,sequence_value);
            check(sequence_value==1 && (status & 32'hff1f7fff)==32'h00017f39,"BIST status");
            fd=$fopen(vector_id ? "bist_pass.txt" : "bist_reject.txt","w");
            $fdisplay(fd,"%08x %08x",sequence_value,status);
            for(i=0;i<6;i=i+1) begin
                wr('h1c,i);rd('h0c,words[0]);rd('h10,words[1]);rd('h20,words[2]);rd('h24,words[3]);rd('h28,words[4]);
                check(words[0]==(32'h664f1800 | (32'(i)<<8) | (32'(vector_id?lags1[i]:lags0[i]) & 255)),"BIST flags/order/lag");
                check(words[1]==1000 && words[2]==800 && words[3]==(vector_id?800:600) && words[4]==100,"BIST values");
                $fdisplay(fd,"%08x %08x %08x %08x %08x",words[0],words[1],words[2],words[3],words[4]);
            end
            wr('h38,4);check(transactions-transaction_start==40,"standard 40 transactions");$fclose(fd);
            check(!irq && !servo_pwm,"BIST consumed no motion");
            wr('h60,100000);wr('h58,1);check(!motion_permit && !servo_pwm && fault_status[10],"unbound BIST denies permit");
        end
        reset();wr('h04,9);check(run_enable,"real enabled");
        publish(100);wr('h38,1);read_expect('h08,1);read_expect('h10,100);
        publish(200);publish(300);read_expect('h08,1);read_expect('h10,100);read_expect('h68,1);
        check(fault_status[3],"overflow fault");wr('h64,32'hfff);check(fault_status[3],"no clear while enabled");
        wr('h38,1);read_expect('h08,1);wr('h38,2);wr('h38,1);read_expect('h08,1);
        wr('h38,4);wr('h38,1);read_expect('h08,2);read_expect('h10,200);
        wr('h58,2);check(!run_enable,"STOP stops admission");read_expect('h08,2);read_expect('h10,200);
        wr('h04,8);wr('h38,4);wr('h64,32'hfff);check(!irq,"clear consumed faults");
        wr('h38,4);check(fault_status[2],"consume without lock");
        reset();wr('h38,3);check(fault_status[2],"multicommand rejected");
        reset();publish(700);wr('h04,10);check(fault_status[1],"mode change with queued frame rejected");
        reset();wr('h04,9);publish(1000);wr('h04,8);check(irq,"disable preserves snapshot");
        wr('h38,1);read_expect('h10,1000);
        reset();source_faults=12'h20;ticks(2);wr('h64,32'hfff);check(fault_status[5],"active cause wins clear");
        source_faults=0;wr('h64,32'hfff);check(fault_status==0,"clear resolved cause");
        $display("LINK_PASS checks=%0d spi_transactions=%0d double_bist=2 standard_read_transactions=40",checks,transactions);$finish;
    end
    initial begin #50000000;$fatal(1,"LINK_FAIL timeout");end
endmodule
