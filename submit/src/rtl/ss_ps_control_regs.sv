// MIGRATION_MODULE_GUIDE
// 分组：PS实验版
// 用途：PS版寄存器层；与SPI版相同公开字段，增加host_stop保留快照的停用入口。
// 接口要点：host_stop来自同步总线复位；冷rst_n才清队列。普通PS复位清使能、角度影子和看门狗，不能自动恢复动作。
// 当前PL+PS主方案入口；历史STM32冻结接口独立保留。
`timescale 1ns/1ps
`default_nettype none
// 独立寄存器/快照/动作控制层。commit一拍只执行一次副作用；read_data按address组合读取。
// SPI与后续PS AXI前端只转换总线，不各自复制一套冻结寄存器语义。
module ss_ps_control_regs #(
    parameter integer ACTUATOR_BOUND=0,LEVEL_ENABLE=0,AUDIO_ENABLE=0,DUAL_AXIS_ENABLE=0, CLK_FREQ_HZ=61440000,
    parameter integer SERVO_MAX=180, MECHANICAL_MIN=0, MECHANICAL_MAX=180
)(
    input wire clk, rst_n, host_stop,
    input wire [((AUDIO_ENABLE || DUAL_AXIS_ENABLE) ? 8 : 7)-1:0] address,
    input wire commit,write_access,format_error,input wire [31:0] write_data,
    output reg [31:0] read_data,
    output wire irq,servo_pwm,servo_vertical_pwm,
    input wire [128:0] feature_meta,
 input wire feature_valid,
    output wire feature_ready,
    input wire [959:0] feature_pairs,
    input wire [31:0] feature_flags,
    input wire [31:0] feature_level,input wire feature_level_valid,
    input wire compute_draining,
    input wire [11:0] source_faults,
    output wire run_enable,
    output reg stop_pulse,
    output wire [31:0] fault_status,
    output wire motion_permit,
    output wire counter_exhausted
);
    reg [3:0] sys_ctrl;
    reg [2:0] pair_select;
    reg bist_select,stop_latched;
    reg [19:0] actuator_shadow;
    reg [31:0] watchdog_ticks;
    reg [11:0] faults;
    reg register_error;
    reg [2:0] snap_command;
    reg act_write;
    reg [3:0] act_control;
    reg bist_trigger;
    // PS-only calibration extension. SPI/frozen frame fields are unchanged.
    reg [8:0] manual_angle,manual_min,manual_max;
    reg manual_limits_valid;
    wire manual_active,manual_draining,manual_pwm,manual_rejected,manual_expired;
    wire sound_pwm,legacy_motion_permit;
    wire dual_active,dual_manual,dual_follow,dual_pwm_h,dual_draining;
    wire dual_rejected,dual_expired,dual_register_error,dual_known,dual_writable;
    wire [31:0] dual_read_data;
    wire manual_write=commit && write_access && address=='h74;
    wire manual_stop=host_stop || (commit && write_access &&
        ((address=='h04 && !write_data[0]) ||
         (address=='h58 && (write_data==0 || write_data[1] || write_data[2]))));
    wire bist_valid;
    wire [959:0] bist_pairs;
    ss_bist_source bist_source(.clk(clk),.rst_n(rst_n),.trigger(bist_trigger),
        .select_pass(bist_select),.valid(bist_valid),.pairs(bist_pairs));
    wire locked,queued,occupied,gap;
    wire [959:0] locked_pairs;
    wire [31:0] locked_flags,locked_energy,locked_sequence,drop_count;
    wire energy_valid,snapshot_error,overflow_pulse,counter_error;
    // BIST 只在空闲启用时发出，真实排空帧永远有优先权；碰撞还会报源协议错。
    assign feature_ready=1'b1;
    wire [128:0] locked_meta;
    wire queue_replace_enable;
    ss_snapshot_queue #(.META_ENABLE(AUDIO_ENABLE),.LATEST_WINS(AUDIO_ENABLE)) queue(
        .replace_enable(queue_replace_enable),
        .frame_meta(feature_valid ? feature_meta : 129'b0),.locked_meta(locked_meta),.clk(clk),.rst_n(rst_n),.frame_valid(feature_valid || bist_valid),
        .frame_pairs(feature_valid ? feature_pairs : bist_pairs),
        .frame_flags(feature_valid ? feature_flags : 32'h18),
        .frame_energy(feature_valid ? (LEVEL_ENABLE ? feature_level : 32'b0) : 32'd100000),
        .frame_energy_valid(feature_valid ? (LEVEL_ENABLE && feature_level_valid) : 1'b1),
        .command(snap_command),.locked(locked),.queued(queued),.occupied(occupied),
        .locked_pairs(locked_pairs),.locked_flags(locked_flags),.locked_energy(locked_energy),
        .locked_sequence(locked_sequence),.locked_energy_valid(energy_valid),
        .gap(gap),.exhausted(counter_exhausted),.drop_count(drop_count),
        .snapshot_error(snapshot_error),.overflow_pulse(overflow_pulse),.counter_error(counter_error));
    wire actuator_bound,accepted,rejected,watchdog_expired,unbound_error,pwm_draining;
    reg [5:0] raw_mask;
    reg source_qualified;
    reg [11:0] frame_errors;
    reg [31:0] fw;
    integer i,qualified_count;
    always @* begin
        raw_mask=0;qualified_count=0;
        for(i=0;i<6;i=i+1) begin
            fw=locked_pairs[i*160+:32];raw_mask[i]=fw[11];
            if(fw[11] && fw[13] && !fw[15] && !fw[14] && fw[31:24]==8'h11 && fw[22:16]>=12)
                qualified_count=qualified_count+1;
        end
        // LS/几何/数值判定保留在 S1；这里只核对已锁原始帧的硬件资格。
        source_qualified=locked && locked_flags[4] && !locked_flags[3] &&
            !locked_flags[20] && locked_flags[31:24]==0 && qualified_count>=3;
        frame_errors=0;
        if(feature_valid) begin
            if(!feature_flags[4]) frame_errors[11]=1;
            if(feature_flags[20]) frame_errors[6]=1;
            if(feature_flags[31:24]!=0) frame_errors[4]=1;
            for(i=0;i<6;i=i+1) begin
                fw=feature_pairs[i*160+:32];
                if(fw[31:28]==0 || fw[27:24]==0) frame_errors[11]=1;
                if(fw[31:28]>6 || fw[27:24]>6 || fw[10:8]!=i || fw[23]) frame_errors[4]=1;
                if(fw[31:28]==4 || fw[27:24]==4) frame_errors[4]=1;
                if(fw[15] || fw[31:28]==3 || fw[27:24]==3) frame_errors[5]=1;
            end
        end
    end
    ss_actuator_control #(.ACTUATOR_BOUND(ACTUATOR_BOUND),.CLK_FREQ_HZ(CLK_FREQ_HZ),
        .SERVO_MAX(SERVO_MAX),.MECHANICAL_MIN(MECHANICAL_MIN),.MECHANICAL_MAX(MECHANICAL_MAX)) actuator (
        .clk(clk),.rst_n(rst_n),.enabled(sys_ctrl[0] && !stop_latched && !host_stop && !dual_active && !dual_draining),.bist(sys_ctrl[1]),
        .fault(|faults || |source_faults || |frame_errors || format_error || overflow_pulse || snapshot_error || register_error),
        .control_write(act_write),.control(act_control),.shadow(actuator_shadow),.watchdog_ticks(watchdog_ticks),
        .locked(locked),.result_qualified(source_qualified),.frame_id(locked_sequence),.permit(legacy_motion_permit),
        .configured(actuator_bound),.pwm(sound_pwm),.accepted(accepted),.rejected(rejected),
        .watchdog_expired(watchdog_expired),.unbound_error(unbound_error),.draining(pwm_draining));
    ss_manual_servo #(.ACTUATOR_BOUND(ACTUATOR_BOUND),.CLK_FREQ_HZ(CLK_FREQ_HZ),
        .SERVO_MAX(SERVO_MAX),.MECHANICAL_MIN(MECHANICAL_MIN),.MECHANICAL_MAX(MECHANICAL_MAX)) manual(
        .clk(clk),.rst_n(rst_n),.idle_allowed(!sys_ctrl[0] && !sys_ctrl[1] &&
            !compute_draining && !pwm_draining && !occupied && !motion_permit && !dual_active && !dual_draining),
        .fault(|faults || |source_faults || |frame_errors || format_error ||
            overflow_pulse || snapshot_error || register_error),.stop(manual_stop),
        .command_write(manual_write),.command(write_data),.angle(manual_angle),
        .limit_min(manual_min),.limit_max(manual_max),.limits_valid(manual_limits_valid),
        .active(manual_active),.pwm(manual_pwm),.draining(manual_draining),
        .rejected(manual_rejected),.watchdog_expired(manual_expired));
    // Sources cannot overlap: manual ARM requires sound idle; SYS enable is
    // rejected while manual is active OR its final high pulse is draining.
    // 双轴与旧水平通路互斥；旧安全退出也撤销新通路，不改变快照所有权。
    assign motion_permit=legacy_motion_permit || dual_follow;
    assign servo_pwm=sound_pwm | manual_pwm | dual_pwm_h;
    generate if(DUAL_AXIS_ENABLE) begin : with_dual_axis
    ss_dual_axis_control #(.ENABLE(ACTUATOR_BOUND),.CLK_FREQ_HZ(CLK_FREQ_HZ)) dual_axis(
        .clk(clk),.rst_n(rst_n),.host_stop(host_stop),.stop(manual_stop || stop_latched),
        .fault(|faults || |source_faults || |frame_errors || format_error || overflow_pulse || snapshot_error || register_error),
        .manual_idle(!sys_ctrl[0] && !sys_ctrl[1] && !compute_draining && !occupied),
        .follow_allowed(run_enable),.others_busy(legacy_motion_permit || manual_active || pwm_draining || manual_draining),
        .locked(locked),.source_qualified(source_qualified && qualified_count>=4),.frame_id(locked_sequence),
        .access(commit),.write_access(write_access),.address({{(DUAL_AXIS_ENABLE || AUDIO_ENABLE ? 0 : 1){1'b0}},address}),.write_data(write_data),
        .read_data(dual_read_data),.known_address(dual_known),.writable(dual_writable),
        .active(dual_active),.manual_active(dual_manual),.follow_active(dual_follow),
        .pwm_h(dual_pwm_h),.pwm_v(servo_vertical_pwm),.draining(dual_draining),
        .rejected(dual_rejected),.watchdog_expired(dual_expired),.register_error(dual_register_error));
    end else begin : without_dual_axis
        // 旧二维工程不引入新模块依赖，接口仍明确给出安全常量。
        assign dual_active=0,dual_manual=0,dual_follow=0,dual_pwm_h=0,servo_vertical_pwm=0,dual_draining=0;
        assign dual_rejected=0,dual_expired=0,dual_register_error=0,dual_known=0,dual_writable=0;
        assign dual_read_data=32'hdeadbeef;
    end endgenerate
    assign run_enable=sys_ctrl[0] && !sys_ctrl[1] && !stop_latched && !counter_exhausted && !host_stop;
    assign fault_status={20'b0,faults};
    assign irq=occupied || |faults;
    wire draining=compute_draining || pwm_draining || manual_draining || dual_draining;
    reg [31:0] status_word;
    reg known_address,writable;
    always @* begin
        status_word=(locked_flags & 32'hff100018) | {18'b0,raw_mask,8'b0};
        status_word[0]=locked;status_word[1]=queued;status_word[2]=gap;
        status_word[5]=energy_valid;status_word[7]=motion_permit;
        status_word[14]=irq;status_word[15]=draining;status_word[16]=sys_ctrl[3];
        status_word[19]=actuator_bound;status_word[17]=(LEVEL_ENABLE!=0);
        status_word[18]=1'b1; // PS manual extension present; check bound bit19 too.
        known_address=1;writable=0;
        case(address)
            'h80: begin read_data=AUDIO_ENABLE ? 32'h00010001 : 0;known_address=AUDIO_ENABLE;end
            'h84: begin read_data=locked_meta[127:96];known_address=AUDIO_ENABLE;end
            'h88: begin read_data=locked_meta[63:32];known_address=AUDIO_ENABLE;end
            'h8c: begin read_data=locked_meta[95:64];known_address=AUDIO_ENABLE;end
            'h90: begin read_data=locked_meta[31:0];known_address=AUDIO_ENABLE;end
            'h94: begin read_data={15'b0,locked_meta[128],16'd1024};known_address=AUDIO_ENABLE;end
            'h98: begin read_data=AUDIO_ENABLE ? 32'h4c415431 : 0;known_address=AUDIO_ENABLE;end // LAT1
            'h00: read_data=32'h5a5a2026;
            'h04: begin read_data={28'b0,sys_ctrl};writable=1;end
            'h08: read_data=locked_sequence;
            'h0c: read_data=locked_pairs[pair_select*160+:32];
            'h10: read_data=locked_pairs[pair_select*160+32+:32];
            'h14: read_data=locked_energy;
            'h18: begin read_data={12'b0,actuator_shadow};writable=1;end
            'h1c: begin read_data={29'b0,pair_select};writable=1;end
            'h20: read_data=locked_pairs[pair_select*160+64+:32];
            'h24: read_data=locked_pairs[pair_select*160+96+:32];
            'h28: read_data=locked_pairs[pair_select*160+128+:32];
            'h2c: begin read_data={31'b0,bist_select};writable=1;end
            'h34: read_data=status_word;
            'h38: begin read_data=0;writable=1;end
            'h58: begin read_data={31'b0,motion_permit};writable=1;end
            'h60: begin read_data=watchdog_ticks;writable=1;end
            'h64: begin read_data=fault_status;writable=1;end
            'h68: read_data=drop_count;
            'h6c: read_data=LEVEL_ENABLE ? 32'h00010001 : 32'h00010000;
            'h70: read_data=32'h4d534301; // Manual Servo Calibration v1 capability.
            'h74: begin read_data={30'b0,manual_draining,manual_active};writable=1;end
            'h78: begin read_data={23'b0,manual_angle};writable=1;end
            'h7c: begin read_data={7'b0,manual_max,7'b0,manual_min};writable=1;end
            default: begin read_data=dual_read_data;known_address=dual_known;writable=dual_writable;end
        endcase
    end
    reg [11:0] fault_events,clear_mask;
    reg register_access_error;
    // LR-001：与顺序写入共用同一组字段校验，非法访问到达拍就禁止READY淘汰。
    always @* begin
        register_access_error=!known_address || (write_access && !writable);
        if(known_address && write_access && writable) case(address)
            'h04: register_access_error=(write_data & ~32'hb)!=0 || !write_data[3] ||
                ((write_data[1]!=sys_ctrl[1]) && (sys_ctrl[0] || manual_active || dual_active || draining || occupied)) ||
                (write_data[0] && !sys_ctrl[0] && (manual_active || dual_manual || draining || counter_exhausted ||
                    (write_data[1] && occupied)));
            'h18: register_access_error=(write_data & 32'hfff00000)!=0 || write_data[19];
            'h1c: register_access_error=write_data>5;
            'h2c: register_access_error=write_data>1 || sys_ctrl[0] || draining || occupied;
            'h38: register_access_error=(write_data & ~32'h7)!=0;
            'h58: register_access_error=(write_data & ~32'hf)!=0;
            'h60: register_access_error=motion_permit;
            'h64: register_access_error=(write_data & ~32'hfff)!=0;
            'h74: register_access_error=write_data>2;
            'h78: register_access_error=(write_data & ~32'h1ff)!=0;
            'h7c: register_access_error=manual_active || manual_draining || (write_data & ~32'h01ff01ff)!=0 ||
                write_data[8:0]>write_data[24:16] || write_data[8:0]<MECHANICAL_MIN ||
                write_data[24:16]>MECHANICAL_MAX;
            default: begin end // 双轴扩展自身的字段校验由dual_register_error同拍提供。
        endcase
    end
    // snap_command比本层事务晚一拍；预测已有待执行命令后的锁，保留紧邻合法ACQUIRE/RELEASE。
    wire lock_after_pending_snap=(snap_command==1) ? (locked || queued) :
        ((snap_command==2 || snap_command==4) ? 1'b0 : locked);
    wire snapshot_access_error=write_access && address=='h38 &&
        ((write_data!=0 && write_data!=1 && write_data!=2 && write_data!=4) ||
         ((write_data==2 || write_data==4) && !lock_after_pending_snap));
    wire queue_access_error=commit && (register_access_error || snapshot_access_error ||
        (write_access && dual_known && address=='ha4 && write_data>4));
    always @* begin
        fault_events=source_faults | frame_errors;
        fault_events[0]=fault_events[0] | format_error;
        fault_events[1]=fault_events[1] | register_error | dual_register_error;
        fault_events[2]=fault_events[2] | snapshot_error;
        fault_events[3]=fault_events[3] | overflow_pulse;
        fault_events[4]=fault_events[4] | (feature_valid && bist_valid);
        fault_events[6]=fault_events[6] | stop_pulse | host_stop | (manual_write && write_data==0);
        fault_events[7]=fault_events[7] | rejected | manual_rejected | dual_rejected;
        fault_events[8]=fault_events[8] | watchdog_expired | manual_expired | dual_expired;
        fault_events[9]=fault_events[9] | counter_error;
        fault_events[10]=fault_events[10] | unbound_error;
        clear_mask=0;
        if(commit && write_access && address=='h64 && (write_data & 32'hfffff000)==0 && !sys_ctrl[0] && !manual_active && !dual_active) begin
            clear_mask=write_data[11:0] & ~source_faults;
            if(draining) clear_mask[6]=0;
            if(counter_exhausted) clear_mask[9]=0;
        end
    end
    // 仅正常真实采集可淘汰READY。STOP同拍、现有/新故障及取消尾帧都先保住旧记录。
    // fault_events来自本拍源标志/停止/错误，不等faults下一拍置位才关替换。
    assign queue_replace_enable=AUDIO_ENABLE && run_enable && feature_valid && !bist_valid && !feature_flags[3] &&
        !compute_draining && !manual_stop && !stop_pulse && !queue_access_error && !(|faults) && !(|fault_events);
    always @(posedge clk) begin
        if(!rst_n) begin
            sys_ctrl<=8;pair_select<=0;bist_select<=0;stop_latched<=0;
            actuator_shadow<=0;watchdog_ticks<=0;faults<=0;
            register_error<=0;snap_command<=0;act_write<=0;act_control<=0;
            bist_trigger<=0;stop_pulse<=0;
            manual_angle<=0;manual_min<=0;manual_max<=0;manual_limits_valid<=0;
        end else begin
            faults<=(faults & ~clear_mask) | fault_events;
            register_error<=0;snap_command<=0;act_write<=0;bist_trigger<=0;stop_pulse<=0;
            if(host_stop) begin
                // PS总线复位撤销控制，保留已发布快照。恢复必须重新配置/使能，旧角度不重放。
                sys_ctrl[0]<=0;stop_latched<=0;actuator_shadow<=0;watchdog_ticks<=0;
                stop_pulse<=sys_ctrl[0];
                manual_angle<=0;manual_limits_valid<=0;
            end else if(commit) begin
                if(register_access_error) register_error<=1;
                else if(write_access) case(address)
                    'h04: begin
                        sys_ctrl<=write_data[3:0];
                        if(!write_data[0]) begin
                            stop_latched<=0;
                            if(sys_ctrl[0]) stop_pulse<=1;
                        end
                        if(write_data[0] && !sys_ctrl[0] && write_data[1]) bist_trigger<=1;
                    end
                    'h18: actuator_shadow<=write_data[19:0];
                    'h1c: pair_select<=write_data[2:0];
                    'h2c: bist_select<=write_data[0];
                    'h38: snap_command<=write_data[2:0]; // 非单一命令仍由原队列报snapshot_error。
                    'h58: begin
                        act_write<=1;act_control<=write_data[3:0];
                        if(write_data[1]) begin stop_pulse<=1;stop_latched<=1;end
                    end
                    'h60: watchdog_ticks<=write_data;
                    'h64: begin end // 清错在clear_mask中执行。
                    'h74: begin end // 命令由manual controller处理。
                    'h78: manual_angle<=write_data[8:0];
                    'h7c: begin manual_min<=write_data[8:0];manual_max<=write_data[24:16];manual_limits_valid<=1;end
                    default: if(!dual_known) register_error<=1; // 新扩展自己的原子控制器处理其写入。
                endcase
            end
        end
    end
endmodule
`default_nettype wire
