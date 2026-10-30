`timescale 1ns/1ps
// 实际BD包装/AXI/快照/双轴路径。1MHz参数保留真实20ms周期和750ms租约。
module tb_dualaxis;
 reg clk=0;always #500 clk=~clk;
 reg rst_n=0,aresetn=0,feature_valid=0,compute_draining=0;
 reg [959:0] feature_pairs=0;reg [31:0] feature_flags=32'h10;
 reg [31:0] feature_level=12000;reg feature_level_valid=1;
 reg [11:0] source_faults=0;
 wire feature_ready,run_enable,irq,servo_pwm,servo_vertical_pwm;wire [31:0] fault_status;
 `include "axi_tasks.svh"
 bd_ps_link #(.DUAL_AXIS_ENABLE(1),.AUDIO_ENABLE(1),.LEVEL_ENABLE(1),.ACTUATOR_BOUND(1),
   .CLK_FREQ_HZ(1000000),.SERVO_MAX(360),.MECHANICAL_MAX(360)) dut(.feature_meta(129'b0),.*);
 reg [31:0] value,sequence_id;integer h_width,v_width,wait_count;
 task reset_all;
   rst_n=0;aresetn=0;feature_valid=0;source_faults=0;compute_draining=0;
   repeat(5)tick();rst_n=1;aresetn=1;repeat(5)tick();
 endtask
 task configure(input integer mask,input integer hmin,input integer hmax,input integer vmin,input integer vmax);
   put('hb0,(hmax<<16)|hmin);put('hb4,(vmax<<16)|vmin);put('hb8,mask);put('ha4,4);
   expect_read('hcc,(hmax<<16)|hmin);expect_read('hd0,(vmax<<16)|vmin);
 endtask
 task target(input integer h,input integer v);put('hac,(v<<16)|h);put('ha4,3);endtask
 task quiet(input integer cycles);
   repeat(cycles)begin tick();check(!servo_pwm && !servo_vertical_pwm,"both outputs low");end
 endtask
 task wait_rise;
   wait_count=0;
   while(!servo_pwm && !servo_vertical_pwm && wait_count<45000)begin tick();wait_count++;end
   check(wait_count<45000,"command produces PWM within two periods");
 endtask
 task measure_pair(input integer h_us,input integer v_us,input bit stop_mid);
   wait_rise();check(servo_pwm && servo_vertical_pwm,"both axes start at same boundary");
   h_width=0;v_width=0;
   fork
     begin while(servo_pwm)begin h_width++;tick();end end
     begin while(servo_vertical_pwm)begin v_width++;tick();end end
     begin if(stop_mid)begin repeat(200)tick();put('ha4,0);end end
   join
   check(h_width==h_us,$sformatf("H pulse %0d expected %0d",h_width,h_us));
   check(v_width==v_us,$sformatf("V pulse %0d expected %0d",v_width,v_us));
 endtask
 task publish(input integer qualified,input bit real_source);
   tick();feature_flags=real_source ? 32'h10 : 32'h18;
   for(integer p=0;p<6;p++) feature_pairs[p*160+:160]=
     {32'd100,32'd800,32'd800,32'd1000,(p<qualified ? 32'h11202800 : 32'h11200000)|(32'(p)<<8)};
   feature_valid=1;tick();feature_valid=0;repeat(4)tick();put('h38,1);rd('h08,sequence_id,0);
 endtask
 task follow_target(input integer h,input integer v,input reg[31:0] seq);
   put('hac,(v<<16)|h);put('hbc,seq);put('ha4,3);
 endtask
 // 独立端口实例只检查同拍STOP+COMMIT及32位序号边界，主功能仍通过上方真实AXI。
 reg direct_reset=0,d_stop=0,d_access=0;reg [7:0] d_addr=0;reg [31:0] d_data=0;
 reg [31:0] d_frame=32'h80000001;wire d_active,d_h,d_v,d_expired,d_rejected;wire [31:0] d_read;
 ss_dual_axis_control #(.ENABLE(1),.CLK_FREQ_HZ(1000000)) simultaneous(
   .clk(clk),.rst_n(direct_reset),.host_stop(1'b0),.stop(d_stop),.fault(1'b0),
   .manual_idle(1'b1),.follow_allowed(1'b1),.others_busy(1'b0),.locked(1'b1),
   .source_qualified(1'b1),.frame_id(d_frame),.access(d_access),.write_access(1'b1),
   .address(d_addr),.write_data(d_data),.read_data(d_read),.known_address(),.writable(),
   .active(d_active),.manual_active(),.follow_active(),.pwm_h(d_h),.pwm_v(d_v),
   .draining(),.rejected(d_rejected),.watchdog_expired(d_expired),.register_error());
 task direct_write(input reg[7:0] a,input reg[31:0] d);
   tick();d_addr=a;d_data=d;d_access=1;tick();d_access=0;tick();
 endtask
 task deadline_setup;
   direct_reset=0;d_stop=0;d_access=0;repeat(2)tick();direct_reset=1;
   direct_write('hb0,360<<16);direct_write('hb4,220<<16);direct_write('hb8,3);
   direct_write('ha4,4);direct_write('ha4,1);direct_write('hac,(110<<16)|180);
   d_addr='hc8;#1;
 endtask
 task commit_at_remaining(input integer remaining_ticks,input bit stop_together);
   while(d_read>remaining_ticks)tick();
   check(d_read==remaining_ticks,"public lease counter reaches requested boundary");
   d_stop=stop_together;d_addr='ha4;d_data=3;d_access=1;tick();d_access=0;
 endtask
 initial begin
   reset_all();expect_read('ha0,32'h44554101);expect_read('h80,32'h10001);
   quiet(21000);expect_read('ha8,0);
   put('hb0,360<<16);expect_read('hcc,0);put('hb4,220<<16);expect_read('hd0,0);
   put('hb8,3);put('ha4,4);expect_read('ha8,32'h300);
   put('hac,(110<<16)|180);put('ha4,1);quiet(21000);put('ha4,3);
   rd('h64,value,0);check(value[7],"pre-ARM target cannot replay");quiet(100);
   reset_all();put('hb0,360<<16);put('hb4,220<<16);put('ha4,4);
   expect_read('hcc,0);expect_read('hd0,0);rd('h64,value,0);
   check(value[7],"incomplete config cannot apply only one axis");
   reset_all();configure(3,20,340,10,210);put('ha4,1);target(90,165);expect_read('h64,0);
   measure_pair(1000,2000,1);quiet(21000);expect_read('ha8,32'h300);
   // 未改任何已接受角度；一轴越界必须整组拒绝。
   put('ha4,1);target(180,211);expect_read('hc0,(165<<16)|90);
   rd('h64,value,0);check(value[7],"one invalid axis rejects entire target");quiet(21000);
   reset_all();configure(3,0,360,0,220);put('ha4,1);target(0,220);
   measure_pair(500,2500,0);target(360,0);measure_pair(2500,500,0);
   put('ha4,0);quiet(21000);put('ha4,1);put('ha4,3);
   rd('h64,value,0);check(value[7],"REVOKE then ARM requires fresh target");
   // 单轴mask：关闭轴的角度可无意义，但该轴必须保持低。
   reset_all();configure(1,0,360,0,220);put('ha4,1);target(180,511);wait_rise();
   check(servo_pwm && !servo_vertical_pwm,"H-only mask");
   repeat(22000)begin tick();check(!servo_vertical_pwm,"V disabled remains low");end
   put('ha4,0);repeat(3000)tick();configure(2,0,360,0,220);put('ha4,1);target(511,110);wait_rise();
   check(!servo_pwm && servo_vertical_pwm,"V-only mask");
   repeat(22000)begin tick();check(!servo_pwm,"H disabled remains low");end
   put('hb8,3);rd('h64,value,0);check(value[1],"live config write rejected");repeat(3000)tick();quiet(21000);
   reset_all();configure(3,0,360,0,220);put('ha4,1);target(180,110);
   repeat(3)begin repeat(300000)tick();target(180,110);rd('ha8,value,0);check(value[0],"fresh manual target renews lease");end
   repeat(755000)tick();rd('h64,value,0);check(value[8],"750ms lease expiration");quiet(21000);
   // 手动拒绝采集；采集时也不能进入手动，但允许停用状态配置后进入FOLLOW。
   reset_all();configure(3,0,360,0,220);put('ha4,1);put('h04,9);
   rd('h64,value,0);check(value[1] && !run_enable,"manual/capture mutual exclusion");
   reset_all();configure(3,0,360,0,220);compute_draining=1;put('ha4,1);
   rd('h64,value,0);check(value[7],"manual waits for compute drain");
   reset_all();configure(3,0,360,0,220);publish(6,1);put('ha4,1);
   rd('h64,value,0);check(value[7],"manual rejects occupied snapshot");
   reset_all();put('h04,9);configure(3,0,360,0,220);put('ha4,1);
   rd('h64,value,0);check(value[7],"manual rejected while acquisition active");
   reset_all();put('h04,9);configure(3,0,360,0,220);publish(4,1);put('ha4,2);
   follow_target(180,110,sequence_id);expect_read('h64,0);expect_read('hc4,sequence_id);
   measure_pair(1500,1500,1);put('ha4,2);follow_target(90,55,sequence_id);
   rd('h64,value,0);check(value[7],"same locked sequence cannot replay across REVOKE/ARM");
   // 普通总线复位保留锁帧与用过的序号。恢复后同帧仍不可重放。
   reset_all();put('h04,9);configure(3,0,360,0,220);publish(6,1);put('ha4,2);
   follow_target(180,110,sequence_id);aresetn=0;repeat(8)tick();aresetn=1;repeat(8)tick();
   expect_read('h08,sequence_id);expect_read('hc4,sequence_id);expect_read('ha8,0);
   put('h64,32'h40);put('h04,9);configure(3,0,360,0,220);put('ha4,2);
   follow_target(180,110,sequence_id);rd('h64,value,0);check(value[7],"bus reset does not permit replay");
   // 新的真实锁帧才可再次接受；BC必须匹配全部32位而非低16位。
   reset_all();put('h04,9);configure(3,0,360,0,220);publish(6,1);put('ha4,2);
   follow_target(180,110,sequence_id);put('h38,4);publish(6,1);
   follow_target(90,55,sequence_id);expect_read('h64,0);expect_read('hc4,2);expect_read('hc0,(55<<16)|90);
   follow_target(180,110,32'h10002);rd('h64,value,0);check(value[7],"full32 sequence match required");
   reset_all();put('h04,9);configure(3,0,360,0,220);publish(3,1);put('ha4,2);
   follow_target(180,110,sequence_id);rd('h64,value,0);check(value[7],"3D requires at least four qualified pairs");
   reset_all();put('h04,9);configure(3,0,360,0,220);publish(6,0);put('ha4,2);
   follow_target(180,110,sequence_id);rd('h64,value,0);check(value[7],"BIST cannot authorize 3D motion");
   // 原有ACT的0、STOP、REVOKE和SYS关闭都覆盖双轴安全退出。
   for(integer kind=0;kind<4;kind++)begin
     reset_all();configure(3,0,360,0,220);put('ha4,1);target(180,110);wait_rise();
     if(kind==3)put('h04,8);else put('h58,kind==0 ? 0 : (kind==1 ? 2 : 4));
     repeat(3000)tick();rd('ha8,value,0);check(!value[0],"legacy exit revokes dual axis");quiet(21000);
   end
   reset_all();configure(3,0,360,0,220);put('ha4,1);target(90,165);wait_rise();
   h_width=0;v_width=0;
   fork
     begin while(servo_pwm)begin h_width++;tick();end end
     begin while(servo_vertical_pwm)begin v_width++;tick();end end
     begin repeat(200)tick();aresetn=0;end
   join
   check(h_width==1000 && v_width==2000,"bus reset drains both independent pulse widths");
   aresetn=1;repeat(8)tick();expect_read('ha8,0);quiet(21000);
   // 输入故障与提交同拍：不能接受目标；源故障仍由公共FAULT保留。
   reset_all();configure(3,0,360,0,220);put('ha4,1);put('hac,(110<<16)|180);
   fork
     begin put('ha4,3);end
     begin wait(dut.u_core.commit && dut.u_core.address=='ha4);source_faults=1;end
   join
   expect_read('hc0,0);quiet(21000);rd('h64,value,0);check(value[0],"fault wins commit");
   direct_reset=1;direct_write('hb0,360<<16);direct_write('hb4,220<<16);
   direct_write('hb8,3);direct_write('ha4,4);direct_write('ha4,2);
   direct_write('hac,(110<<16)|180);direct_write('hbc,32'h80000001);
   d_stop=1;direct_write('ha4,3);d_stop=0;check(!d_active,"same-cycle STOP wins COMMIT");
   d_addr='hc4;#1;check(d_read==0,"STOP never records an accepted sequence");
   direct_write('ha4,2);direct_write('hac,(110<<16)|180);direct_write('hbc,32'h80000001);direct_write('ha4,3);
   d_addr='hc4;#1;check(d_read==32'h80000001,"full unsigned high-bit sequence accepted");
   // DA-001独立边界预期：到期前一拍接受，到期拍超时，之后保持撤销；STOP优先。
   deadline_setup();commit_at_remaining(2,0);d_addr='hc8;#1;
   check(d_active && d_read==750000 && !d_expired && !d_rejected,"pre-deadline commit renews lease");
   deadline_setup();commit_at_remaining(1,0);d_addr='hc0;#1;
   check(!d_active && d_expired && !d_rejected && d_read==0,"deadline COMMIT records timeout not rejection");
   deadline_setup();while(d_read!=0)tick();check(d_expired && !d_active,"lease expiry without command");
   direct_write('ha4,3);d_addr='hc0;#1;
   check(!d_active && d_read==0,"post-deadline COMMIT cannot restart or accept target");
   deadline_setup();commit_at_remaining(1,1);d_addr='hc0;#1;
   check(!d_active && !d_expired && !d_rejected && d_read==0,"STOP wins deadline and COMMIT");
   // DA-002：复位刺激必须发生在两个真实输出都已高时。
   reset_all();configure(3,0,360,0,220);put('ha4,1);target(180,110);wait_rise();
   check(servo_pwm && servo_vertical_pwm,"both outputs high immediately before cold reset");
   rst_n=0;direct_reset=0;#1;check(!servo_pwm && !servo_vertical_pwm && !d_h && !d_v,"cold reset immediate low");
   $display("DUALAXIS_PASS checks=%0d AXI=1 manual_no_audio=1 follow_4pairs=1 atomic=1 masks=1 pulse_tail=1 lease=1 replay=1 bus_reset_retains=1 STOP_wins=1",checks);
   $finish;
 end
 initial begin #8000000000.0;$fatal(1,"DUALAXIS_FAIL timeout");end
endmodule
