/* Test-only direct semantic input oracle, independent of FEATURE_0 decoding.
 * The original solver C tests provide independent forward-physics expectations.
 * This oracle isolates bridge/ctypes regressions, not algorithm correctness. */
#include "doa_solver_3d.h"
#include <string.h>
int reference3d(uint32_t sequence,uint32_t flags,const int64_t input[42],
                int32_t info[12],float values[8],int64_t pairs[30])
{
    doa3d_config_t c;doa_frame_input_t f;doa3d_output_t o;doa_status_t rc;unsigned i;
    memset(&f,0,sizeof f);f.frame_id=sequence;f.flags=flags;
    doa3d_default_config(&c);
    for(i=0;i<6U;++i) {
        doa_pair_input_t *p=&f.pair[i];const int64_t *s=&input[7U*i];
        p->lag=(int32_t)s[0];p->peak=(int32_t)s[1];p->r_minus=(int32_t)s[2];
        p->r_plus=(int32_t)s[3];p->second_peak=(int32_t)s[4];
        p->mask_count=(uint8_t)s[5];p->flags=(uint32_t)s[6];
    }
    rc=doa3d_solve(&f,&c,&o);
    info[0]=(int32_t)rc;info[1]=o.direction_valid;info[2]=(int32_t)o.reason;
    info[3]=o.azimuth_valid;info[4]=o.elevation_valid;info[5]=o.azimuth_q8;info[6]=o.elevation_q8;
    info[7]=o.valid_pair_count;info[8]=o.valid_pair_mask;info[9]=o.coordinates_measured;
    info[10]=o.first_error_code;info[11]=o.bad_pair_index;
    values[0]=o.ux;values[1]=o.uy;values[2]=o.uz;values[3]=o.norm;
    values[4]=o.residual_rms_samples;values[5]=o.normal_condition;values[6]=o.azimuth_deg;values[7]=o.elevation_deg;
    for(i=0;i<6U;++i) {
        pairs[i*5U]=o.pair[i].delta_q12;pairs[i*5U+1U]=o.pair[i].tau_q12;
        pairs[i*5U+2U]=o.pair[i].margin_q15;pairs[i*5U+3U]=o.pair[i].qualified;
        pairs[i*5U+4U]=(int64_t)o.pair[i].reason;
    }
    return (int)rc;
}

