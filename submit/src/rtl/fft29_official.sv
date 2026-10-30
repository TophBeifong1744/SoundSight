// MIGRATION_MODULE_GUIDE
// 分组：05 前向 FFT 与定点转换
// 用途：薄封装官方 ss_fft29，不实现另一套 FFT 数学模型。
// 接口要点：config/data/out/status 独立握手；29 位实虚部；配置字固定 0x0AAAAB。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
// The only FFT implementation is the managed AMD xfft 9.1 revision 15 core.
// Configuration/packing are fixed by FF-1.0; no arithmetic model here.
module fft29_official (
    input wire clk, cold_rst_n,
    input wire config_valid, output wire config_ready,
    input wire data_valid, output wire data_ready,
    input wire signed [28:0] data_real, data_imag, input wire data_last,
    output wire out_valid, input wire out_ready,
    output wire signed [28:0] out_real, out_imag,
    output wire [9:0] out_index, output wire out_last,
    output wire status_valid, input wire status_ready,
    output wire [7:0] status_raw, output wire [6:0] events
);
    wire [63:0] output_data;
    wire [23:0] output_user;
    ss_fft29 core (
        .aclk(clk), .aresetn(cold_rst_n),
        .s_axis_config_tdata(24'h0aaaab),
        .s_axis_config_tvalid(config_valid), .s_axis_config_tready(config_ready),
        .s_axis_data_tdata({3'b0, data_imag, 3'b0, data_real}),
        .s_axis_data_tvalid(data_valid), .s_axis_data_tready(data_ready),
        .s_axis_data_tlast(data_last),
        .m_axis_data_tdata(output_data), .m_axis_data_tuser(output_user),
        .m_axis_data_tvalid(out_valid), .m_axis_data_tready(out_ready),
        .m_axis_data_tlast(out_last),
        .m_axis_status_tdata(status_raw),
        .m_axis_status_tvalid(status_valid), .m_axis_status_tready(status_ready),
        .event_frame_started(events[0]),
        .event_tlast_unexpected(events[1]), .event_tlast_missing(events[2]),
        .event_status_channel_halt(events[3]),
        .event_data_in_channel_halt(events[4]),
        .event_data_out_channel_halt(events[5]), .event_fft_overflow(events[6])
    );
    assign out_real = output_data[28:0];
    assign out_imag = output_data[60:32];
    assign out_index = output_user[9:0];
endmodule
