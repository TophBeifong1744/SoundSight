// MIGRATION_MODULE_GUIDE
// 分组：05 六对特征
// 用途：按01、02、03、12、13、23串行做跨谱、PHAT、IFFT、整数峰和邻点提取；没有PL内LS或角度解算。
// 接口要点：begin/s/end 使用32位帧号；S25实虚部及channel/bin顺序检查。取消保留已完成对并终结其余对。feature_pairs 每对160位、共960位。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
`default_nettype none
// 六对数值引擎：唯一在途帧，32位真实帧号；没有票据、cookie或宽身份包。
// 正常数据依次为4通道×513个半谱点；取消仍等前端/已启动IFFT排空。
module ss_pair_engine #(parameter integer LEVEL_ENABLE=0) (
 input wire clk,rst_n,
 input wire begin_valid,output wire begin_ready,input wire [31:0] begin_frame,
 input wire s_valid,output wire s_ready,input wire [31:0] s_frame,
 input wire [1:0] s_channel,input wire [9:0] s_bin,
 input wire signed [24:0] s_real,s_imag,input wire s_numeric_valid,
 input wire end_valid,output wire end_ready,input wire [31:0] end_frame,
 input wire end_cancelled,input wire [7:0] end_error,
 input wire cancel,
 input wire [31:0] frame_level,input wire frame_level_valid,
 output wire [31:0] feature_level,output wire feature_level_valid,
 output wire busy,output wire ip_obligation,
 output wire feature_valid,input wire feature_ready,
 output wire [31:0] feature_frame_id,feature_frame_flags,
 output wire [959:0] feature_pairs,
 output wire feature_drop_pulse,output wire [31:0] feature_drop_count,
 output wire feature_gap,feature_counter_exhausted,feature_source_protocol_error,
 output wire [4:0] debug_state
);
 import doa_math_pkg::*;
 wire cold_rst_n=rst_n;
 localparam [4:0] IDLE=0,COLLECT=1,BARRIER=2,PAIR_BEGIN=3,CROSS=4,
 NORMALIZE=5,PHAT_FINAL=6,CONFIG=7,RUN_IP=8,IP_FINAL=9,
 LAG_SCAN=10,LAG_FINAL=11,NEXT_PAIR=12,FINISH=20,REPORT=21,LAG_MARGIN=22;
 localparam [3:0] PENDING=0,OK=1,REJECTED=2,NUMERIC=3,PROTOCOL=4,CANCELLED=5,SKIPPED=6;
 localparam [7:0] ERR_ID=1,ERR_ORDER=2,ERR_SOURCE_NUMERIC=3,ERR_FRONTEND=4,
 ERR_PHAT=5,ERR_IFFT_INDEX=6,ERR_IFFT_LAST=7,ERR_IFFT_STATUS=8,ERR_IFFT_EVENT=9;
 reg [4:0] state;
 reg [31:0] frame;
 reg [11:0] received;
 reg [9:0] expected_bin;
 reg [1:0] expected_channel;
 reg transaction_cancelled,source_bad;
 reg [7:0] first_error_code;
 wire killed=transaction_cancelled || (cancel && busy);
 reg [23:0] pair_state;
 reg [47:0] backend_stage_state;
 reg [5:0] pair_valid,pair_hardware_started,pair_physically_retired;
 reg [41:0] pair_mask_counts;
 reg [10:0] input_count,output_count;
 reg status_received;
 wire feature_accepting;
 wire [23:0] ip_config_data=24'h0AAAAA;
 wire ip_config_valid=state==CONFIG;
 wire ip_config_ready;
 reg [63:0] ip_input_data;
 wire ip_input_valid=state==RUN_IP && input_count<1024;
 wire ip_input_ready;
 wire ip_input_last=input_count==1023;
 wire [63:0] ip_output_data;
 wire [9:0] ip_output_index;
 wire ip_output_valid,ip_output_last;
 wire ip_output_ready=state==RUN_IP && output_count<1024;
 wire [7:0] ip_status_data;
 wire ip_status_valid;
 wire ip_status_ready=state==RUN_IP && !status_received;
 wire ip_event_unexpected_last,ip_event_missing_last,ip_event_overflow;
 ifft25_official inverse(.clk(clk),.cold_rst_n(rst_n),.config_data(ip_config_data),
 .config_valid(ip_config_valid),.config_ready(ip_config_ready),.input_data(ip_input_data),
 .input_valid(ip_input_valid),.input_last(ip_input_last),.input_ready(ip_input_ready),
 .output_data(ip_output_data),.output_index(ip_output_index),.output_valid(ip_output_valid),
 .output_last(ip_output_last),.output_ready(ip_output_ready),.status_data(ip_status_data),
 .status_valid(ip_status_valid),.status_ready(ip_status_ready),.unexpected_last(ip_event_unexpected_last),
 .missing_last(ip_event_missing_last),.overflow(ip_event_overflow),.frame_started(),
 .status_halt(),.input_halt(),.output_halt());
 assign begin_ready=state==IDLE && feature_accepting && begin_frame!=0;
 assign s_ready=state==COLLECT;
 assign end_ready=state==COLLECT;
 assign busy=state!=IDLE;
 assign debug_state=state;
 assign ip_obligation=state==RUN_IP;
    (* ram_style="block" *) logic [49:0] spectrum0 [0:512];
    (* ram_style="block" *) logic [49:0] spectrum1 [0:512];
    (* ram_style="block" *) logic [49:0] spectrum2 [0:512];
    (* ram_style="block" *) logic [49:0] spectrum3 [0:512];
    logic [49:0] spectrum_read [0:3];
    logic [49:0] spectrum_a,spectrum_b;
    logic cross_phase;
    logic [2:0] normal_phase;
    logic [2:0] math_phase;
    logic signed [49:0] product_arbr,product_aibi,product_aibr,product_arbi;
    logic signed [50:0] cross_re_exact,cross_im_exact;
    logic signed [101:0] cross_re_square,cross_im_square;
    // 跨谱分四级寄存：乘积、加减、平方、求和；bin/配对/复数载荷同步延迟。
    logic signed [49:0] product_arbr_q,product_aibi_q,product_aibr_q,product_arbi_q;
    logic signed [50:0] cross_re_q,cross_im_q;
    logic signed [101:0] cross_re_square_q,cross_im_square_q;
    logic signed [50:0] square_re_q,square_im_q,sum_re_q,sum_im_q;
    logic [102:0] cross_sum_q;
    logic [6:0] product_bin_q,value_bin_q,square_bin_q,sum_bin_q;
    logic [2:0] product_pair_q,value_pair_q,square_pair_q,sum_pair_q;
    logic product_valid,value_valid,square_valid,sum_valid,cross_commit;
    logic phat_start,phat_ready,phat_done,phat_busy;
    logic [51:0] phat_result;
    // 私有ALU接线不复制transaction身份或PHAT状态机。
    logic phat_alu_start,phat_alu_ready,phat_alu_done;
    logic [1:0] phat_alu_op;
    wide_t phat_alu_a,phat_alu_b,phat_alu_result;
    logic signed [31:0] phat_alu_shift;
    // 工作集精确缩减：跨谱仅7..85，lag及邻点仅-9..+9。
    (* ram_style="block" *) logic [204:0] cross_work [0:78];
    logic [204:0] cross_read;
    (* ram_style="block" *) logic [49:0] phat_half [0:78];
    logic [49:0] ip_half_data;
    logic signed [24:0] correlation [0:18];
    logic [2:0] pair_id;
    logic [9:0] k;
    logic [6:0] mask_count;
    logic [102:0] maximum_square;
    logic pair_bad,ip_pair_bad,ip_pair_numeric;


    logic signed [5:0] lag,peak_lag;
    logic signed [24:0] peak;
    logic signed [24:0] second_peak;
    logic second_valid;
    logic [114:0] mask_scaled_square;
    logic [114:0] mask_scaled_square_q;
    wide_t normal_square;
    logic [51:0] normalized;
    integer i,j,a_ch,b_ch,dx,dy,next_half_index,scan_index,left_index,right_index;

    wire raw_ok=(state==NEXT_PAIR) && pair_valid[pair_id] && !killed;
    reg [3:0] raw_phat_stage,raw_ifft_stage;
    reg [31:0] raw_word;
    reg [159:0] raw_words;
    always @* begin
        raw_phat_stage=backend_stage_state[pair_id*4+:4];
        raw_ifft_stage=backend_stage_state[(pair_id+6)*4+:4];
        if(raw_phat_stage==PENDING) raw_phat_stage=killed ? CANCELLED : SKIPPED;
        if(raw_ifft_stage==PENDING) raw_ifft_stage=killed ? CANCELLED : SKIPPED;
        raw_word=0;
        raw_word[10:8]=pair_id;
        raw_word[27:24]=raw_phat_stage;raw_word[31:28]=raw_ifft_stage;
        raw_word[14]=killed || pair_state[pair_id*4+:4]==CANCELLED;
        raw_word[15]=raw_phat_stage==NUMERIC || raw_ifft_stage==NUMERIC;
        raw_words=0;
        if(raw_ok) begin
            raw_word[7:0]={{2{peak_lag[5]}},peak_lag};
            raw_word[11]=1;raw_word[12]=second_valid;raw_word[13]=1;
            raw_word[22:16]=pair_mask_counts[pair_id*7+:7];
            raw_words[32+:32]={{7{peak[24]}},peak};
            raw_words[64+:32]={{7{correlation[left_index][24]}},correlation[left_index]};
            raw_words[96+:32]={{7{correlation[right_index][24]}},correlation[right_index]};
            raw_words[128+:32]=second_valid ? {{7{second_peak[24]}},second_peak} : 32'b0;
        end
        raw_words[0+:32]=raw_word;
    end
    f1a_frame_store #(.LEVEL_ENABLE(LEVEL_ENABLE)) feature_store(
        .clk(clk),.cold_rst_n(cold_rst_n),.frame_start(begin_valid && begin_ready),.frame_start_bist(1'b0),
        .pair_event(state==NEXT_PAIR),.pair_index(pair_id),.pair_words(raw_words),
        .frame_finish(state==REPORT),
        .frame_level(frame_level),.frame_level_valid(frame_level_valid),
        .feature_level(feature_level),.feature_level_valid(feature_level_valid),
        .frame_cancelled(killed),.first_error(first_error_code),
        .phat_stages(backend_stage_state[23:0]),.ifft_stages(backend_stage_state[47:24]),
        .accepting(feature_accepting),.feature_valid(feature_valid),.feature_ready(feature_ready),
        .feature_frame_id(feature_frame_id),.feature_frame_flags(feature_frame_flags),
        .feature_pairs(feature_pairs),.drop_pulse(feature_drop_pulse),.drop_count(feature_drop_count),
        .gap(feature_gap),.counter_exhausted(feature_counter_exhausted),
        .source_protocol_error(feature_source_protocol_error));
    assign cross_commit=rst_n && !killed && (state==CROSS || state==NORMALIZE) && sum_valid && sum_pair_q==pair_id;
    // PHAT独占一个多周期整数核；不再保留已经迁到CPU的LS算术仲裁。
    doa_math_serial arithmetic(.clk(clk),.cold_rst_n(rst_n),.cancel(killed),
      .start(phat_alu_start),.ready(phat_alu_ready),.operation(phat_alu_op),
      .operand_a(phat_alu_a),.operand_b(phat_alu_b),.shift(phat_alu_shift),
      .done(phat_alu_done),.result(phat_alu_result),.busy());
    doa_phat_client phat_math(.clk(clk),.cold_rst_n(cold_rst_n),.cancel(killed),
      .start(phat_start),.ready(phat_ready),.done(phat_done),.in_real($signed(cross_read[101:51])),
      .in_imag($signed(cross_read[50:0])),.in_square($unsigned(normal_square)),.result(phat_result),.busy(phat_busy),
      .alu_start(phat_alu_start),.alu_ready(phat_alu_ready),.alu_done(phat_alu_done),
      .alu_op(phat_alu_op),.alu_a(phat_alu_a),.alu_b(phat_alu_b),
      .alu_shift(phat_alu_shift),.alu_result(phat_alu_result));
    always_comb begin
      // CONFIG预置第0点；每次真实接受才同步读取下一点，stall不改数据。
      next_half_index=input_count<512 ? input_count+1 : 1023-input_count;
      ip_input_data=0;
      if(input_count<1024) begin
        ip_input_data[24:0]=ip_half_data[49:25];
        ip_input_data[56:32]=input_count<=512 ? ip_half_data[24:0] : -$signed(ip_half_data[24:0]);
      end
      case(pair_id)
        0:begin a_ch=0;b_ch=1;dx=1;dy=0;end
        1:begin a_ch=0;b_ch=2;dx=1;dy=1;end
        2:begin a_ch=0;b_ch=3;dx=0;dy=1;end
        3:begin a_ch=1;b_ch=2;dx=0;dy=1;end
        4:begin a_ch=1;b_ch=3;dx=-1;dy=1;end
        default:begin a_ch=2;b_ch=3;dx=-1;dy=0;end
      endcase
      spectrum_a=spectrum_read[a_ch];spectrum_b=spectrum_read[b_ch];
      // 25位输入的单乘积精确占50位，加/减精确占51位。
      product_arbr=$signed(spectrum_a[49:25])*$signed(spectrum_b[49:25]);
      product_aibi=$signed(spectrum_a[24:0])*$signed(spectrum_b[24:0]);
      product_aibr=$signed(spectrum_a[24:0])*$signed(spectrum_b[49:25]);
      product_arbi=$signed(spectrum_a[49:25])*$signed(spectrum_b[24:0]);
      cross_re_exact={product_arbr_q[49],product_arbr_q}+{product_aibi_q[49],product_aibi_q};
      cross_im_exact={product_aibr_q[49],product_aibr_q}-{product_arbi_q[49],product_arbi_q};
      cross_re_square=cross_re_q*cross_re_q;
      cross_im_square=cross_im_q*cross_im_q;
      normal_square={89'd0,cross_read[204:102]};
      normalized=phat_result;
      // correlation槽0..18对应原自然序位置1015..1023,0..9。
      scan_index=lag+9;
      left_index=peak_lag+8;
      right_index=peak_lag+10;

      mask_scaled_square={12'd0,cross_read[204:102]}*115'd2500;
      phat_start=state==NORMALIZE && normal_phase==1 && phat_ready && !killed;
    end
    // 无复位数组清零：新事务必须收满4×513个实际谱点后才读取。
    always_ff @(posedge clk) begin
      if(cold_rst_n && s_valid && s_ready && s_frame==frame && s_bin<=512) case(s_channel)
        0:spectrum0[s_bin]<={s_real,s_imag};
        1:spectrum1[s_bin]<={s_real,s_imag};
        2:spectrum2[s_bin]<={s_real,s_imag};
        3:spectrum3[s_bin]<={s_real,s_imag};
      endcase
      if(cold_rst_n && state==CROSS && !cross_phase && !killed) begin
        spectrum_read[0]<=spectrum0[k];spectrum_read[1]<=spectrum1[k];
        spectrum_read[2]<=spectrum2[k];spectrum_read[3]<=spectrum3[k];
      end
      if(cross_commit)
        cross_work[sum_bin_q]<={cross_sum_q,sum_re_q,sum_im_q};
      if(cold_rst_n && !killed && state==NORMALIZE && normal_phase==0 && k>=7 && k<=85)
        cross_read<=cross_work[k-7];
      // 全部1024点仍交付官方IP，工作集以外显式补零；取消后的真实drain继续。
      if(cold_rst_n && state==CONFIG) ip_half_data<=0;
      else if(cold_rst_n && state==RUN_IP && ip_input_valid && ip_input_ready) begin
        if(input_count<1023 && next_half_index>=7 && next_half_index<=85)
          ip_half_data<=phat_half[next_half_index-7];
        else ip_half_data<=0;
      end
    end
    // 保留原每两拍读bin；尾部提交落在NORMALIZE跳过0..6的空拍内。
    // 数据寄存器不清零，valid在冷复位/取消/事务或配对离开窗口时全部失效。
    always_ff @(posedge clk) begin
      if(!cold_rst_n || killed || (state!=CROSS && state!=NORMALIZE)) begin
        product_valid<=0;value_valid<=0;square_valid<=0;sum_valid<=0;
      end else begin
        product_valid<=state==CROSS && cross_phase;
        value_valid<=product_valid;
        square_valid<=value_valid;
        sum_valid<=square_valid;
        if(state==CROSS && cross_phase) begin
          product_arbr_q<=product_arbr;product_aibi_q<=product_aibi;
          product_aibr_q<=product_aibr;product_arbi_q<=product_arbi;
          product_bin_q<=7'(k-7);product_pair_q<=pair_id;
        end
        if(product_valid) begin
          cross_re_q<=cross_re_exact;cross_im_q<=cross_im_exact;
          value_bin_q<=product_bin_q;value_pair_q<=product_pair_q;
        end
        if(value_valid) begin
          cross_re_square_q<=cross_re_square;cross_im_square_q<=cross_im_square;
          square_re_q<=cross_re_q;square_im_q<=cross_im_q;
          square_bin_q<=value_bin_q;square_pair_q<=value_pair_q;
        end
        if(square_valid) begin
          // S102平方非负；先扩成U103再相加，不截进位、不改原精度。
          cross_sum_q<={1'b0,cross_re_square_q}+{1'b0,cross_im_square_q};
          sum_re_q<=square_re_q;sum_im_q<=square_im_q;
          sum_bin_q<=square_bin_q;sum_pair_q<=square_pair_q;
        end
      end
    end
    always_ff @(posedge clk) begin
      if(!rst_n) begin
        state<=IDLE;frame<=0;received<=0;expected_bin<=0;expected_channel<=0;
        transaction_cancelled<=0;source_bad<=0;first_error_code<=0;
        pair_state<=0;backend_stage_state<=0;pair_valid<=0;pair_mask_counts<=0;
        pair_hardware_started<=0;pair_physically_retired<=0;
        cross_phase<=0;normal_phase<=0;math_phase<=0;pair_id<=0;k<=0;
        maximum_square<=0;mask_count<=0;pair_bad<=0;ip_pair_bad<=0;ip_pair_numeric<=0;
        input_count<=0;output_count<=0;status_received<=0;
        lag<=0;peak_lag<=0;peak<=0;second_peak<=0;second_valid<=0;
      end else begin
        if(cancel && busy) transaction_cancelled<=1;
        if(cross_commit && cross_sum_q>maximum_square) maximum_square<=cross_sum_q;
        case(state)
          IDLE: if(begin_valid && begin_ready) begin
            frame<=begin_frame;received<=0;expected_bin<=0;expected_channel<=0;
            transaction_cancelled<=cancel;source_bad<=0;first_error_code<=0;
            pair_state<=0;backend_stage_state<=0;pair_valid<=0;pair_mask_counts<=0;
            pair_hardware_started<=0;pair_physically_retired<=0;pair_id<=0;
            state<=COLLECT;
          end
          COLLECT: begin
            if(s_valid && s_ready) begin
              received<=received+1'b1;
              if(s_frame!=frame || s_channel!=expected_channel || s_bin!=expected_bin || received>=2052) begin
                source_bad<=1;if(first_error_code==0)first_error_code<=s_frame!=frame?ERR_ID:ERR_ORDER;
              end else if(!s_numeric_valid) begin
                source_bad<=1;if(first_error_code==0)first_error_code<=ERR_SOURCE_NUMERIC;
              end
              if(expected_bin==512)begin expected_bin<=0;expected_channel<=expected_channel+1'b1;end
              else expected_bin<=expected_bin+1'b1;
            end
            // 前端只有真正排空已启动FFT后才发布end，普通取消不复位官方IP。
            if(end_valid && end_ready)begin
              if(end_cancelled)transaction_cancelled<=1;
              if(end_frame!=frame || end_error!=0)begin
                source_bad<=1;if(first_error_code==0)first_error_code<=end_frame!=frame?ERR_ID:ERR_FRONTEND;
              end
              state<=BARRIER;
            end
          end
          BARRIER: begin
            if(received!=2052 || source_bad || first_error_code!=0 || killed)begin
              if(received!=2052 && first_error_code==0 && !killed)first_error_code<=ERR_ORDER;
              for(j=0;j<6;j=j+1)pair_state[j*4+:4]<=killed?CANCELLED:PROTOCOL;
              pair_physically_retired<=6'h3f;state<=FINISH;
            end else state<=PAIR_BEGIN;
          end
          PAIR_BEGIN: begin
            k<=7;cross_phase<=0;normal_phase<=0;math_phase<=0;maximum_square<=0;mask_count<=0;pair_bad<=0;
            if(killed || first_error_code!=0) begin
              pair_state[pair_id*4+:4]<=killed ? CANCELLED : NUMERIC;
              backend_stage_state[pair_id*4+:4]<=killed ? CANCELLED : SKIPPED;
              backend_stage_state[(pair_id+6)*4+:4]<=killed ? CANCELLED : SKIPPED;
              pair_physically_retired[pair_id]<=1;state<=NEXT_PAIR;
            end else state<=CROSS;
          end
          CROSS: begin
            if(killed) begin pair_state[pair_id*4+:4]<=CANCELLED;pair_physically_retired[pair_id]<=1;state<=NEXT_PAIR;cross_phase<=0;end
            else if(!cross_phase) cross_phase<=1;
            else begin
              cross_phase<=0;
              if(k==85) begin k<=0;normal_phase<=0;state<=NORMALIZE;end
              else k<=k+1;
            end
          end
          NORMALIZE: begin
            if(killed) begin
                pair_state[pair_id*4+:4]<=CANCELLED;
                pair_physically_retired[pair_id]<=1;
                state<=NEXT_PAIR;normal_phase<=0;
            end
            else case(normal_phase)
              0: begin
                    if(k>=7 && k<=85) begin
                        phat_half[k-7]<=0;
                        normal_phase<=3;
                    end
                    else if(k==512) state<=PHAT_FINAL;
                    else k<=k+1;
                end
              3: begin
                // 先寄存完整乘积。
                mask_scaled_square_q <= mask_scaled_square;
                normal_phase <= 4;
              end
              4: begin
                // 下一拍使用寄存乘积做比较。
                if (normal_square > 0 &&
                    mask_scaled_square_q >= {12'd0, maximum_square}) begin
                  mask_count <= mask_count + 1;
                  normal_phase <= 1;
                end else begin
                  normal_phase <= 0;
                  k <= k + 1;
                end
              end
              1: if(phat_start) normal_phase<=2;
              2: if(phat_done) begin
                if(normalized[51] || normalized[24:0]==25'h1000000) begin
                  pair_bad<=1;if(first_error_code==0) first_error_code<=ERR_PHAT;
                end else phat_half[k-7]<=normalized[49:0];
                normal_phase<=0;
                if(k==512) state<=PHAT_FINAL;else k<=k+1;
              end
              default: normal_phase<=0;
            endcase
          end
          PHAT_FINAL: begin
            pair_mask_counts[pair_id*7+:7]<=mask_count;
            if(pair_bad || killed || mask_count<12) begin
              pair_state[pair_id*4+:4]<=killed ? CANCELLED : (pair_bad ? NUMERIC : REJECTED);
              backend_stage_state[pair_id*4+:4]<=killed ? CANCELLED : (pair_bad ? NUMERIC : REJECTED);
              backend_stage_state[(pair_id+6)*4+:4]<=killed ? CANCELLED : SKIPPED;
              pair_physically_retired[pair_id]<=1;state<=NEXT_PAIR;
            end else begin backend_stage_state[pair_id*4+:4]<=OK;state<=CONFIG;end
          end
          CONFIG: if(ip_config_valid && ip_config_ready) begin
            pair_hardware_started[pair_id]<=1;input_count<=0;output_count<=0;
            status_received<=0;ip_pair_bad<=0;ip_pair_numeric<=0;state<=RUN_IP;
          end
          RUN_IP: begin
            if(ip_input_valid && ip_input_ready) begin
              input_count<=input_count+1;
            end
            if(ip_output_valid && ip_output_ready) begin
              output_count<=output_count+1;
              if(output_count<=9) correlation[output_count+9]<=$signed(ip_output_data[24:0]);
              else if(output_count>=1015) correlation[output_count-1015]<=$signed(ip_output_data[24:0]);
              if(ip_output_index!=output_count[9:0]) begin
                ip_pair_bad<=1;if(first_error_code==0) first_error_code<=ERR_IFFT_INDEX;
              end else if(ip_output_last!=(output_count==1023)) begin
                ip_pair_bad<=1;if(first_error_code==0) first_error_code<=ERR_IFFT_LAST;
              end
            end
            if(ip_status_valid && ip_status_ready) begin
              status_received<=1;
              if(ip_status_data!=0) begin
                ip_pair_bad<=1;if(ip_status_data[0]) ip_pair_numeric<=1;
                if(first_error_code==0) first_error_code<=ERR_IFFT_STATUS;
              end
            end
            if(ip_event_unexpected_last || ip_event_missing_last || ip_event_overflow) begin
              if(ip_event_overflow) ip_pair_numeric<=1;
              ip_pair_bad<=1;if(first_error_code==0) first_error_code<=ERR_IFFT_EVENT;
            end
            if(input_count==1024 && output_count==1024 && status_received) state<=IP_FINAL;
          end
          IP_FINAL: begin
            pair_physically_retired[pair_id]<=1;
            if(killed || ip_pair_bad) begin
              pair_state[pair_id*4+:4]<=killed ? CANCELLED : (ip_pair_numeric ? NUMERIC : PROTOCOL);
              backend_stage_state[(pair_id+6)*4+:4]<=killed ? CANCELLED : (ip_pair_numeric ? NUMERIC : PROTOCOL);state<=NEXT_PAIR;
            end else begin
              backend_stage_state[(pair_id+6)*4+:4]<=OK;
              lag<=(pair_id==1 || pair_id==4) ? -8 : -6;peak<=-25'sd16777216;peak_lag<=0;
              second_peak<=0;second_valid<=0;state<=LAG_SCAN;
            end
          end
          LAG_SCAN: begin
            if(lag==((pair_id==1 || pair_id==4) ? -8 : -6) || correlation[scan_index]>peak) begin peak<=correlation[scan_index];peak_lag<=lag;end
            if(killed) begin pair_state[pair_id*4+:4]<=CANCELLED;state<=NEXT_PAIR;end
            else if(lag==((pair_id==1 || pair_id==4) ? 8 : 6)) begin
              lag<=(pair_id==1 || pair_id==4) ? -8 : -6;state<=LAG_MARGIN;
            end
            else lag<=lag+1;
          end
          LAG_MARGIN: begin
            if((lag<peak_lag-1 || lag>peak_lag+1) && (!second_valid || correlation[scan_index]>second_peak)) begin
              second_peak<=correlation[scan_index];second_valid<=1;
            end
            if(killed) begin pair_state[pair_id*4+:4]<=CANCELLED;state<=NEXT_PAIR;end
            else if(lag==((pair_id==1 || pair_id==4) ? 8 : 6)) begin math_phase<=0;state<=LAG_FINAL;end
            else lag<=lag+1;
          end
          LAG_FINAL: begin
            // 此沿在 LAG_MARGIN 最后一笔 NBA 更新之后，四相关值已稳定。
            // 原始资格不经过软件负责的插值/tau门限。NEXT_PAIR 将载荷采入独立槽。
            pair_valid[pair_id]<=!killed;
            pair_state[pair_id*4+:4]<=killed ? CANCELLED : OK;
            state<=NEXT_PAIR;
          end

          NEXT_PAIR: begin
            if(pair_id==5)begin pair_id<=0;state<=FINISH;end
            else begin pair_id<=pair_id+1'b1;state<=PAIR_BEGIN;end
          end
          FINISH: begin
            for(j=0;j<12;j=j+1)if(backend_stage_state[j*4+:4]==PENDING)
              backend_stage_state[j*4+:4]<=killed?CANCELLED:SKIPPED;
            state<=REPORT;
          end
          REPORT:state<=IDLE;
          default:begin if(first_error_code==0)first_error_code<=ERR_FRONTEND;state<=FINISH;end
        endcase
      end
    end
endmodule
`default_nettype wire
