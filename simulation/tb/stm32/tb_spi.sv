`timescale 1ns/1ps
module tb_spi;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,cs_n=1,sck=0,mosi=0;
    wire miso,commit,write_access,format_error;
    wire [6:0] address;
    wire [31:0] write_data;
    reg [31:0] read_data=32'h89abcdef;
    ss_spi_mode0 dut(.*);
    integer commits=0,errors=0,checks=0;
    reg [31:0] saved_write;
    reg [6:0] saved_address;
    always @(posedge clk) begin
        if(commit) begin commits=commits+1;saved_write=write_data;saved_address=address;end
        if(format_error) errors=errors+1;
    end
    task ticks(input integer n);repeat(n) @(negedge clk);endtask
    task check(input bit okay,input string message);
        checks=checks+1;if(!okay)$fatal(1,"SPI_FAIL %s",message);
    endtask
    task packet(input reg[39:0] payload,input integer bits,input integer half_period,input bit change_read,input bit reset_mid,output reg[31:0] result);
        integer i,old_commits;
        old_commits=commits;result=0;cs_n=0;ticks(10);
        for(i=0;i<bits;i=i+1) begin
            mosi=i<40?payload[39-i]:1;ticks(half_period);sck=1;
            if(i>=8 && i<40) result={result[30:0],miso};
            ticks(half_period);sck=0;
            if(i==10 && change_read) read_data=32'h12345678;
            if(i==20 && reset_mid) begin rst_n=0;ticks(4);rst_n=1;end
        end
        ticks(10);check(commits==old_commits,"no commit before CS rises");cs_n=1;ticks(16);
    endtask
    reg [31:0] got;
    initial begin
        ticks(8);rst_n=1;ticks(16);
        packet({8'h04,32'b0},40,8,1,0,got);
        check(commits==1 && errors==0 && got==32'h89abcdef,"8-cycle boundary/read latched");
        packet({8'h98,32'h12345678},40,31,0,0,got);
        check(commits==2 && saved_write==32'h12345678 && saved_address=='h18 && write_access,"write endian/header");
        packet({8'h98,32'hdeadbeef},40,6,0,0,got);check(commits==2 && errors==1,"too fast rejected");
        packet({8'h98,32'hdeadbeef},0,8,0,0,got);check(commits==2 && errors==2,"zero length");
        packet({8'h98,32'hdeadbeef},70,8,0,0,got);check(commits==2 && errors==3,"counter saturates long frame");
        packet({8'h98,32'hdeadbeef},40,8,0,1,got);check(commits==2,"reset discards partial transaction");
        packet({8'h98,32'hcafe1234},40,8,0,0,got);check(commits==3 && saved_write==32'hcafe1234,"recovery next CS");
        $display("SPI_PASS checks=%0d commits=%0d errors=%0d",checks,commits,errors);$finish;
    end
endmodule
