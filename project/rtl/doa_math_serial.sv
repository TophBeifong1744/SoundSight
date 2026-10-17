// MIGRATION_MODULE_GUIDE
// 分组：06 六对特征
// 用途：以多周期方式执行共享整数算术，避免全部运算挤在一拍。
// 接口要点：操作选择、操作数、启动/忙/结果；完整定义见源码声明及状态机。
// 全部参数与端口：document/modules/RTL-INTERFACES.html。
`timescale 1ns/1ps
// 192位精确整数核：共享194位加减通路，分拍舍入/符号恢复以减少组合资源。
module doa_math_serial (
  input logic clk, cold_rst_n, cancel,
  input logic start, output logic ready,
  input logic [1:0] operation, // 0=RNE DIV,1=RNE SQRT,2=RNE SHIFT,3=MUL low192
  input logic signed [191:0] operand_a, operand_b,
  input logic signed [31:0] shift,
  output logic done, output logic signed [191:0] result,
  output logic busy
);
  localparam logic [2:0] INIT=0,CORE=1,ROUND_TEST=2,ROUND_ADD=3,SIGN=4;
  logic [2:0] phase;
  logic [1:0] op;
  logic [191:0] a,b,q;
  logic [193:0] remainder;
  logic [7:0] count;
  logic negative,left_shift,invalid_shift,sticky,guard,increment;
  logic [193:0] add_a,add_b;
  logic subtract;
  logic [194:0] add_full;
  logic [193:0] add_value;
  logic no_borrow,equal_value;
  assign ready=!busy;
  // 同一物理宽加减器：扩展进位表示无借位，避免独立比较器和减法器。
  assign add_full={1'b0,add_a}+{1'b0,(add_b^{194{subtract}})}+subtract;
  assign add_value=add_full[193:0];
  assign no_borrow=add_full[194];
  assign equal_value=(add_value==0);
  always_comb begin
    add_a=0;add_b=0;subtract=0;
    case(phase)
      INIT: begin
        if(negative && !left_shift) begin add_b={2'd0,a};subtract=1;end
        else add_a={2'd0,a};
      end
      CORE: case(op)
        0: begin add_a={1'b0,remainder[191:0],a[191]};add_b={2'd0,b};subtract=1;end
        1: begin
          add_a=(remainder<<2)|{192'd0,a[191:190]};
          add_b=({98'd0,q[95:0]}<<2)|194'd1;subtract=1;
        end
        3: begin add_a={2'd0,q};add_b=b[0] ? {2'd0,a} : 194'd0;end
        default: begin end
      endcase
      ROUND_TEST: begin
        // DIV 的 (r<<1) 必须先在192位截断，与历史函数逐码一致。
        add_a=op==0 ? {2'd0,remainder[190:0],1'b0} : remainder;
        add_b=op==0 ? {2'd0,b} : {98'd0,q[95:0]};subtract=1;
      end
      ROUND_ADD: begin
        add_a=op==2 ? {2'd0,a} : {2'd0,q};
        add_b=op==2 ? {193'd0,(guard && (sticky || a[0]))} : {193'd0,increment};
      end
      SIGN: begin
        if(negative) begin add_b={2'd0,q};subtract=1;end
        else add_a={2'd0,q};
      end
      default: begin end
    endcase
  end
  // 私有商/余数由本地空闲态清零，与迟到的start和cancel控制分开。
  // 接受请求沿ready=!busy，因此当沿已完成初始化，不增加任何服务拍。
  // cancel仍立即撤销busy/done/result；私有残值在下一空闲沿清除，绝不对外发布。
  always_ff @(posedge clk) begin
    if(!cold_rst_n || !busy) begin q<=0;remainder<=0;end
    else begin
      case(phase)
        CORE: case(op)
          0: begin
            q<={q[190:0],no_borrow};
            remainder<=no_borrow ? add_value : {1'b0,remainder[191:0],a[191]};
          end
          1: begin
            q<={96'd0,q[94:0],no_borrow};
            remainder<=no_borrow ? add_value : ((remainder<<2)|{192'd0,a[191:190]});
          end
          3: q<=add_value[191:0];
          default: begin end
        endcase
        ROUND_ADD: if(op!=1 && !(op==2 && left_shift)) q<=add_value[191:0];
        default: begin end
      endcase
    end
  end
  always_ff @(posedge clk) begin
    // 取消同拍优先于完成，不发布旧请求done或结果。
    if(!cold_rst_n || cancel) begin
      busy<=0;done<=0;result<=0;phase<=INIT;op<=0;a<=0;b<=0;
      count<=0;negative<=0;left_shift<=0;invalid_shift<=0;
      sticky<=0;guard<=0;increment<=0;
    end else begin
      done<=0;
      if(start && ready) begin
        busy<=1;op<=operation;a<=operand_a;b<=operand_b;
        negative<=operand_a<0;left_shift<=operation==2 && shift<0;
        invalid_shift<=operation==2 && ((shift>=191) || (shift<=-192));
        sticky<=0;guard<=0;increment<=0;phase<=INIT;count<=0;
        case(operation)
          0: count<=192;
          1: begin phase<=CORE;count<=96;end
          2: count<=shift<0 ? -shift : shift;
          3: begin phase<=CORE;count<=192;end
        endcase
      end else if(busy) begin
        case(phase)
          INIT: begin
            if((op==0 && $signed(b)<=0) || (op==2 && invalid_shift)) begin
              result<=0;busy<=0;done<=1;
            end else begin a<=add_value[191:0];phase<=count==0 ? ROUND_ADD : CORE;end
          end
          CORE: case(op)
            0: begin
              a<=a<<1;count<=count-1;
              if(count==1) phase<=ROUND_TEST;
            end
            1: begin
              a<=a<<2;count<=count-1;
              if(count==1) phase<=ROUND_TEST;
            end
            2: begin
              a<=left_shift ? a<<1 : a>>1;count<=count-1;
              if(!left_shift) begin
                if(count==1) guard<=a[0];else sticky<=sticky|a[0];
              end
              if(count==1) phase<=ROUND_ADD;
            end
            3: begin
              a<=a<<1;b<=b>>1;count<=count-1;
              if(count==1 || b[191:1]==0) begin result<=add_value[191:0];busy<=0;done<=1;end
            end
          endcase
          ROUND_TEST: begin
            increment<=no_borrow && (!equal_value || (op==0 && q[0]));phase<=ROUND_ADD;
          end
          ROUND_ADD: begin
            if(op==1) begin result<={96'd0,add_value[95:0]};busy<=0;done<=1;end
            else if(op==2 && left_shift) begin result<=a;busy<=0;done<=1;end
            else begin phase<=SIGN;end
          end
          SIGN: begin result<=add_value[191:0];busy<=0;done<=1;end
          default: begin result<=0;busy<=0;done<=1;end
        endcase
      end
    end
  end
endmodule
