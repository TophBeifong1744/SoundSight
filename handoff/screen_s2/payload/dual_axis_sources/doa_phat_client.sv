// MIGRATION_MODULE_GUIDE
// 分组：06 六对特征
// 用途：把 PHAT 所需算术请求送到共享多周期计算单元。
// 接口要点：请求/返回握手、操作数和结果；等待期间保持当前对的计算上下文。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
// PHAT唯一控制器：保留任意公开输入域、零平方快路径及原完成沿。
module doa_phat_client (
  input logic clk,cold_rst_n,cancel,start,
  output logic ready,done,
  input logic signed [50:0] in_real,in_imag,
  input logic [191:0] in_square,
  output logic [51:0] result,
  output logic busy,
  // 私有请求/响应接合：控制器不再内建算术核，十四阶段时标保持。
  output logic alu_start,
  input logic alu_ready,alu_done,
  output logic [1:0] alu_op,
  output logic signed [191:0] alu_a,alu_b,
  output logic signed [31:0] alu_shift,
  input logic signed [191:0] alu_result
);
  import doa_math_pkg::*;
  logic [3:0] stage;
  logic issued;
  // 精确域宽：含任意U192平方的截断/开方回绕，不限制新调用输入。
  logic signed [50:0] re,im;
  logic [95:0] mag;
  logic [31:0] mant,r;
  logic [30:0] mr;
  logic signed [99:0] out_re;
  logic signed [32:0] newton_factor;
  wide_t temp;
  integer exponent,leading,rom_index,i;
  assign ready=!busy;
  always_comb begin
    leading=0;
    for(i=0;i<96;i=i+1) if(mag[i]) leading=i;
    // mant为0或[2^30,2^31]；原integer索引仅-256或0..256。
    if(mant<32'd1073741824) rom_index=0;
    else if(mant>=32'd2147483648) rom_index=255;
    else rom_index={24'd0,mant[29:22]};
    newton_factor=33'sd2147483648-$signed({2'd0,mr});
    alu_start=busy && !issued && alu_ready && !cancel;
    alu_op=2;alu_a=temp;alu_b=0;alu_shift=30;
    case(stage)
      0: begin alu_op=1;alu_a=temp;end
      1: begin alu_a=wide_t'($unsigned(mag));alu_shift=leading-30;end
      2: begin alu_op=3;alu_a=wide_t'($unsigned(mant));alu_b=wide_t'($unsigned(recip_rom(rom_index[7:0])));end
      6: begin alu_op=3;alu_a=wide_t'($unsigned(mant));alu_b=wide_t'($unsigned(r));end
      3,7: begin alu_a=temp;end
      4,8: begin alu_op=3;alu_a=wide_t'($unsigned(r));alu_b=wide_t'(newton_factor);end
      5,9: begin alu_a=temp;end
      10: begin alu_op=3;alu_a=wide_t'(re);alu_b=wide_t'($unsigned(r));end
      11: begin alu_a=temp;alu_shift=exponent-17;end
      12: begin alu_op=3;alu_a=wide_t'(im);alu_b=wide_t'($unsigned(r));end
      13: begin alu_a=temp;alu_shift=exponent-17;end
      default: begin alu_start=0;end
    endcase
  end
  always_ff @(posedge clk) begin
    if(!cold_rst_n || cancel) begin
      busy<=0;done<=0;result<=0;stage<=0;issued<=0;
      re<=0;im<=0;mag<=0;mant<=0;r<=0;mr<=0;temp<=0;out_re<=0;exponent<=0;
    end else begin
      done<=0;
      if(start && ready) begin
        result<=0;re<=in_real;im<=in_imag;
        temp<=in_square<<48;stage<=0;issued<=0;
        if(in_square==0) begin result<=52'h8000000000000;done<=1;busy<=0;end
        else busy<=1;
      end else if(busy) begin
        if(alu_start) issued<=1;
        if(alu_done) begin
          issued<=0;stage<=stage+1;
          case(stage)
            0: mag<=alu_result[95:0];
            1: begin mant<=alu_result[31:0];exponent<=leading;end
            // ROM seed is selected from newly published mant at stage2 issue.
            2,4,6,8,10,12: temp<=alu_result;
            3,7: mr<=alu_result[30:0];
            5,9: r<=alu_result[31:0];
            11: out_re<=alu_result[99:0];
            13: begin
              result<=0;
              if(out_re< -100'sd16777216 || out_re>100'sd16777215 ||
                 alu_result< -192'sd16777216 || alu_result>192'sd16777215) result[51]<=1;
              else begin result[49:25]<=out_re[24:0];result[24:0]<=alu_result[24:0];end
              busy<=0;done<=1;
            end
          endcase
        end
        if(stage==2 && !issued) r<={1'b0,recip_rom(rom_index[7:0])};
      end
    end
  end
endmodule
