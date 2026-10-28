#include "doa_dispatch.h"
#include <string.h>
doa_status_t doa_dispatch_solve(const doa_frame_input_t *frame,
    const doa_servo_config_t *servo,const doa3d_config_t *cfg,doa_dispatch_output_t *o)
{
    doa_status_t status;
    if(o==NULL)return DOA_BAD_ARGUMENT;
    memset(o,0,sizeof(*o));o->profile=SS_DOA_PROFILE;
#if SS_DOA_PROFILE == SS_DOA_PLANAR
    (void)cfg;status=doa_solve(frame,servo,&o->planar);
    if(status==DOA_OK && o->planar.direction_valid){o->direction_valid=1U;o->azimuth_valid=1U;o->azimuth_q8=o->planar.angle_q8;}
#else
    (void)servo;status=doa3d_solve(frame,cfg,&o->spatial);
    if(status==DOA_OK){o->direction_valid=o->spatial.direction_valid;o->azimuth_valid=o->spatial.azimuth_valid;o->elevation_valid=o->spatial.elevation_valid;o->azimuth_q8=o->spatial.azimuth_q8;o->elevation_q8=o->spatial.elevation_q8;}
#endif
    return status;
}

