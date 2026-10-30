`timescale 1ns/1ps
// 从外部PDM引脚驱动到六对特征/SPI读回，不force内部PCM或FFT。
// 全部通道输入同一PRBS，所以六对必须相同且lag=0；这不是方位精度测试。
// 128ns是数据手册100ns加本设计外部/IO预算28ns；上升沿后5ns进入高阻。
module tb_pdm;
 reg clk=0; always #8.138020833 clk=~clk;
 reg core_clk=0; initial begin #2.3;forever #5 core_clk=~core_clk;end
 integer core_cycles=0;
 reg rst_n=0;
 reg [3:0] pdm_data=0;
 wire [3:0] pdm_clocks;
 reg spi_cs_n=1,spi_sck=0,spi_mosi=0;
 wire spi_miso,irq,servo_pwm,feature_valid,feature_ready,run_enable,draining;
 wire [959:0] feature_pairs;
 wire [31:0] feature_flags,fault_status;
 wire [11:0] source_faults;
 wire [3:0] debug_frontend; wire [4:0] debug_backend;
 // 只缩短传感器上电等待，1024/512、PDM/CIC、FFT和六对计算参数均不变。
 bd_clean_compute #(.WARMUP_SAMPLES(32)) compute(
  .clk(core_clk),.rst_n(rst_n),.io_clk(clk),.io_rst_n(rst_n),.enable(run_enable),.pdm_data(pdm_data),.pdm_clocks(pdm_clocks),
  .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_pairs(feature_pairs),
  .feature_flags(feature_flags),.draining(draining),.source_faults(source_faults),
  .debug_frontend(debug_frontend),.debug_backend(debug_backend));
 bd_stm32_link link(.clk(clk),.rst_n(rst_n),.spi_cs_n(spi_cs_n),.spi_sck(spi_sck),.spi_mosi(spi_mosi),
  .spi_miso(spi_miso),.irq(irq),.servo_pwm(servo_pwm),.feature_valid(feature_valid),.feature_ready(feature_ready),
  .feature_pairs(feature_pairs),.feature_flags(feature_flags),.compute_draining(draining),.source_faults(source_faults),
  .run_enable(run_enable),.fault_status(fault_status),.stop_pulse(),.motion_permit(),.counter_exhausted());
 integer cycles=0,checks=0,pcm_checks=0,bit_count=0,frames=0,frame_start_cycle=0,max_service=0;
 integer history[0:189],weights[0:189],history_head=0;
 integer sum,reference_pcm,k,j,clock_edges=0;
 reg [31:0] rng=32'h1765ca19;
 reg expected_bit=0;
 task check(input bit okay,input string message);
  checks=checks+1;if(!okay)$fatal(1,"PDM_FAIL %s cycle=%0d",message,cycles);
 endtask
 // 三个长度64的矩形FIR卷积，与RTL三级积分器/梳状滤波的写法不同。
 function integer triangle(input integer n);triangle=n<0?0:(n+1)*(n+2)/2;endfunction
 initial begin
  for(k=0;k<190;k=k+1)begin
   history[k]=0;weights[k]=triangle(k)-3*triangle(k-64)+3*triangle(k-128);
  end
 end
 always @(negedge pdm_clocks[0]) if(rst_n)begin
  rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};expected_bit=rng[0];
  #128;pdm_data={4{expected_bit}};
 end
 always @(posedge pdm_clocks[0]) if(rst_n)begin
  clock_edges=clock_edges+1;
  check(compute.u_core.core.acquisition.pdm_sync === {4{expected_bit}},"PDM valid window/sample phase");
  // 环形历史避免每个PDM位都搬动190个元素；FIR参考计算不变。
  history_head=history_head==0?189:history_head-1;
  history[history_head]=expected_bit?1:-1;bit_count=bit_count+1;
  if(bit_count%64==0)begin
   sum=0;for(j=0;j<190;j=j+1)sum=sum+history[(history_head+j)%190]*weights[j];
   reference_pcm=sum*32;
   if(reference_pcm>8388607)reference_pcm=8388607;
   if(reference_pcm< -8388608)reference_pcm=-8388608;
   #0.01;
   for(j=0;j<4;j=j+1)check($signed(compute.u_core.core.acquisition.pcm[j*24+:24])===reference_pcm,"independent CIC FIR reference");
   pcm_checks=pcm_checks+4;
  end
  #5;pdm_data=4'bzzzz;
 end
 always @(posedge clk) if(rst_n)begin
  cycles=cycles+1;
  if(cycles%250000==0)$display("PDM_PROGRESS cycles=%0d pcm_checks=%0d frames=%0d",cycles,pcm_checks,frames);
  if(servo_pwm)$fatal(1,"PDM_FAIL unbound actuator output");
  if(feature_valid && feature_ready)begin
   frames=frames+1;
  end
 end
 always @(posedge core_clk)if(rst_n)begin
  core_cycles=core_cycles+1;
  if(compute.u_core.core.begin_valid && compute.u_core.core.begin_ready)frame_start_cycle=core_cycles;
  if(compute.u_core.core_valid && compute.u_core.core_ready)begin
   check(core_cycles-frame_start_cycle<655360,"original calculation cycle budget at 100MHz");
   if(core_cycles-frame_start_cycle>max_service)max_service=core_cycles-frame_start_cycle;
  end
 end
 task ticks(input integer n);repeat(n)@(negedge clk);endtask
 task transfer(input reg[7:0] header,input reg[31:0] data,output reg[31:0] result);
  reg[39:0] packet;integer b;
  packet={header,data};result=0;spi_cs_n=0;#1000;
  for(b=0;b<40;b=b+1)begin
   spi_mosi=packet[39-b];#500;spi_sck=1;
   if(b>=8)result={result[30:0],spi_miso};
   #500;spi_sck=0;
  end
  #1000;spi_cs_n=1;#1000;
 endtask
 reg[31:0] got,word0,words[0:4],first_words[0:4];
 reg[7:0] addresses[0:4];integer fd,f,p,w,before_edges;
 initial begin
  addresses[0]='h0c;addresses[1]='h10;addresses[2]='h20;addresses[3]='h24;addresses[4]='h28;
  ticks(20);rst_n=1;ticks(20);
  transfer(0,0,got);check(got==32'h5a5a2026,"MAGIC");
  transfer(8'h84,9,got);
  fd=$fopen("pdm_six_pairs.txt","w");
  for(f=1;f<=2;f=f+1)begin
   wait(irq);check(fault_status==0,"no fault before acquire");
   transfer(8'hb8,1,got);transfer(8'h08,0,got);check(got==f,"frame sequence");
   transfer(8'h34,0,got);check(got[0] && got[4] && !got[3] && !got[5] && got[13:8]==63,"all six real terminal pairs");
   for(p=0;p<6;p=p+1)begin
    transfer(8'h9c,p,got);
    for(w=0;w<5;w=w+1)transfer(addresses[w],0,words[w]);
    check(words[0][10:8]==p && words[0][7:0]==0,"pair echo and zero lag");
    check(words[0][31:24]==8'h11 && words[0][15:11]==5'b00111,"stages and validity");
    check($signed(words[1])>0 && $signed(words[1])>=$signed(words[4]),"autocorrelation peak");
    for(w=0;w<5;w=w+1)begin
     if(p==0)first_words[w]=words[w];
     else check(w==0?(words[w]&32'hfffff8ff)==first_words[w]:words[w]==first_words[w],"six identical channel pairs");
    end
    $fdisplay(fd,"frame=%0d pair=%0d %08x %08x %08x %08x %08x",f,p,words[0],words[1],words[2],words[3],words[4]);
   end
   transfer(8'hb8,4,got);check(fault_status==0,"no source or FIFO fault");
  end
  transfer(8'h84,8,got);wait(!draining);before_edges=clock_edges;ticks(100);
  check(clock_edges>before_edges,"physical PDM clock continues while stopped");
  check(!run_enable && !servo_pwm,"stop closes new work and output");
  $fclose(fd);
  $display("PDM_PASS frames=%0d checks=%0d pcm_checks=%0d max_service=%0d cycles=%0d pin_input=1 official_fft_ifft=1 compute_hz=100000000 acquire_hz=61440000",frames,checks,pcm_checks,max_service,cycles);$finish;
 end
 initial begin #80000000;$fatal(1,"PDM_FAIL timeout");end
endmodule
