#include "ss_solver_3d_bridge.h"
#include "doa_geometry.h"
#include <string.h>
/* PS-only capability advertised by ss_ps_control_regs. This says the manual
 * interface exists; it neither grants motion nor contributes to frame flags.
 * Keep the frozen STM32/SPI status mask unchanged and reject other reserved bits.
 */
#define SS3D_PS_MANUAL_CAPABILITY UINT32_C(0x00040000)
#define SS3D_PS_STATUS_DEFINED_MASK (SNAP_STATUS_DEFINED_MASK | SS3D_PS_MANUAL_CAPABILITY)
uint32_t ss3d_bridge_version(void) { return SS3D_BRIDGE_VERSION; }
int ss3d_solve_words(uint32_t sequence,uint32_t status,
    const uint32_t words[30],const float geo[15],const uint32_t meta[7],
    const char source[64],int32_t info[SS3D_INFO_COUNT],
    float values[SS3D_VALUE_COUNT],int64_t pairs[SS3D_PAIR_VALUE_COUNT])
{
    doa_geometry_record_t record;
    doa_geometry_report_t report;
    doa3d_config_t config;
    doa_frame_input_t frame;
    doa3d_output_t result;
    doa_status_t rc;
    unsigned i,j;
    if(info) memset(info,0,SS3D_INFO_COUNT*sizeof *info);
    if(values) memset(values,0,SS3D_VALUE_COUNT*sizeof *values);
    if(pairs) memset(pairs,0,SS3D_PAIR_VALUE_COUNT*sizeof *pairs);
    if(!info || !values || !pairs || !words || !geo || !meta || !source || !sequence) return -1;
    info[11]=255;info[13]=255;
    if(status & ~SS3D_PS_STATUS_DEFINED_MASK) return -2;
    if(!(status & SNAP_STATUS_LOCKED)) return -3;
    memset(&frame,0,sizeof frame);
    frame.frame_id=sequence;frame.flags=SNAP_STATUS_GET_FRAME_FLAGS(status);
    for(i=0;i<6U;++i) {
        uint32_t w=words[i*5U];doa_pair_input_t *p=&frame.pair[i];
        if((w & ~FEATURE_0_DEFINED_MASK) || FEATURE_0_GET_PAIR(w)!=i) return -4;
        p->lag=FEATURE_0_GET_LAG(w);p->flags=FEATURE_0_GET_FLAGS(w);
        p->mask_count=(uint8_t)FEATURE_0_GET_MASK_COUNT(w);
        p->peak=fpga_abi_word_to_s32(words[i*5U+1U]);
        p->r_minus=fpga_abi_word_to_s32(words[i*5U+2U]);
        p->r_plus=fpga_abi_word_to_s32(words[i*5U+3U]);
        p->second_peak=fpga_abi_word_to_s32(words[i*5U+4U]);
    }
    memset(&record,0,sizeof record);
    record.schema=meta[0];record.revision=meta[1];
    if(meta[2]>2U) { info[12]=DOA_GEOMETRY_METADATA;return -5; }
    record.provenance=(doa_geometry_source_t)meta[2];
    memcpy(record.source_id,source,64);
    record.sample_rate_hz=geo[12];record.sound_speed_m_s=geo[13];record.position_error_mm=geo[14];
    for(i=0;i<4U;++i) {
        if(meta[3U+i]>3U) { info[12]=DOA_GEOMETRY_CHANNEL;return -5; }
        record.mic[i].channel=(uint8_t)meta[3U+i];
        for(j=0;j<3U;++j) record.mic[i].xyz_mm[j]=geo[3U*i+j];
    }
    info[12]=(int32_t)doa_geometry_build(&record,&config,&report);
    info[13]=report.bad_pair;
    if(info[12]!=DOA_GEOMETRY_OK) return -5;
    rc=doa3d_solve(&frame,&config,&result);
    info[0]=(int32_t)rc;info[1]=result.direction_valid;info[2]=(int32_t)result.reason;
    info[3]=result.azimuth_valid;info[4]=result.elevation_valid;
    info[5]=result.azimuth_q8;info[6]=result.elevation_q8;
    info[7]=result.valid_pair_count;info[8]=result.valid_pair_mask;
    info[9]=result.coordinates_measured;info[10]=result.first_error_code;info[11]=result.bad_pair_index;
    values[0]=result.ux;values[1]=result.uy;values[2]=result.uz;values[3]=result.norm;
    values[4]=result.residual_rms_samples;values[5]=result.normal_condition;
    values[6]=result.azimuth_deg;values[7]=result.elevation_deg;
    for(i=0;i<6U;++i) {
        const doa_pair_result_t *p=&result.pair[i];
        pairs[5U*i]=p->delta_q12;pairs[5U*i+1U]=p->tau_q12;pairs[5U*i+2U]=p->margin_q15;
        pairs[5U*i+3U]=p->qualified;pairs[5U*i+4U]=(int64_t)p->reason;
    }
    return (int)rc;
}
