// MIGRATION_MODULE_GUIDE
// 分组：08 动作保护
// 用途：撤销许可时阻止新高脉冲；已有高脉冲完整结束；冷复位立即低。
// 接口要点：raw_pwm/permit/revoke/fresh_command→受保护 PWM、排尾和等待新命令状态。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 中文用途：独立撤销PWM门；正常撤销保留已输出高脉冲，禁止新脉冲，复位例外立即低。
module i17_turntable_pwm_guard (
    input wire clk, rst_n,
    input wire raw_pwm_i,
    input wire permit_i,
    input wire output_revoke_i,
    input wire fresh_command_i,
    output reg pwm_o,
    output reg open_o,
    output reg draining_o,
    output reg awaiting_command_o
);
    reg raw_q;
    reg pending_q;
    reg skipped_rise_q;
    wire raw_rise = raw_pwm_i && !raw_q;
    wire revoke = !permit_i || output_revoke_i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            raw_q <= 0; pending_q <= 0; skipped_rise_q <= 0;
            pwm_o <= 0; open_o <= 0; draining_o <= 0; awaiting_command_o <= 1;
        end else begin
            raw_q <= raw_pwm_i;
            // 物理端已高才可排尾；raw已高但物理端未高不构成已启动脉冲。
            if (revoke) begin
                pending_q <= 0; skipped_rise_q <= 0; open_o <= 0;
                awaiting_command_o <= 1;
                if (pwm_o && raw_pwm_i) begin
                    pwm_o <= 1; draining_o <= 1;
                end else begin
                    pwm_o <= 0; draining_o <= 0;
                end
            end else if (draining_o) begin
                pwm_o <= pwm_o && raw_pwm_i;
                if (!raw_pwm_i) draining_o <= 0;
                // 排尾期间不接受重开；调用方必须在排尾结束后提交新有效命令。
            end else if (open_o) begin
                pwm_o <= raw_pwm_i;
            end else begin
                pwm_o <= 0;
                // 中文用途：首个新命令建立边界等待；同授权代后续命令不重启，避免高频更新饿死开门。
                if (fresh_command_i && !pending_q) begin
                    pending_q <= 1; skipped_rise_q <= 0; awaiting_command_o <= 0;
                end else if (pending_q && raw_rise) begin
                    if (!skipped_rise_q) skipped_rise_q <= 1;
                    else begin
                        pwm_o <= 1; open_o <= 1; pending_q <= 0;
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
