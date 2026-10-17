`timescale 1ns/1ps
// 使用本次Vivado实际生成的Clocking Wizard和Processor System Reset模型。
// FCLK由测试平台驱动；不声称仿真了PS启动/DDR。
module tb_platform;
 reg fclk=0,running=1,ps_reset_n=1,cold_reset_n=0;
 always #5 if(running)fclk=~fclk;else fclk=0;
 wire mid_clk,core_clk,io_clk,main_locked,audio_locked;
 wire core_rst_n,io_rst_n,bus_rst_n,bus_io_rst_n;
 wire core_ip_rst_n,io_ip_rst_n;
 soundsight_ps_bd_clk_main_0 main_clock(.clk_in1(fclk),.resetn(cold_reset_n),.clk_out1(mid_clk),.clk_out2(core_clk),.locked(main_locked));
 soundsight_ps_bd_clk_audio_0 audio_clock(.clk_in1(mid_clk),.resetn(main_locked),.clk_out1(io_clk),.locked(audio_locked));
 soundsight_ps_bd_core_reset_0 core_reset(.slowest_sync_clk(core_clk),.dcm_locked(audio_locked),.ext_reset_in(cold_reset_n),.aux_reset_in(1'b1),.mb_debug_sys_rst(1'b0),.peripheral_aresetn(core_ip_rst_n),.mb_reset(),.bus_struct_reset(),.peripheral_reset(),.interconnect_aresetn());
 soundsight_ps_bd_io_reset_0 io_reset(.slowest_sync_clk(io_clk),.dcm_locked(audio_locked),.ext_reset_in(cold_reset_n),.aux_reset_in(1'b1),.mb_debug_sys_rst(1'b0),.peripheral_aresetn(io_ip_rst_n),.mb_reset(),.bus_struct_reset(),.peripheral_reset(),.interconnect_aresetn());
 soundsight_ps_bd_core_release_0 core_release(.dest_clk(core_clk),.src_arst(core_ip_rst_n && audio_locked),.dest_arst(core_rst_n));
 soundsight_ps_bd_io_release_0 io_release(.dest_clk(io_clk),.src_arst(io_ip_rst_n && audio_locked),.dest_arst(io_rst_n));
 realtime core_edge=0,io_edge=0;
 always @(posedge core_clk)core_edge=$realtime;
 always @(posedge io_clk)io_edge=$realtime;
 always @(posedge core_rst_n)if($realtime>1 && $realtime-core_edge>0.001)$fatal(1,"PLATFORM_FAIL core reset released off edge");
 always @(posedge io_rst_n)if($realtime>1 && $realtime-io_edge>0.001)$fatal(1,"PLATFORM_FAIL io reset released off edge");
 soundsight_ps_bd_bus_reset_0 bus_reset(.slowest_sync_clk(core_clk),.dcm_locked(audio_locked),.ext_reset_in(ps_reset_n),.aux_reset_in(1'b1),.mb_debug_sys_rst(1'b0),.peripheral_aresetn(bus_rst_n),.mb_reset(),.bus_struct_reset(),.peripheral_reset(),.interconnect_aresetn());
 soundsight_ps_bd_bus_io_reset_0 bus_io_reset(.slowest_sync_clk(io_clk),.dcm_locked(audio_locked),.ext_reset_in(ps_reset_n),.aux_reset_in(1'b1),.mb_debug_sys_rst(1'b0),.peripheral_aresetn(bus_io_rst_n),.mb_reset(),.bus_struct_reset(),.peripheral_reset(),.interconnect_aresetn());
 reg save=0;reg [31:0] retained=0;
 always @(posedge io_clk)if(!io_rst_n)retained<=0;else if(save)retained<=32'h12345678;
 integer checks=0;real start_time,core_period,io_period;
 task check(input bit ok,input string msg);checks++;if(!ok)$fatal(1,"PLATFORM_FAIL %s",msg);endtask
 initial begin
  #200;cold_reset_n=1;
  wait(core_rst_n && io_rst_n && bus_rst_n && bus_io_rst_n);
  check(main_locked && audio_locked,"release requires both locks");
  @(posedge core_clk);start_time=$realtime;repeat(1000)@(posedge core_clk);core_period=($realtime-start_time)/1000;
  @(posedge io_clk);start_time=$realtime;repeat(1000)@(posedge io_clk);io_period=($realtime-start_time)/1000;
  check(core_period>9.998 && core_period<10.002,"100MHz actual period");
  check(io_period>16.274 && io_period<16.278,"61.44MHz actual period");
  @(negedge io_clk);save=1;repeat(3)@(negedge io_clk);save=0;
  ps_reset_n=0;#5000;
  check(!bus_rst_n && !bus_io_rst_n,"PS reset asserted in both bus domains");
  check(core_rst_n && io_rst_n && retained==32'h12345678,"PS bus reset preserves cold domain record");
  ps_reset_n=1;wait(bus_rst_n && bus_io_rst_n);#100;
  check(retained==32'h12345678,"record retained after bus reset release");
  // 关FCLK模拟平台时钟丢失；随后恢复必须经过重新锁定及冷复位。
  @(negedge fclk);running=0;#10000;
  check(!main_locked && !audio_locked,"clock loss detected");
  check(!core_rst_n && !io_rst_n,"both cold resets assert even with stopped clocks");
  // 官方MMCM模型明确要求输入时钟恢复时复位。此动作代表PS显式冷恢复，非自动保帧。
  cold_reset_n=0;running=1;#500;cold_reset_n=1;
  wait(main_locked && audio_locked);wait(core_rst_n && io_rst_n);repeat(4)@(negedge io_clk);
  check(retained==0,"cold restart invalidates old record");
  $display("PLATFORM_PASS checks=%0d core_period_ns=%0.6f io_period_ns=%0.6f ps_reset_preserves=1 restart_clears=1",checks,core_period,io_period);$finish;
 end
 initial begin #200000;$fatal(1,"PLATFORM_FAIL timeout");end
endmodule
