/* Reuse the analytic forward fixture, not any inverse-derived expected angle. */
#define main legacy_3d_regression_entry
#include "test_doa_3d.c"
#undef main
#include "doa_target_3d.h"
#include <limits.h>

static doa3d_output_t angle(int32_t az,int32_t el)
{
    doa3d_output_t d;memset(&d,0,sizeof(d));d.frame_id=17U;
    d.direction_valid=1U;d.azimuth_valid=1U;d.elevation_valid=1U;
    d.reason=DOA3D_VALID;d.azimuth_q8=az;d.elevation_q8=el;return d;
}
static void empty_target(const doa_target3d_output_t *o)
{ CHECK("aggregate invalid clears both targets",!o->software_target_valid && o->horizontal_deg==0U && o->vertical_deg==0U); }
static void examples(void)
{
    doa_target3d_config_t c;doa_target3d_output_t o;doa3d_output_t d=angle(0,0);
    doa_target3d_example_config(&c);
    CHECK("default disabled",!doa_target3d_config_valid(&c) && doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_DISABLED);empty_target(&o);
    c.enable_mapping=1U;CHECK("explicit enabled",doa_target3d_config_valid(&c));
    CHECK("zero",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==90U && o.vertical_deg==90U);
    d=angle(45*256,30*256);
    CHECK("positive",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==135U && o.vertical_deg==120U);
    printf("D4_MAP,az=45,el=30,h=%u,v=%u,SOFTWARE_ONLY\n",(unsigned)o.horizontal_deg,(unsigned)o.vertical_deg);
    d=angle(-45*256,-30*256);
    CHECK("negative",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==45U && o.vertical_deg==60U);
    printf("D4_MAP,az=-45,el=-30,h=%u,v=%u,SOFTWARE_ONLY\n",(unsigned)o.horizontal_deg,(unsigned)o.vertical_deg);
    c.revision=7U;c.horizontal.direction=-1;c.vertical.direction=-1;c.vertical.offset_q8=80*256;
    d=angle(45*256,-30*256);
    CHECK("independent signs and zero",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==45U && o.vertical_deg==110U && o.config_revision==7U && o.frame_id==17U);
    printf("D4_MAP,reverse_both=1,vertical_zero=80,h=%u,v=%u,revision=%lu\n",(unsigned)o.horizontal_deg,(unsigned)o.vertical_deg,(unsigned long)o.config_revision);
}
static void boundaries(void)
{
    doa_target3d_config_t c;doa_target3d_output_t o;doa3d_output_t d;
    doa_target3d_example_config(&c);c.enable_mapping=1U;
    d=angle(128,384);
    CHECK("RNE half to even",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==90U && o.vertical_deg==92U);
    d=angle(-128,-384);
    CHECK("negative input half to even",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==90U && o.vertical_deg==88U);
    d=angle(-90*256,90*256);
    CHECK("endpoints included",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==0U && o.vertical_deg==180U);
    d=angle(90*256+1,0);
    CHECK("no domain clamp",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_AXIS_LIMIT && o.horizontal_status==DOA_MAP_DOMAIN && o.vertical_status==DOA_MAP_OK && o.axes_evaluated);empty_target(&o);
    c.horizontal.domain_max_q8=100*256;d=angle(90*256+1,0);
    CHECK("pre-round mechanical bound",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_AXIS_LIMIT && o.horizontal_status==DOA_MAP_MECHANICAL);empty_target(&o);
    c.horizontal.offset_q8=-1;d=angle(0,0);
    CHECK("negative tiny output not rounded into range",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_AXIS_LIMIT);empty_target(&o);
    doa_target3d_example_config(&c);c.enable_mapping=1U;c.vertical.mechanical_min=20;c.vertical.mechanical_max=160;
    d=angle(0,71*256);
    CHECK("vertical limit suppresses good horizontal",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_AXIS_LIMIT && o.horizontal_status==DOA_MAP_OK && o.vertical_status==DOA_MAP_MECHANICAL);empty_target(&o);
    d=angle(180*256,0);
    CHECK("positive180 not canonical",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_ANGLE_RANGE);empty_target(&o);
    c.horizontal.offset_q8=180*256;c.horizontal.domain_min_q8=-180*256;c.horizontal.domain_max_q8=179*256;c.horizontal.mechanical_max=359;c.horizontal.servo_max=359;
    d=angle(-180*256,0);
    CHECK("negative180 explicit domain accepted",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==0U);
    d=angle(179*256,0);
    CHECK("no implicit shortest path wrap",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==359U);
    d=angle(0,90*256+1);CHECK("elevation canonical",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_ANGLE_RANGE);empty_target(&o);
    d=angle(INT32_MIN,INT32_MAX);CHECK("extreme angles safe",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_ANGLE_RANGE);empty_target(&o);
    puts("D4_BOUNDARIES,PASS,RNE,domain,pre_round_limits,no_wrap,no_clamp");
}
static void source_and_config(void)
{
    doa_target3d_config_t c;doa_target3d_output_t o;doa3d_output_t d;
    unsigned int n;
    for(n=0U;n<16U;++n) {
        doa_target3d_example_config(&c);c.enable_mapping=1U;d=angle(0,0);
        switch(n) {
        case 0:c.revision=0;break;case 1:c.enable_mapping=2;break;
        case 2:c.horizontal.config_valid=0;break;case 3:c.vertical.config_valid=2;break;
        case 4:c.horizontal.direction=0;break;case 5:c.vertical.direction=INT32_MIN;break;
        case 6:c.horizontal.offset_q8=INT32_MAX;break;case 7:c.vertical.offset_q8=INT32_MIN;break;
        case 8:c.horizontal.domain_min_q8=-46081;break;case 9:c.horizontal.domain_max_q8=46080;break;
        case 10:c.vertical.domain_min_q8=-23041;break;case 11:c.vertical.domain_max_q8=23041;break;
        case 12:c.vertical.domain_min_q8=1;c.vertical.domain_max_q8=0;break;
        case 13:c.horizontal.mechanical_min=181;break;case 14:c.vertical.servo_max=0;break;
        default:c.vertical.servo_max=512;break;
        }
        memset(&o,0xa5,sizeof(o));
        CHECK("config invalid",!doa_target3d_config_valid(&c) && doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_CONFIG && !o.axes_evaluated);empty_target(&o);
    }
    doa_target3d_example_config(&c);c.enable_mapping=1U;
    for(n=0U;n<9U;++n) {
        d=angle(45*256,30*256);CHECK("valid first",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK);
        if(n==0U)d.direction_valid=0U;
        if(n==1U)d.direction_valid=2U;
        if(n==2U)d.reason=DOA3D_CANCELLED;
        if(n==3U)d.first_error_code=1U;
        if(n==4U)d.azimuth_valid=0U;
        if(n==5U)d.elevation_valid=0U;
        if(n==6U)d.azimuth_valid=2U;
        if(n==7U)d.elevation_valid=2U;
        CHECK("invalid source",doa_target3d_map(n==8U?DOA_INPUT_RANGE:DOA_OK,&d,&c,&o)!=DOA_TARGET3D_OK && !o.axes_evaluated);empty_target(&o);
    }
    CHECK("null config",doa_target3d_map(DOA_OK,&d,NULL,&o)==DOA_TARGET3D_ARGUMENT);empty_target(&o);
    CHECK("null direction",doa_target3d_map(DOA_OK,NULL,&c,&o)==DOA_TARGET3D_ARGUMENT);empty_target(&o);
    CHECK("null output",doa_target3d_map(DOA_OK,&d,&c,NULL)==DOA_TARGET3D_ARGUMENT);
    CHECK("null config check",!doa_target3d_config_valid(NULL));doa_target3d_example_config(NULL);
    puts("D4_REJECTIONS,PASS,16_bad_configs,invalid_sources,clear_previous_target");
}
static void sweep(void)
{
    doa_target3d_config_t c;doa_target3d_output_t o;doa3d_output_t d;
    int32_t q;int sign;
    doa_target3d_example_config(&c);c.enable_mapping=1U;
    /* Every Q8 subdegree across both axes' entire example domain; independent
     * floating reference uses floor and an explicit half/even decision. */
    for(sign=-1;sign<=1;sign+=2)for(q=-23040;q<=23040;++q) {
        double raw=90.0+(double)sign*(double)q/256.0,base=floor(raw),frac=raw-base;
        unsigned int expected=(unsigned int)base;
        if(frac>0.5 || (frac==0.5 && (expected%2U)!=0U))++expected;
        c.horizontal.direction=sign;c.vertical.direction=-sign;d=angle(q,-q);
        CHECK("full-domain independent reference",doa_target3d_map(DOA_OK,&d,&c,&o)==DOA_TARGET3D_OK && o.horizontal_deg==expected && o.vertical_deg==expected);
    }
    puts("D4_SWEEP,PASS,92162_Q8_sign_combinations");
}
static void integration(void)
{
    const double cases[][2]={{45,30},{-45,-30},{120,15},{0,90},{0,-90}};
    doa3d_config_t geometry;doa_target3d_config_t c;doa_target3d_output_t mapped;
    doa3d_output_t solved;doa_frame_input_t f;doa_status_t status;unsigned int i;
    doa3d_default_config(&geometry);doa_target3d_example_config(&c);c.enable_mapping=1U;
    for(i=0U;i<5U;++i) {
        f=synthetic(cases[i][0],cases[i][1]);status=doa3d_solve(&f,&geometry,&solved);
        CHECK("C solver valid",status==DOA_OK && solved.direction_valid);
        if(i<2U)CHECK("solver to two targets",doa_target3d_map(status,&solved,&c,&mapped)==DOA_TARGET3D_OK && mapped.horizontal_deg==(i==0U?135U:45U) && mapped.vertical_deg==(i==0U?120U:60U));
        else {CHECK("back or pole suppressed",doa_target3d_map(status,&solved,&c,&mapped)==(i==2U?DOA_TARGET3D_AXIS_LIMIT:DOA_TARGET3D_AXIS_UNOBSERVABLE));empty_target(&mapped);}
        printf("D4_CHAIN,az=%.0f,el=%.0f,status=%d,valid=%u,h=%u,v=%u\n",cases[i][0],cases[i][1],(int)mapped.status,(unsigned)mapped.software_target_valid,(unsigned)mapped.horizontal_deg,(unsigned)mapped.vertical_deg);
    }
    f=synthetic(45,30);for(i=0U;i<6U;++i)f.pair[i].mask_count=0;
    status=doa3d_solve(&f,&geometry,&solved);
    CHECK("solver rejection suppresses",doa_target3d_map(status,&solved,&c,&mapped)==DOA_TARGET3D_DIRECTION_REJECTED);empty_target(&mapped);
    f=synthetic(45,30);f.pair[0].lag=32;status=doa3d_solve(&f,&geometry,&solved);
    CHECK("solver API error suppresses",doa_target3d_map(status,&solved,&c,&mapped)==DOA_TARGET3D_SOLVER_ERROR);empty_target(&mapped);
}
int main(void)
{
    examples();boundaries();source_and_config();sweep();integration();
    printf("D4_RESULT,%s,checks=%u,failures=%u\n",failures?"FAIL":"PASS",checks,failures);
    return failures?1:0;
}
