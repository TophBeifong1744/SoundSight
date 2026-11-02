// MIGRATION_MODULE_GUIDE
// 分组：06 六对特征
// 用途：薄封装官方 ss_ifft25，方向与缩放配置来自六对引擎。
// 接口要点：24 位 config、64 位数据打包、10 位输出索引、独立 status/events。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
// Managed AMD xfft9.1 revision15 only; runtime config is supplied by the backend.
module ifft25_official (
    input wire clk,cold_rst_n,
    input wire [23:0] config_data, input wire config_valid, output wire config_ready,
    input wire [63:0] input_data, input wire input_valid,input_last,
    output wire input_ready,
    output wire [63:0] output_data, output wire [9:0] output_index,
    output wire output_valid,output_last, input wire output_ready,
    output wire [7:0] status_data, output wire status_valid,input wire status_ready,
    output wire unexpected_last,missing_last,overflow,
    output wire frame_started,status_halt,input_halt,output_halt
);
    wire [23:0] output_user;
    ss_ifft25 core (
        .aclk(clk),.aresetn(cold_rst_n),
        .s_axis_config_tdata(config_data),.s_axis_config_tvalid(config_valid),
        .s_axis_config_tready(config_ready),
        .s_axis_data_tdata(input_data),.s_axis_data_tvalid(input_valid),
        .s_axis_data_tready(input_ready),.s_axis_data_tlast(input_last),
        .m_axis_data_tdata(output_data),.m_axis_data_tuser(output_user),
        .m_axis_data_tvalid(output_valid),.m_axis_data_tready(output_ready),
        .m_axis_data_tlast(output_last),
        .m_axis_status_tdata(status_data),.m_axis_status_tvalid(status_valid),
        .m_axis_status_tready(status_ready),
        .event_frame_started(frame_started),.event_tlast_unexpected(unexpected_last),
        .event_tlast_missing(missing_last),.event_fft_overflow(overflow),
        .event_status_channel_halt(status_halt),.event_data_in_channel_halt(input_halt),
        .event_data_out_channel_halt(output_halt)
    );
    assign output_index=output_user[9:0];
endmodule
