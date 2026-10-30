`timescale 1ns/1ps
// 从SPI写enable，到真实官方FFT/IFFT计算，再由SPI逐字读回完整六对。
// 仅PCM来源为测试台；不会把BIST当自然声源，也不使能PWM。
module tb_stm32;
 reg clk=0;always #8.138 clk=~clk;
 reg rst_n=0;
 reg [3:0] pdm_data=0;
 wire [3:0] pdm_clocks;
 reg spi_cs_n=1,spi_sck=0,spi_mosi=0;
 wire spi_miso,irq,servo_pwm;
 wire [31:0] fault_status;
 wire [3:0] debug_frontend;
 wire [4:0] debug_backend;
 ss_stm32_tile #(.WARMUP_SAMPLES(16)) dut(.*);
 reg fixture_valid=0;
 reg [95:0] fixture_pcm=0;
 reg [31:0] rng=32'h1765ca19;
 integer checks=0,cycles=0,p,word_index,fd;
 task check(input bit okay,input string message);
   checks=checks+1;if(!okay)$fatal(1,"STM32_FAIL %s",message);
 endtask
 task ticks(input integer n);repeat(n)@(negedge clk);endtask
 task transfer(input reg[7:0] header,input reg[31:0] data,output reg[31:0] result);
   reg[39:0] packet;integer i;
   packet={header,data};result=0;spi_cs_n=0;ticks(12);
   for(i=0;i<40;i=i+1)begin
     spi_mosi=packet[39-i];ticks(31);spi_sck=1;
     if(i>=8)result={result[30:0],spi_miso};
     ticks(31);spi_sck=0;
   end
   ticks(12);spi_cs_n=1;ticks(16);
 endtask
 reg[31:0] got;
 reg[31:0] words[0:4];
 reg[7:0] addresses[0:4];
 always @(posedge clk)begin
   cycles=cycles+1;if(cycles%100000==0)$display("STM32_PROGRESS cycle=%0d front=%0d back=%0d",cycles,debug_frontend,debug_backend);
   if(servo_pwm)$fatal(1,"STM32_FAIL PWM during unbound test");
 end
 initial begin
   addresses[0]='h0c;addresses[1]='h10;addresses[2]='h20;addresses[3]='h24;addresses[4]='h28;
   force dut.compute.sample_valid=fixture_valid;force dut.compute.sample_pcm=fixture_pcm;force dut.compute.sample_clipped=0;
   ticks(16);rst_n=1;ticks(16);
   transfer(8'h00,0,got);check(got==32'h5a5a2026,"magic");
   transfer(8'hac,1,got);transfer(8'h84,11,got);
   check(irq && debug_frontend==0 && !servo_pwm,"BIST leaves compute idle");
   transfer(8'hb8,1,got);transfer(8'h08,0,got);check(got==1,"BIST frame sequence");
   transfer(8'h0c,0,got);check(got==32'h664f1804,"pass BIST first pair");
   transfer(8'hb8,4,got);check(!irq && fault_status==0,"BIST consumed");
   transfer(8'h84,10,got);transfer(8'h84,8,got);transfer(8'he4,32'hfff,got);
   check(fault_status==0,"disable and clear completed stop");
   transfer(8'h84,9,got);
   for(integer i=0;i<1024;i=i+1)begin
     ticks(16);rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
     fixture_pcm={4{{4{rng[19]}},rng[19:0]}};fixture_valid=1;ticks(1);fixture_valid=0;
   end
   wait(irq);check(fault_status==0,"real result IRQ without fault");
   transfer(8'hb8,1,got);transfer(8'h34,0,got);
   check(got[0] && got[4] && !got[3] && !got[5] && got[13:8]==63,"real status flags");
   transfer(8'h08,0,got);check(got==2,"common BIST/real sequence");
   fd=$fopen("stm32_real_spi.txt","w");
   for(p=0;p<6;p=p+1)begin
     transfer(8'h9c,p,got);
     for(word_index=0;word_index<5;word_index=word_index+1)transfer(addresses[word_index],0,words[word_index]);
     check(words[0]==(32'h11413800 | (p<<8)),"feature0 exact");
     check(words[1]==32'h104000 && words[2]==32'hf5739 && words[3]==32'hf5739 && words[4]==32'hcc2d8,"four correlations exact");
     $fdisplay(fd,"%0d %08x %08x %08x %08x %08x",p,words[0],words[1],words[2],words[3],words[4]);
   end
   transfer(8'hb8,4,got);check(!irq && fault_status==0,"consume real result");
   transfer(8'h84,8,got);
   $fclose(fd);$display("STM32_PASS checks=%0d cycles=%0d bist_and_real_spi=1 official_fft_ifft=1",checks,cycles);$finish;
 end
 initial begin #15000000;$fatal(1,"STM32_FAIL timeout");end
endmodule
