/* Host-only stdin adapter. Input numbers are range-checked by replay_3d.py;
 * this private protocol is NOT the frozen SPI ABI or a hardware driver. */
#include "selected_geometry.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    doa3d_config_t c;doa_geometry_report_t report;doa_frame_input_t f;
    doa3d_output_t o;doa_status_t status;unsigned int i;int n;
    if(doa_geometry_build(&ss_geometry_selected,&c,&report)!=DOA_GEOMETRY_OK) {
        fprintf(stderr,"Geometry rejected: status=%d,pair=%u\n",(int)report.status,(unsigned)report.bad_pair);return 2;
    }
    printf("{\"geometry_valid\":true,\"solver_api\":%" PRIu32 ",\"normal_condition\":%.9g,\"uncertainty_known\":%u,\"pairs\":[",
        DOA3D_API_VERSION,(double)report.normal_condition,(unsigned)report.uncertainty_known);
    for(i=0U;i<6U;++i)printf("%s[%.9g,%.9g,%.9g]",i?",":"",(double)report.distance_mm[i],(double)report.nominal_delay_samples[i],(double)report.bounded_delay_samples[i]);
    puts("]}");
    for(;;) {
        memset(&f,0,sizeof(f));
        n=scanf("%" SCNu32 " %" SCNu32,&f.frame_id,&f.flags);
        if(n==EOF) return ferror(stdin)?2:0;
        if(n!=2) {fputs("Bad private frame input\n",stderr);return 2;}
        for(i=0U;i<6U;++i) {
            uint32_t mask;doa_pair_input_t *p=&f.pair[i];
            if(scanf("%" SCNd32 " %" SCNd32 " %" SCNd32 " %" SCNd32 " %" SCNd32 " %" SCNu32 " %" SCNu32,
                &p->lag,&p->peak,&p->r_minus,&p->r_plus,&p->second_peak,&mask,&p->flags)!=7 || mask>255U) {
                fputs("Bad private pair input\n",stderr);return 2;
            }
            p->mask_count=(uint8_t)mask;
        }
        status=doa3d_solve(&f,&c,&o);
        printf("{\"frame_id\":%" PRIu32 ",\"api_status\":%d,\"reason\":%d,\"valid\":%u,\"az_valid\":%u,\"el_valid\":%u,\"pair_count\":%u,\"pair_mask\":%u,\"first_error\":%u,\"bad_pair\":%u,",
            o.frame_id,(int)status,(int)o.reason,(unsigned)o.direction_valid,(unsigned)o.azimuth_valid,(unsigned)o.elevation_valid,
            (unsigned)o.valid_pair_count,(unsigned)o.valid_pair_mask,(unsigned)o.first_error_code,(unsigned)o.bad_pair_index);
        printf("\"ux\":%.9g,\"uy\":%.9g,\"uz\":%.9g,\"norm\":%.9g,\"residual\":%.9g,\"condition\":%.9g,\"azimuth_q8\":%" PRId32 ",\"elevation_q8\":%" PRId32 ",\"pairs\":[",
            (double)o.ux,(double)o.uy,(double)o.uz,(double)o.norm,(double)o.residual_rms_samples,(double)o.normal_condition,o.azimuth_q8,o.elevation_q8);
        for(i=0U;i<6U;++i) {
            const doa_pair_result_t *p=&o.pair[i];
            printf("%s{\"delta_q12\":%" PRId32 ",\"tau_q12\":%" PRId32 ",\"margin_q15\":%" PRId64 ",\"qualified\":%u,\"reason\":%d}",
                i?",":"",p->delta_q12,p->tau_q12,p->margin_q15,(unsigned)p->qualified,(int)p->reason);
        }
        printf("],\"azimuth_deg\":%.9g,\"elevation_deg\":%.9g}\n",(double)o.azimuth_deg,(double)o.elevation_deg);
    }
}
