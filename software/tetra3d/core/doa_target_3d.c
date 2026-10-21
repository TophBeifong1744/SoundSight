#include "doa_target_3d.h"
#include <string.h>
void doa_target3d_example_config(doa_target3d_config_t *c)
{
    if(c==NULL) return;
    memset(c,0,sizeof(*c));c->revision=1U;
    c->horizontal.config_valid=1U;c->horizontal.offset_q8=23040;
    c->horizontal.direction=1;c->horizontal.domain_min_q8=-23040;
    c->horizontal.domain_max_q8=23040;c->horizontal.mechanical_min=0U;
    c->horizontal.mechanical_max=180U;c->horizontal.servo_max=180U;
    c->vertical=c->horizontal;
}
static int axis_config_valid(const doa_servo_config_t *c,int vertical)
{
    /* Same structural constraints as frozen doa_map_angle_q8; only the
     * vertical input domain is narrower. Numerical mapping itself is reused. */
    return c->config_valid==1U && (c->direction==1 || c->direction==-1) &&
        c->offset_q8>=-INT32_C(8388608) && c->offset_q8<=INT32_C(8388607) &&
        c->domain_min_q8>=(vertical?-INT32_C(23040):-INT32_C(46080)) &&
        c->domain_max_q8<=(vertical?INT32_C(23040):INT32_C(46079)) &&
        c->domain_min_q8<=c->domain_max_q8 &&
        c->mechanical_min<=c->mechanical_max && c->mechanical_max<=c->servo_max &&
        c->servo_max>0U && c->servo_max<=511U;
}
int doa_target3d_config_valid(const doa_target3d_config_t *c)
{
    return c!=NULL && c->revision!=0U && c->enable_mapping==1U &&
        axis_config_valid(&c->horizontal,0) && axis_config_valid(&c->vertical,1);
}
static doa_target3d_status_t finish(doa_target3d_output_t *o,doa_target3d_status_t s)
{ if(o!=NULL)o->status=s;return s; }
doa_target3d_status_t doa_target3d_map(doa_status_t solve_status,
    const doa3d_output_t *direction,const doa_target3d_config_t *config,doa_target3d_output_t *out)
{
    doa_servo_result_t h,v;
    if(out==NULL) return DOA_TARGET3D_ARGUMENT;
    memset(out,0,sizeof(*out));
    out->horizontal_status=DOA_MAP_DISABLED;out->vertical_status=DOA_MAP_DISABLED;
    if(direction==NULL || config==NULL) return finish(out,DOA_TARGET3D_ARGUMENT);
    out->frame_id=direction->frame_id;out->config_revision=config->revision;
    if(config->enable_mapping==0U) return finish(out,DOA_TARGET3D_DISABLED);
    if(!doa_target3d_config_valid(config)) return finish(out,DOA_TARGET3D_CONFIG);
    if(solve_status!=DOA_OK) return finish(out,DOA_TARGET3D_SOLVER_ERROR);
    if(direction->direction_valid!=1U || direction->reason!=DOA3D_VALID || direction->first_error_code!=0U)
        return finish(out,DOA_TARGET3D_DIRECTION_REJECTED);
    if(direction->azimuth_valid!=1U || direction->elevation_valid!=1U)
        return finish(out,DOA_TARGET3D_AXIS_UNOBSERVABLE);
    if(direction->azimuth_q8< -INT32_C(46080) || direction->azimuth_q8>=INT32_C(46080) ||
       direction->elevation_q8< -INT32_C(23040) || direction->elevation_q8>INT32_C(23040))
        return finish(out,DOA_TARGET3D_ANGLE_RANGE);
    out->axes_evaluated=1U;
    out->horizontal_status=doa_map_angle_q8(direction->azimuth_q8,&config->horizontal,&h);
    out->vertical_status=doa_map_angle_q8(direction->elevation_q8,&config->vertical,&v);
    if(!h.valid || !v.valid) return finish(out,DOA_TARGET3D_AXIS_LIMIT);
    out->horizontal_deg=h.angle_deg;out->vertical_deg=v.angle_deg;
    out->software_target_valid=1U;return finish(out,DOA_TARGET3D_OK);
}
