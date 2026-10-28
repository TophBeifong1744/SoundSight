/* PS主机桥：逐字段解码冻结的六对字，不把C结构体当线协议。
 * 原S1源文件保持不变。out[]只用于本机ctypes，不是新的板间ABI。
 */
#include <stdint.h>
#include <string.h>
#include "doa_solver.h"

int ss_solve_words(uint32_t sequence, uint32_t status,
                   const uint32_t words[30], const int32_t config[7],
                   int32_t out[12])
{
    doa_frame_input_t frame;
    doa_servo_config_t servo;
    doa_solve_output_t result;
    unsigned p;
    doa_status_t rc;
    if (!words || !out || !sequence) return -1;
    memset(&frame,0,sizeof frame);memset(&servo,0,sizeof servo);
    memset(out,0,12*sizeof *out);
    if (status & ~(SNAP_STATUS_DEFINED_MASK | UINT32_C(0x00040000))) return -2; /* PS manual capability */
    if (!(status & SNAP_STATUS_LOCKED)) return -3;
    frame.frame_id=sequence;frame.flags=SNAP_STATUS_GET_FRAME_FLAGS(status);
    for(p=0;p<6;p++) {
        uint32_t w=words[p*5];
        if ((w & ~FEATURE_0_DEFINED_MASK) || FEATURE_0_GET_PAIR(w)!=p) return -4;
        frame.pair[p].lag=FEATURE_0_GET_LAG(w);
        frame.pair[p].flags=FEATURE_0_GET_FLAGS(w);
        frame.pair[p].mask_count=(uint8_t)FEATURE_0_GET_MASK_COUNT(w);
        frame.pair[p].peak=fpga_abi_word_to_s32(words[p*5+1]);
        frame.pair[p].r_minus=fpga_abi_word_to_s32(words[p*5+2]);
        frame.pair[p].r_plus=fpga_abi_word_to_s32(words[p*5+3]);
        frame.pair[p].second_peak=fpga_abi_word_to_s32(words[p*5+4]);
    }
    if(config) {
        /* 参数来自显式机械配置；先检查再缩窄，不能让负数回绕为uint16。 */
        if(config[4]<0 || config[4]>511 || config[5]<0 || config[5]>511 || config[6]<1 || config[6]>511) return -5;
        servo.config_valid=1;servo.offset_q8=config[0];servo.direction=config[1];
        servo.domain_min_q8=config[2];servo.domain_max_q8=config[3];
        servo.mechanical_min=(uint16_t)config[4];servo.mechanical_max=(uint16_t)config[5];servo.servo_max=(uint16_t)config[6];
    }
    rc=doa_solve(&frame,config?&servo:0,&result);
    out[0]=rc;out[1]=result.direction_valid;out[2]=result.direction_reason;
    out[3]=result.angle_q8;out[4]=result.ux_q20;out[5]=result.uy_q20;
    out[6]=result.valid_pair_count;out[7]=result.horizontal_servo_deg;
    out[8]=result.servo_cmd_valid;out[9]=result.servo_map_status;
    out[10]=result.first_error_code;out[11]=result.bad_pair_index;
    return (int)rc;
}
