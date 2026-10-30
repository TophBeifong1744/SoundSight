// MIGRATION_MODULE_GUIDE
// 分组：01 时钟与总接合
// 用途：复用两级官方 MMCM 和 BUFG：50→96→61.44 MHz。
// 接口要点：sys_clk 输入；clk50/clk_pcm 与各自同步释放的复位输出。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// Official 7-series primitives; 50 -> 96 -> 61.44 MHz.
module sound_servo_clock(input wire sys_clk, output wire clk50, clk_pcm,
 output wire rst50_n, rst_pcm_n);
 wire in_clk, fb1, fb1b, out1, clk96, lock1;
 wire fb2, fb2b, out2, lock2;
 IBUF u_ibuf(.I(sys_clk), .O(in_clk));
 BUFG u_50(.I(in_clk), .O(clk50));
 MMCME2_BASE #(.CLKIN1_PERIOD(20.0), .DIVCLK_DIVIDE(1),
  .CLKFBOUT_MULT_F(24.0), .CLKOUT0_DIVIDE_F(12.5), .STARTUP_WAIT("FALSE"))
 u_m1(.CLKIN1(clk50), .CLKFBIN(fb1b), .CLKFBOUT(fb1), .CLKOUT0(out1),
  .LOCKED(lock1), .PWRDWN(1'b0), .RST(1'b0));
 BUFG u_fb1(.I(fb1), .O(fb1b));
 BUFG u_96(.I(out1), .O(clk96));
 MMCME2_BASE #(.CLKIN1_PERIOD(10.416666667), .DIVCLK_DIVIDE(1),
  .CLKFBOUT_MULT_F(8.0), .CLKOUT0_DIVIDE_F(12.5), .STARTUP_WAIT("FALSE"))
 u_m2(.CLKIN1(clk96), .CLKFBIN(fb2b), .CLKFBOUT(fb2), .CLKOUT0(out2),
  .LOCKED(lock2), .PWRDWN(1'b0), .RST(!lock1));
 BUFG u_fb2(.I(fb2), .O(fb2b));
 BUFG u_pcm(.I(out2), .O(clk_pcm));
 wire locks = lock1 && lock2;
 (* ASYNC_REG="TRUE" *) logic [2:0] r50, rp;
 always_ff @(posedge clk50 or negedge locks)
  if (!locks) r50 <= 0; else r50 <= {r50[1:0],1'b1};
 always_ff @(posedge clk_pcm or negedge locks)
  if (!locks) rp <= 0; else rp <= {rp[1:0],1'b1};
 assign rst50_n = r50[2];
 assign rst_pcm_n = rp[2];
endmodule
`default_nettype wire
