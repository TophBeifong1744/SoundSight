#include "ss_solver_3d_bridge.h"
#include "doa_geometry.h"
#include <stdlib.h>
#include <string.h>
uint32_t ss3d_bridge_version(void) { return SS3D_BRIDGE_VERSION; }
static void clear_info(int32_t *info)
{
    if(info){memset(info,0,SS3D_INFO_COUNT*sizeof *info);info[11]=255;info[13]=255;}
}
static void clear_output(int32_t *info,float *values,int64_t *pairs)
{
    if(info)memset(info,0,SS3D_INFO_COUNT*sizeof *info);
    if(values)memset(values,0,SS3D_VALUE_COUNT*sizeof *values);
    if(pairs)memset(pairs,0,SS3D_PAIR_VALUE_COUNT*sizeof *pairs);
}
static int decode(uint32_t sequence,uint32_t status,const uint32_t words[30],doa_frame_input_t *frame)
{
    unsigned i;
    if(!sequence || !words)return -1;
    if(status & ~SNAP_STATUS_DEFINED_MASK) return -2;
    if(!(status & SNAP_STATUS_LOCKED)) return -3;
    memset(frame,0,sizeof *frame);
    frame->frame_id=sequence;frame->flags=SNAP_STATUS_GET_FRAME_FLAGS(status);
    for(i=0;i<6U;++i) {
        uint32_t w=words[i*5U];doa_pair_input_t *p=&frame->pair[i];
        if((w & ~FEATURE_0_DEFINED_MASK) || FEATURE_0_GET_PAIR(w)!=i) return -4;
        p->lag=FEATURE_0_GET_LAG(w);p->flags=FEATURE_0_GET_FLAGS(w);
        p->mask_count=(uint8_t)FEATURE_0_GET_MASK_COUNT(w);
        p->peak=fpga_abi_word_to_s32(words[i*5U+1U]);
        p->r_minus=fpga_abi_word_to_s32(words[i*5U+2U]);
        p->r_plus=fpga_abi_word_to_s32(words[i*5U+3U]);
        p->second_peak=fpga_abi_word_to_s32(words[i*5U+4U]);
    }
    return 0;
}
static int geometry(const float geo[15],const uint32_t meta[7],const char source[64],
                    doa3d_config_t *config,int32_t info[SS3D_INFO_COUNT])
{
    doa_geometry_record_t record;
    doa_geometry_report_t report;
    unsigned i,j;
    if(!geo || !meta || !source)return -1;
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
    info[12]=(int32_t)doa_geometry_build(&record,config,&report);
    info[13]=report.bad_pair;
    if(info[12]!=DOA_GEOMETRY_OK) return -5;
    return 0;
}
static void encode(doa_status_t rc,const doa3d_output_t *result,int32_t *info,float *values,int64_t *pairs)
{
    unsigned i;
    info[0]=(int32_t)rc;info[1]=result->direction_valid;info[2]=(int32_t)result->reason;
    info[3]=result->azimuth_valid;info[4]=result->elevation_valid;
    info[5]=result->azimuth_q8;info[6]=result->elevation_q8;
    info[7]=result->valid_pair_count;info[8]=result->valid_pair_mask;
    info[9]=result->coordinates_measured;info[10]=result->first_error_code;info[11]=result->bad_pair_index;
    values[0]=result->ux;values[1]=result->uy;values[2]=result->uz;values[3]=result->norm;
    values[4]=result->residual_rms_samples;values[5]=result->normal_condition;
    values[6]=result->azimuth_deg;values[7]=result->elevation_deg;
    for(i=0;i<6U;++i) {
        const doa_pair_result_t *p=&result->pair[i];
        pairs[5U*i]=p->delta_q12;pairs[5U*i+1U]=p->tau_q12;pairs[5U*i+2U]=p->margin_q15;
        pairs[5U*i+3U]=p->qualified;pairs[5U*i+4U]=(int64_t)p->reason;
    }
}
int ss3d_solve_words(uint32_t sequence,uint32_t status,
    const uint32_t words[30],const float geo[15],const uint32_t meta[7],
    const char source[64],int32_t info[SS3D_INFO_COUNT],
    float values[SS3D_VALUE_COUNT],int64_t pairs[SS3D_PAIR_VALUE_COUNT])
{
    doa3d_config_t config;
    doa_frame_input_t frame;
    doa3d_output_t result;
    doa_status_t rc;
    int status_rc;
    clear_output(info,values,pairs);
    if(!info || !values || !pairs || !words || !geo || !meta || !source || !sequence)return -1;
    clear_info(info);
    status_rc=decode(sequence,status,words,&frame);if(status_rc)return status_rc;
    status_rc=geometry(geo,meta,source,&config,info);if(status_rc)return status_rc;
    rc=doa3d_solve(&frame,&config,&result);
    encode(rc,&result,info,values,pairs);return (int)rc;
}
int ss3d_context_create(const float geo[15],const uint32_t meta[7],const char source[64],
    const uint32_t options_meta[3],const float options[10],int32_t info[SS3D_INFO_COUNT],void **context)
{
    doa3d_config_t config;
    doa3d_options_t settings;
    doa3d_prepared_t *p;
    unsigned i;
    int rc;
    if(context)*context=NULL;
    clear_info(info);
    if(!info || !context)return -1;
    rc=geometry(geo,meta,source,&config,info);if(rc)return rc;
    doa3d_default_options(&settings);
    if((options_meta==NULL)!=(options==NULL))return -6;
    if(options_meta!=NULL){
        if(options_meta[0]!=SS3D_OPTIONS_SCHEMA || options_meta[1]>1U ||
           options_meta[2]<4U || options_meta[2]>6U)return -6;
        settings.version=options_meta[0];settings.quality_weighting=(uint8_t)options_meta[1];
        config.min_pairs=(uint8_t)options_meta[2];
        config.max_normal_condition=options[0];config.max_residual_rms_samples=options[1];
        config.norm_min=options[2];config.norm_max=options[3];config.tau_slack_samples=options[4];
        settings.quality_weight_floor=options[5];
        for(i=0;i<4U;++i)settings.channel_delay_samples[i]=options[6U+i];
    }
    p=(doa3d_prepared_t *)malloc(sizeof(*p));if(p==NULL)return -7;
    if(doa3d_prepare(&config,&settings,p)!=DOA_OK){free(p);return -6;}
    *context=p;return 0;
}
int ss3d_context_solve(const void *context,uint32_t sequence,uint32_t status,
    const uint32_t words[30],int32_t info[SS3D_INFO_COUNT],
    float values[SS3D_VALUE_COUNT],int64_t pairs[SS3D_PAIR_VALUE_COUNT])
{
    doa_frame_input_t frame;
    doa3d_output_t result;
    doa_status_t rc;
    int status_rc;
    clear_output(info,values,pairs);
    if(!context || !info || !values || !pairs || !words || !sequence)return -1;
    clear_info(info);
    status_rc=decode(sequence,status,words,&frame);if(status_rc)return status_rc;
    rc=doa3d_solve_prepared(&frame,(const doa3d_prepared_t *)context,&result);
    encode(rc,&result,info,values,pairs);return (int)rc;
}
void ss3d_context_destroy(void *context) { free(context); }
