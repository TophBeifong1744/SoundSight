`timescale 1ns/1ps
`default_nettype none
// PS专用双轴扩展。配置先写影子再原子应用，目标一字提交，两轴共用租约。
// 手动不依赖声音；跟随只接受当前真实合格锁帧。普通总线复位保留已用帧号。
module ss_dual_axis_control #(
    parameter integer ENABLE=0, CLK_FREQ_HZ=61440000
)(
    input wire clk, rst_n, host_stop, stop, fault,
    input wire manual_idle, follow_allowed, others_busy,
    input wire locked, source_qualified,
    input wire [31:0] frame_id,
    input wire access, write_access,
    input wire [7:0] address,
    input wire [31:0] write_data,
    output reg [31:0] read_data,
    output reg known_address, writable,
    output wire active, manual_active, follow_active,
    output wire pwm_h, pwm_v, draining,
    output reg rejected, watchdog_expired,
    output wire register_error
);
    localparam integer LEASE_TICKS=(CLK_FREQ_HZ/4)*3;
    localparam CONFIG_OK=ENABLE && CLK_FREQ_HZ>=1000000;
    reg [1:0] mode; // 0关闭，1无声手动，2真实帧跟随。
    reg have_command,config_valid;
    reg [31:0] angle_shadow, sequence_shadow;
    reg [31:0] h_limits_shadow,v_limits_shadow;
    reg [1:0] axes_shadow,axes;
    reg [2:0] config_dirty;
    reg angle_dirty,sequence_dirty;
    reg [8:0] h_min,h_max,v_min,v_max;
    reg [31:0] accepted_angles, last_frame, remaining;
    wire drain_h,drain_v;
    assign active=(mode!=0);
    assign manual_active=(mode==1);
    assign follow_active=(mode==2);
    assign draining=drain_h || drain_v;

    wire command=access && write_access && address==8'ha4 && ENABLE;
    wire revoke_command=command && write_data==0;
    wire apply_command=command && write_data==4;
    wire arm_manual=command && write_data==1;
    wire arm_follow=command && write_data==2;
    wire commit_command=command && write_data==3;
    wire config_idle=!active && !draining && !others_busy;
    wire limits_ok=(h_limits_shadow & 32'hfe00fe00)==0 &&
        (v_limits_shadow & 32'hfe00fe00)==0 &&
        h_limits_shadow[8:0]<=h_limits_shadow[24:16] && h_limits_shadow[24:16]<=360 &&
        v_limits_shadow[8:0]<=v_limits_shadow[24:16] && v_limits_shadow[24:16]<=220;
    wire apply_ok=config_idle && config_dirty==3'b111 && axes_shadow!=0 && limits_ok;
    // 关闭的轴不要求有效角度，且绝不输出PWM；开启的轴拒绝越界而非饱和。
    wire angles_ok=angle_dirty && (angle_shadow & 32'hfe00fe00)==0 &&
        (!axes[0] || (angle_shadow[8:0]>=h_min && angle_shadow[8:0]<=h_max)) &&
        (!axes[1] || (angle_shadow[24:16]>=v_min && angle_shadow[24:16]<=v_max));
    wire frame_ok=locked && source_qualified && frame_id!=0 &&
        sequence_dirty && sequence_shadow==frame_id && frame_id!=last_frame;
    wire expired=active && remaining<=1;
    wire environment_bad=host_stop || stop || fault || !CONFIG_OK ||
        (manual_active && !manual_idle) || (follow_active && !follow_allowed);
    wire arm_ok=config_idle && config_valid && !environment_bad &&
        ((arm_manual && manual_idle) || (arm_follow && follow_allowed));
    wire commit_ok=active && !environment_bad && !expired && !draining &&
        !others_busy && angles_ok && (manual_active || frame_ok);
    wire bad_command=command && !revoke_command &&
        !((arm_manual || arm_follow) && arm_ok) &&
        !(commit_command && commit_ok) && !(apply_command && apply_ok);

    reg bad_access;
    always @* begin
        read_data=32'hdeadbeef;known_address=ENABLE!=0;writable=0;
        case(address)
            8'ha0:read_data=CONFIG_OK ? 32'h44554101 : 0;
            8'ha4:begin read_data=0;writable=1;end
            8'ha8:read_data={22'b0,(config_valid ? axes : 2'b0),3'b0,
                            drain_v,drain_h,have_command,follow_active,active};
            8'hac:begin read_data=angle_shadow;writable=1;end
            8'hb0:begin read_data=h_limits_shadow;writable=1;end
            8'hb4:begin read_data=v_limits_shadow;writable=1;end
            8'hb8:begin read_data={30'b0,axes_shadow};writable=1;end
            8'hbc:begin read_data=sequence_shadow;writable=1;end
            8'hc0:read_data=accepted_angles;
            8'hc4:read_data=last_frame;
            8'hc8:read_data=remaining;
            8'hcc:read_data={7'b0,h_max,7'b0,h_min};
            8'hd0:read_data={7'b0,v_max,7'b0,v_min};
            default:known_address=0;
        endcase
        bad_access=0;
        if(access && write_access && known_address) begin
            if(!writable)bad_access=1;
            case(address)
                8'hac:bad_access=(write_data & 32'hfe00fe00)!=0;
                8'hb0,8'hb4:bad_access=!config_idle || (write_data & 32'hfe00fe00)!=0;
                8'hb8:bad_access=!config_idle || (write_data & ~32'h3)!=0;
                default:begin end
            endcase
        end
    end
    assign register_error=bad_access;
    wire revoke=environment_bad || revoke_command || bad_access || bad_command;
    wire accept_now=commit_command && commit_ok && !bad_access;
    always @(posedge clk) begin
        if(!rst_n) begin
            mode<=0;have_command<=0;config_valid<=0;remaining<=0;
            angle_shadow<=0;sequence_shadow<=0;angle_dirty<=0;sequence_dirty<=0;
            h_limits_shadow<=0;v_limits_shadow<=0;axes_shadow<=0;config_dirty<=0;
            axes<=0;h_min<=0;h_max<=0;v_min<=0;v_max<=0;
            accepted_angles<=0;last_frame<=0;rejected<=0;watchdog_expired<=0;
        end else begin
            rejected<=0;watchdog_expired<=0;
            if(host_stop) begin
                // 不清last_frame：PS复位后不能重放仍锁着的旧跟随帧。
                mode<=0;have_command<=0;config_valid<=0;remaining<=0;
                angle_shadow<=0;sequence_shadow<=0;angle_dirty<=0;sequence_dirty<=0;
                h_limits_shadow<=0;v_limits_shadow<=0;axes_shadow<=0;config_dirty<=0;
                axes<=0;h_min<=0;h_max<=0;v_min<=0;v_max<=0;accepted_angles<=0;
            end else begin
                if(revoke)begin mode<=0;have_command<=0;remaining<=0;angle_dirty<=0;sequence_dirty<=0;end
                else if(expired)begin
                    mode<=0;have_command<=0;remaining<=0;angle_dirty<=0;sequence_dirty<=0;
                    watchdog_expired<=1;
                end else if((arm_manual || arm_follow) && arm_ok)begin
                    mode<=arm_manual ? 1 : 2;remaining<=LEASE_TICKS;have_command<=0;
                    angle_dirty<=0;sequence_dirty<=0;
                end else if(accept_now)begin
                    accepted_angles<=angle_shadow;remaining<=LEASE_TICKS;have_command<=1;
                    angle_dirty<=0;sequence_dirty<=0;
                    if(follow_active)last_frame<=frame_id;
                end else if(active)remaining<=remaining-1'b1;
                // STOP优先；与STOP同拍的COMMIT既不接受也不产生额外拒绝故障。
                // DA-001：到期事件独立于命令拒绝。截止拍COMMIT不能把超时bit8盖成bit7。
                // 显式STOP/撤许可和环境故障优先；到期前一拍的合法COMMIT仍可续约。
                if(expired && !environment_bad && !revoke_command)watchdog_expired<=1;
                if(bad_command && !host_stop && !stop && !expired)rejected<=1;
                if(apply_command && apply_ok && !environment_bad)begin
                    h_min<=h_limits_shadow[8:0];h_max<=h_limits_shadow[24:16];
                    v_min<=v_limits_shadow[8:0];v_max<=v_limits_shadow[24:16];
                    axes<=axes_shadow;config_valid<=1;config_dirty<=0;
                end
                if(access && write_access && known_address && !bad_access && !environment_bad && !expired)begin
                    case(address)
                        8'hac:begin angle_shadow<=write_data;angle_dirty<=1;end
                        8'hb0:begin h_limits_shadow<=write_data;config_dirty[0]<=1;end
                        8'hb4:begin v_limits_shadow<=write_data;config_dirty[1]<=1;end
                        8'hb8:begin axes_shadow<=write_data[1:0];config_dirty[2]<=1;end
                        8'hbc:begin sequence_shadow<=write_data;sequence_dirty<=1;end
                        default:begin end
                    endcase
                end
            end
        end
    end
    wire raw_h,raw_v;
    // 两路使用同域、同复位的20ms计数器；同一COMMIT进入同一周期边界。
    motor_drive #(.CLK_FREQ_HZ(CLK_FREQ_HZ),.MAX_ANGLE_DEG(360),.RESET_ANGLE_DEG(0)) horizontal(
        .clk(clk),.rst_n(rst_n),.angle_deg_i(angle_shadow[8:0]),.angle_valid_i(accept_now && axes[0]),.pwm_o(raw_h));
    motor_drive #(.CLK_FREQ_HZ(CLK_FREQ_HZ),.MAX_ANGLE_DEG(220),.RESET_ANGLE_DEG(0)) vertical(
        .clk(clk),.rst_n(rst_n),.angle_deg_i(angle_shadow[24:16]),.angle_valid_i(accept_now && axes[1]),.pwm_o(raw_v));
    i17_turntable_pwm_guard h_guard(.clk(clk),.rst_n(rst_n),.raw_pwm_i(raw_h),
        .permit_i(active && axes[0]),.output_revoke_i(revoke || expired),.fresh_command_i(accept_now && axes[0]),
        .pwm_o(pwm_h),.open_o(),.draining_o(drain_h),.awaiting_command_o());
    i17_turntable_pwm_guard v_guard(.clk(clk),.rst_n(rst_n),.raw_pwm_i(raw_v),
        .permit_i(active && axes[1]),.output_revoke_i(revoke || expired),.fresh_command_i(accept_now && axes[1]),
        .pwm_o(pwm_v),.open_o(),.draining_o(drain_v),.awaiting_command_o());
endmodule
`default_nettype wire
