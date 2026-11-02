// MIGRATION_MODULE_GUIDE
// 分组：08 动作保护
// 用途：检查独立许可、当前锁帧、新鲜度、角度范围和看门狗后接受一次动作。
// 接口要点：影子角度/COMMIT、锁帧序号、资格、故障；permit/PWM/拒绝/超时。ACTUATOR_BOUND 默认 0。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// SPI 影子命令到真实 PWM 的唯一许可点。软件负责 S1 数学合格；硬件复核
// 当前锁帧/原始资格/序号/轴/范围/故障/看门狗。接受同一帧只能一次。
module ss_actuator_control #(
    parameter integer ACTUATOR_BOUND=0, CLK_FREQ_HZ=61440000,
    parameter integer SERVO_MAX=180, MECHANICAL_MIN=0, MECHANICAL_MAX=180
)(
    input wire clk, rst_n, enabled, bist, fault,
    input wire control_write,
    input wire [3:0] control,
    input wire [19:0] shadow,
    input wire [31:0] watchdog_ticks,
    input wire locked, result_qualified,
    input wire [31:0] frame_id,
    output reg permit,
    output wire configured, pwm,
    output reg accepted, rejected, watchdog_expired, unbound_error,
    output wire draining
);
    localparam CONFIG_OK=ACTUATOR_BOUND && SERVO_MAX>=1 && SERVO_MAX<=511 &&
        MECHANICAL_MIN>=0 && MECHANICAL_MIN<=MECHANICAL_MAX && MECHANICAL_MAX<=SERVO_MAX;
    assign configured=CONFIG_OK;
    reg [31:0] remaining, last_frame;
    reg have_command;
    wire revoke=(!enabled || bist || fault || !CONFIG_OK || watchdog_ticks==0 ||
                 (control_write && (control==0 || control[1] || control[2])));
    wire expired=permit && have_command && remaining<=1;
    wire legal_command=permit && !revoke && !expired && locked && result_qualified &&
                      frame_id!=0 && frame_id!=last_frame && shadow[18] && !shadow[19] &&
                      shadow[8:0]>=MECHANICAL_MIN && shadow[8:0]<=MECHANICAL_MAX && !draining;
    wire accept_now=control_write && control[3] && legal_command;
    always @(posedge clk) begin
        if(!rst_n) begin
            permit<=0;remaining<=0;last_frame<=0;have_command<=0;
            accepted<=0;rejected<=0;watchdog_expired<=0;unbound_error<=0;
        end else begin
            accepted<=0;rejected<=0;watchdog_expired<=0;unbound_error<=0;
            if(revoke) begin permit<=0;remaining<=0;have_command<=0;end
            else if(expired) begin permit<=0;have_command<=0;remaining<=0;watchdog_expired<=1;end
            else begin
                if(permit && have_command) remaining<=remaining-1'b1;
                if(control_write && control[0]) permit<=1;
                if(accept_now) begin
                    accepted<=1;last_frame<=frame_id;remaining<=watchdog_ticks;have_command<=1;
                end
            end
            // STOP/REVOKE 不执行同写 COMMIT，也不把正常撤销误报为拒绝。
            if(control_write && control!=0 && !control[1] && !control[2]) begin
                if(!CONFIG_OK && (control[0] || control[3])) unbound_error<=1;
                if((control[3] && !legal_command) || (control[0] && revoke)) rejected<=1;
            end
        end
    end
    wire raw_pwm;
    motor_drive #(.CLK_FREQ_HZ(CLK_FREQ_HZ),.MAX_ANGLE_DEG(SERVO_MAX),.RESET_ANGLE_DEG(0)) motor (
        .clk(clk),.rst_n(rst_n),.angle_deg_i(shadow[8:0]),.angle_valid_i(accept_now),.pwm_o(raw_pwm));
    // 最后一拍也阻止新脉冲；已经输出的完整高脉冲由原 guard 排尾。
    i17_turntable_pwm_guard guard (
        .clk(clk),.rst_n(rst_n),.raw_pwm_i(raw_pwm),.permit_i(permit),
        .output_revoke_i(revoke || expired),.fresh_command_i(accept_now),
        .pwm_o(pwm),.open_o(),.draining_o(draining),.awaiting_command_o());
endmodule
`default_nettype wire
