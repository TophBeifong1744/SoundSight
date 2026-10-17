#include "doa_dispatch.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static unsigned int checks,failures;
#define CHECK(n,x) do { ++checks; if(!(x)){++failures;printf("FAIL,%s,line=%d\n",n,__LINE__);} } while(0)
static const unsigned int aa[6]={0,0,0,1,1,2},bb[6]={1,2,3,2,3,3};
static const double rad=0.017453292519943295769;
static void set_tau(doa_pair_input_t *p,double tau)
{
    long tq=lround(tau*4096.0),lag=lround((double)tq/4096.0),delta=tq-lag*4096L;
    p->lag=(int32_t)lag;p->peak=100000;p->r_minus=(int32_t)(100000L-4096L-2L*delta);
    p->r_plus=(int32_t)(100000L-4096L+2L*delta);p->second_peak=10000;p->mask_count=79;
    p->flags=FEATURE_0_RAW_PEAK_VALID|FEATURE_0_SECOND_VALID|FEATURE_0_IFFT_QUALIFIED|
        (UINT32_C(1)<<FEATURE_0_PHAT_STAGE_SHIFT)|(UINT32_C(1)<<FEATURE_0_IFFT_STAGE_SHIFT);
}
/* Independent forward model: absolute arrivals at analytic positions, followed
 * by arrival[a]-arrival[b]. Never calls inverse solver or its default geometry. */
static doa_frame_input_t synthetic(double az,double el)
{
    doa_frame_input_t f;double pos[4][3],arrival[4],u[3];unsigned int i;
    const double a=40.0,h=sqrt(2.0/3.0)*a,x=a/sqrt(3.0);
    memset(&f,0,sizeof(f));f.frame_id=100;f.flags=SNAP_STATUS_ALL_TERMINAL;
    pos[0][0]=x;pos[0][1]=0;pos[0][2]=-h/4;
    pos[1][0]=-x/2;pos[1][1]=a/2;pos[1][2]=-h/4;
    pos[2][0]=-x/2;pos[2][1]=-a/2;pos[2][2]=-h/4;
    pos[3][0]=0;pos[3][1]=0;pos[3][2]=3*h/4;
    u[0]=cos(el*rad)*cos(az*rad);u[1]=cos(el*rad)*sin(az*rad);u[2]=sin(el*rad);
    for(i=0;i<4U;++i)arrival[i]=-(pos[i][0]*u[0]+pos[i][1]*u[1]+pos[i][2]*u[2])*48.0/343.0;
    for(i=0;i<6U;++i)set_tau(&f.pair[i],arrival[aa[i]]-arrival[bb[i]]);
    return f;
}
static double angle_error(double a,double b)
{double e=fabs(a-b);return e>180.0?360.0-e:e;}
static void test_direction(double az,double el,int print)
{
    doa3d_config_t c;doa3d_output_t o;doa_frame_input_t f=synthetic(az,el);
    doa_dispatch_output_t d;double coserr,err;
    doa3d_default_config(&c);
    CHECK("API",doa3d_solve(&f,&c,&o)==DOA_OK);
    CHECK("direction",o.direction_valid && o.elevation_valid && o.reason==DOA3D_VALID);
    CHECK("all pairs",o.valid_pair_count==6U);
    CHECK("nominal not measured",o.coordinates_measured==0U);
    CHECK("elevation",fabs(o.elevation_deg-el)<0.03);
    if(fabs(el)==90.0)CHECK("pole azimuth invalid",o.azimuth_valid==0U && o.azimuth_q8==0);
    else CHECK("azimuth",o.azimuth_valid && angle_error(o.azimuth_deg,az)<0.03);
    coserr=(o.ux*cos(el*rad)*cos(az*rad)+o.uy*cos(el*rad)*sin(az*rad)+o.uz*sin(el*rad))/o.norm;
    if(coserr>1.0)coserr=1.0;
    if(coserr< -1.0)coserr=-1.0;
    err=acos(coserr)/rad;CHECK("3D angular error",err<0.04);
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    CHECK("dispatch",doa_dispatch_solve(&f,NULL,&c,&d)==DOA_OK && d.profile==1U && d.direction_valid && d.elevation_valid && d.azimuth_q8==o.azimuth_q8);
#else
    (void)d;
#endif
    if(print)printf("DIRECTION,expected_az=%.1f,expected_el=%.1f,actual_az=%.6f,actual_el=%.6f,az_valid=%u,el_valid=%u,rms=%.8f,norm=%.8f\n",az,el,(double)o.azimuth_deg,(double)o.elevation_deg,(unsigned)o.azimuth_valid,(unsigned)o.elevation_valid,(double)o.residual_rms_samples,(double)o.norm);
}
static void rejection(const char *name,doa_frame_input_t *f,doa3d_config_t *c,doa_status_t status,doa3d_reason_t reason)
{
    doa3d_output_t o;memset(&o,0xa5,sizeof(o));
    CHECK(name,doa3d_solve(f,c,&o)==status && !o.direction_valid && !o.azimuth_valid && !o.elevation_valid && o.reason==reason && o.azimuth_q8==0 && o.elevation_q8==0);
    printf("REJECT,%s,status=%d,reason=%d\n",name,(int)status,(int)o.reason);
}
static void negatives(void)
{
    doa3d_config_t c;doa_frame_input_t f;doa3d_output_t o;unsigned int i,j;
    doa3d_default_config(&c);f=synthetic(0,0);
    for(i=0;i<6U;++i)f.pair[i].mask_count=11;
    rejection("mask_below12",&f,&c,DOA_OK,DOA3D_PAIRS);
    f=synthetic(0,0);f.pair[2].mask_count=0;f.pair[4].mask_count=0;f.pair[5].mask_count=0;
    rejection("only_base_triangle",&f,&c,DOA_OK,DOA3D_PAIRS);
    f=synthetic(45,30);f.pair[0].mask_count=0;
    CHECK("one pair lost",doa3d_solve(&f,&c,&o)==DOA_OK && o.direction_valid && o.valid_pair_count==5U);
    f=synthetic(0,0);for(i=0;i<4U;++i)c.mic_mm[i][2]=0;
    rejection("coplanar",&f,&c,DOA_OK,DOA3D_SINGULAR);
    doa3d_default_config(&c);for(i=0;i<4U;++i)c.mic_mm[i][2]*=0.01f;
    rejection("flattened_geometry",&f,&c,DOA_OK,DOA3D_CONDITION);
    doa3d_default_config(&c);for(i=0;i<4U;++i)for(j=0;j<3U;++j)c.mic_mm[i][j]*=2;
    rejection("exceeds_PL_window",&f,&c,DOA_BAD_ARGUMENT,DOA3D_CONFIG);
    doa3d_default_config(&c);c.mic_mm[0][0]=NAN;
    rejection("NaN_geometry",&f,&c,DOA_BAD_ARGUMENT,DOA3D_CONFIG);
    doa3d_default_config(&c);c.sample_rate_hz=44100;
    rejection("wrong_samplerate",&f,&c,DOA_BAD_ARGUMENT,DOA3D_CONFIG);
    doa3d_default_config(&c);for(i=0;i<6U;++i)set_tau(&f.pair[i],0);
    rejection("zero_norm",&f,&c,DOA_OK,DOA3D_NORM);
    f=synthetic(0,0);set_tau(&f.pair[0],4.0);
    rejection("inconsistent_pair",&f,&c,DOA_OK,DOA3D_RESIDUAL);
    f=synthetic(0,0);f.flags|=SNAP_STATUS_FRAME_CANCELLED;
    rejection("cancel",&f,&c,DOA_OK,DOA3D_CANCELLED);
    f=synthetic(0,0);f.pair[0].flags|=FEATURE_0_NUMERIC_ERROR;
    rejection("source_numeric",&f,&c,DOA_OK,DOA3D_SOURCE);
    f=synthetic(0,0);f.pair[0].peak=DOA_S25_MAX+1;
    rejection("S25_range",&f,&c,DOA_INPUT_RANGE,DOA3D_SOURCE);
    f=synthetic(0,0);f.pair[0].lag=32;
    rejection("S6_range",&f,&c,DOA_INPUT_RANGE,DOA3D_SOURCE);
    f=synthetic(0,0);f.flags=0;
    rejection("incomplete",&f,&c,DOA_INCOMPLETE_FRAME,DOA3D_SOURCE);
    f=synthetic(0,0);f.pair[0].flags|=UINT32_C(0x00800000);
    rejection("reserved_flags",&f,&c,DOA_INPUT_FLAGS,DOA3D_SOURCE);
    f=synthetic(0,0);f.flags|=SNAP_STATUS_BIST;
    for(i=0;i<6U;++i)f.pair[i].flags=ABI_BIST_PAIR_FLAGS;
    rejection("legacy_BIST_not_3D",&f,&c,DOA_OK,DOA3D_LEGACY_BIST);
    /* Translation of coordinates must not rotate the inferred direction. */
    f=synthetic(-70,25);for(i=0;i<4U;++i){c.mic_mm[i][0]+=100;c.mic_mm[i][1]-=40;c.mic_mm[i][2]+=10;}
    CHECK("translation",doa3d_solve(&f,&c,&o)==DOA_OK && o.direction_valid && angle_error(o.azimuth_deg,-70)<0.03 && fabs(o.elevation_deg-25)<0.03);
}

static void subsets(void)
{
    unsigned int mask,i,count;doa3d_config_t c;doa_frame_input_t f;doa3d_output_t o;
    doa3d_default_config(&c);
    for(mask=0U;mask<64U;++mask){
        f=synthetic(45,30);count=0U;
        for(i=0;i<6U;++i){if((mask&(1U<<i))!=0U)++count;else f.pair[i].mask_count=0U;}
        CHECK("subset API",doa3d_solve(&f,&c,&o)==DOA_OK);
        CHECK("subset count",o.valid_pair_count==count);
        if(count>=4U)CHECK("subset direction",o.direction_valid && angle_error(o.azimuth_deg,45)<0.03 && fabs(o.elevation_deg-30)<0.03);
        else CHECK("subset rejection",!o.direction_valid && o.reason==DOA3D_PAIRS);
    }
    printf("SUBSETS,64,minimum_pairs=4,all_expected\n");
}

static void planar_adapter(void)
{
#if SS_DOA_PROFILE == SS_DOA_PLANAR
    doa_frame_input_t f;doa_solve_output_t before;doa_dispatch_output_t after;unsigned int i;
    const int32_t lags[6]=ABI_BIST_PASS_LAGS_INITIALIZER;
    memset(&f,0,sizeof(f));f.frame_id=1;f.flags=ABI_BIST_FRAME_FLAGS;
    for(i=0;i<6U;++i){f.pair[i].lag=lags[i];f.pair[i].peak=1000;f.pair[i].r_minus=800;f.pair[i].r_plus=800;f.pair[i].second_peak=100;f.pair[i].mask_count=79;f.pair[i].flags=ABI_BIST_PAIR_FLAGS;}
    CHECK("original 2D",doa_solve(&f,NULL,&before)==DOA_OK);
    CHECK("2D dispatch",doa_dispatch_solve(&f,NULL,NULL,&after)==DOA_OK);
    CHECK("2D preserved",memcmp(&before,&after.planar,sizeof(before))==0 && after.profile==0U && after.direction_valid && !after.elevation_valid);
#endif
}
int main(void)
{
    int az,el;doa3d_config_t c;unsigned int i;
    doa3d_default_config(&c);
    for(i=0;i<4U;++i)printf("MIC,%u,x=%.6f,y=%.6f,z=%.6f,mm\n",i,(double)c.mic_mm[i][0],(double)c.mic_mm[i][1],(double)c.mic_mm[i][2]);
    test_direction(0,0,1);test_direction(90,0,1);test_direction(-90,0,1);
    test_direction(45,30,1);test_direction(-45,-30,1);test_direction(0,90,1);test_direction(0,-90,1);
    for(el=-75;el<=75;el+=15)for(az=-180;az<180;az+=15)test_direction((double)az,(double)el,0);
    negatives();subsets();planar_adapter();
    printf("RESULT,%s,profile=%d,checks=%u,failures=%u,SYNTHETIC_FEATURES_ONLY\n",failures?"FAIL":"PASS",SS_DOA_PROFILE,checks,failures);
    return failures?1:0;
}
