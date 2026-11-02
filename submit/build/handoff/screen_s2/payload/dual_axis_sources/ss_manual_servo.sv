// PS-only manual calibration. No audio frame, BIST result or snapshot is used.
// Explicit ARM + COMMIT, hardware bounds and fixed 750ms lease protect PWM.
`timescale 1ns/1ps
`default_nettype none
module ss_manual_servo #(
    parameter integer ACTUATOR_BOUND=0, CLK_FREQ_HZ=61440000,
    parameter integer SERVO_MAX=360, MECHANICAL_MIN=0, MECHANICAL_MAX=360
)(
    input wire clk, rst_n, idle_allowed, fault, stop,
    input wire command_write,
    input wire [31:0] command,
    input wire [8:0] angle, limit_min, limit_max,
    input wire limits_valid,
    output reg active, rejected, watchdog_expired,
    output wire pwm, draining
);
    localparam integer LEASE_TICKS=(CLK_FREQ_HZ/4)*3;
    localparam CONFIG_OK=ACTUATOR_BOUND && CLK_FREQ_HZ>=4 && SERVO_MAX>=1 &&
        SERVO_MAX<=511 && MECHANICAL_MIN>=0 && MECHANICAL_MIN<=MECHANICAL_MAX &&
        MECHANICAL_MAX<=SERVO_MAX;
    reg [31:0] remaining;
    wire bounds_ok=limits_valid && limit_min<=limit_max &&
        limit_min>=MECHANICAL_MIN && limit_max<=MECHANICAL_MAX;
    wire revoke=stop || fault || !idle_allowed || !CONFIG_OK ||
        (command_write && command==0);
    wire expired=active && remaining<=1;
    wire accept_now=command_write && command==2 && active && !revoke && !expired &&
        !draining && bounds_ok && angle>=limit_min && angle<=limit_max;
    wire arm_now=command_write && command==1 && !active && !revoke && !draining && bounds_ok;
    always @(posedge clk) begin
        if(!rst_n) begin active<=0;remaining<=0;rejected<=0;watchdog_expired<=0;end
        else begin
            rejected<=0;watchdog_expired<=0;
            if(revoke) begin active<=0;remaining<=0;end
            else if(expired) begin active<=0;remaining<=0;watchdog_expired<=1;end
            else if(arm_now || accept_now) begin active<=1;remaining<=LEASE_TICKS;end
            else if(active) remaining<=remaining-1'b1;
            // STOP wins over a simultaneous command; malformed commands never
            // refresh the lease. A live ARM cannot be abused as a heartbeat.
            if(command_write && command!=0 && !stop &&
               !((command==1 && arm_now) || (command==2 && accept_now))) rejected<=1;
        end
    end
    wire raw_pwm;
    motor_drive #(.CLK_FREQ_HZ(CLK_FREQ_HZ),.MAX_ANGLE_DEG(SERVO_MAX),.RESET_ANGLE_DEG(0)) motor(
        .clk(clk),.rst_n(rst_n),.angle_deg_i(angle),.angle_valid_i(accept_now),.pwm_o(raw_pwm));
    i17_turntable_pwm_guard guard(.clk(clk),.rst_n(rst_n),.raw_pwm_i(raw_pwm),
        .permit_i(active),.output_revoke_i(revoke || expired),.fresh_command_i(accept_now),
        .pwm_o(pwm),.open_o(),.draining_o(draining),.awaiting_command_o());
endmodule
`default_nettype wire
