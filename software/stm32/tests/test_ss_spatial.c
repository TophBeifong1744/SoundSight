#define main s2_existing_regression_main
#include "test_fpga_link.c"
#undef main
#include "ss_app.h"
#include "ss_spatial.h"
#include <math.h>

/* Independent analytic forward arrivals; no inverse/default-config call. */
static packet_t tetra_packet(double az,double el,uint32_t id)
{
    const unsigned int a[6]={0,0,0,1,1,2},b[6]={1,2,3,2,3,3};
    const double rad=0.017453292519943295769;
    double h=sqrt(2.0/3.0)*40.0,x=40.0/sqrt(3.0),arrival[4],u[3];
    double pos[4][3]; unsigned int i; packet_t p=packet(1,0,id);
    pos[0][0]=x;pos[0][1]=0.0;pos[0][2]=-h/4.0;
    pos[1][0]=-x/2.0;pos[1][1]=20.0;pos[1][2]=-h/4.0;
    pos[2][0]=-x/2.0;pos[2][1]=-20.0;pos[2][2]=-h/4.0;
    pos[3][0]=0.0;pos[3][1]=0.0;pos[3][2]=3.0*h/4.0;
    u[0]=cos(az*rad)*cos(el*rad);u[1]=sin(az*rad)*cos(el*rad);u[2]=sin(el*rad);
    for(i=0U;i<4U;++i) arrival[i]=-(pos[i][0]*u[0]+pos[i][1]*u[1]+pos[i][2]*u[2])*48.0/343.0;
    for(i=0U;i<6U;++i) {
        long q=lround((arrival[a[i]]-arrival[b[i]])*4096.0);
        long lag=lround((double)q/4096.0),delta=q-lag*4096L;
        p.word[i][0]=(p.word[i][0]&UINT32_C(0xFFFFFF00))|(uint32_t)(lag<0?lag+256:lag);
        p.word[i][1]=100000U;p.word[i][2]=(uint32_t)(95904L-2L*delta);
        p.word[i][3]=(uint32_t)(95904L+2L*delta);p.word[i][4]=10000U;
    }
    return p;
}
static void app_setup(mock_t *m,ss_app_t *a)
{
    ss_link_t l;setup(m,&l);m->strict_control=1;
    CHECK("app init",ss_app_init(a,&l.bus)==SS_OK);
    CHECK("app start",ss_app_start(a)==SS_OK);
    CHECK("probe",ss_app_step(a)==SS_APP_NONE);
    CHECK("start",ss_app_step(a)==SS_APP_NONE && a->runtime.state==SS_RT_RUNNING);
    CHECK("3D arm rejected",ss_app_arm(a)==SS_ARGUMENT);
    ++m->clock_ms;
}
static void directions(void)
{
    const double dirs[][2]={{45,30},{-45,-30},{0,90},{0,-90},{120,15}};
    mock_t m;ss_app_t a;unsigned int i,before;
    app_setup(&m,&a);
    for(i=0U;i<5U;++i) {
        publish(&m,tetra_packet(dirs[i][0],dirs[i][1],i+1U));before=m.count;
        CHECK("one 3D application frame",ss_app_step(&a)==SS_APP_FRAME && a.fresh!=0U);
        CHECK("42 transactions",m.count-before==42U && m.consumes==i+1U && m.acquires==i+1U);
        CHECK("3D result profile and frame",a.spatial_result.profile==1U && a.spatial_result.direction_valid && a.spatial_result.spatial.frame_id==i+1U);
        CHECK("planar output not repurposed",zero_bytes(&a.result,sizeof(a.result)) && zero_bytes(&a.spatial_result.planar,sizeof(a.spatial_result.planar)));
        CHECK("elevation",fabs((double)a.spatial_result.elevation_q8/256.0-dirs[i][1])<0.04);
        if(i==2U || i==3U) CHECK("pole azimuth invalid",a.spatial_result.azimuth_valid==0U && a.spatial_result.azimuth_q8==0);
        else CHECK("azimuth",a.spatial_result.azimuth_valid && fabs((double)a.spatial_result.azimuth_q8/256.0-dirs[i][0])<0.04);
        CHECK("nominal provenance",a.spatial_result.spatial.coordinates_measured==0U);
        printf("D1_DIRECTION,expected_az=%.1f,expected_el=%.1f,az_q8=%ld,el_q8=%ld,az_valid=%u,consumes=%u,transfers=%u\n",
               dirs[i][0],dirs[i][1],(long)a.spatial_result.azimuth_q8,(long)a.spatial_result.elevation_q8,(unsigned)a.spatial_result.azimuth_valid,m.consumes,m.count-before);
        ++m.clock_ms;
    }
    CHECK("stats",a.frames==5U && a.rejected==0U);
    CHECK("no actions",m.action_writes==0U && m.permit_writes==0U && m.watchdog==0U);
    CHECK("STOP",ss_app_stop(&a)==SS_OK && ss_app_step(&a)==SS_APP_NONE);
    CHECK("drained",ss_app_step(&a)==SS_APP_ENDED && m.ctrl==8U && m.fault==64U);
    CHECK("ackstop",ss_app_ack_stop(&a)==SS_OK && m.fault==0U);
}
static void rejected_and_recovery(void)
{
    mock_t m;ss_app_t a;packet_t p;unsigned int i,before;
    app_setup(&m,&a);
    p=tetra_packet(45,30,1U);for(i=0;i<6U;++i)p.word[i][0]&=~UINT32_C(0x00FF0000);
    publish(&m,p);
    CHECK("mask rejection consumed",ss_app_step(&a)==SS_APP_FRAME && a.spatial_result.spatial.reason==DOA3D_PAIRS && !a.spatial_result.direction_valid && m.consumes==1U && a.rejected==1U);
    ++m.clock_ms;publish(&m,packet(1,1,2U));
    CHECK("legacy BIST not 3D",ss_app_step(&a)==SS_APP_FRAME && a.spatial_result.spatial.reason==DOA3D_LEGACY_BIST && !a.spatial_result.direction_valid && m.consumes==2U);
    ++m.clock_ms;p=tetra_packet(45,30,3U);p.flags|=SNAP_STATUS_FRAME_CANCELLED;publish(&m,p);
    CHECK("cancel consumed once",ss_app_step(&a)==SS_APP_FRAME && a.spatial_result.spatial.reason==DOA3D_CANCELLED && m.consumes==3U);
    ++m.clock_ms;before=m.count;
    CHECK("no stale valid on no frame",ss_app_step(&a)==SS_APP_NONE && a.fresh==0U && zero_bytes(&a.spatial_result,sizeof(a.spatial_result)) && m.consumes==3U && m.count-before==3U);
    ++m.clock_ms;publish(&m,tetra_packet(45,30,4U));m.fail_at=m.count+10U;
    CHECK("fault no result",ss_app_step(&a)==SS_APP_ERROR && a.fresh==0U && zero_bytes(&a.spatial_result,sizeof(a.spatial_result)));
    m.fail_at=0U;before=m.consumes;
    CHECK("recover no consume",ss_app_recover(&a)==SS_OK && a.runtime.state==SS_RT_IDLE && m.consumes==before);
    CHECK("explicit 3D discard",ss_app_discard(&a)==SS_OK && a.spatial_result.spatial.frame_id==4U && m.consumes==before+1U && m.action_writes==0U);
    puts("D1_REJECTIONS,PASS,mask,legacy_BIST,cancel,no_frame,clear_stale,recover,explicit_discard");
}
static void faults_and_budget(void)
{
    mock_t m;ss_link_t l;doa3d_config_t cfg;doa_frame_input_t f;doa_dispatch_output_t o;
    unsigned int n;int after,timeout;ss_status_t s;
    doa3d_default_config(&cfg);
    for(timeout=0;timeout<2;++timeout)for(after=0;after<2;++after)for(n=1U;n<=40U;++n){
        setup(&m,&l);publish(&m,tetra_packet(45,30,1U));m.fail_at=n;m.fail_after=after;m.timeout_error=timeout;
        memset(&o,0x5A,sizeof(o));s=ss_spatial_poll(&l,&cfg,&f,&o);
        CHECK("injected status",s==(timeout?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("clear output",zero_bytes(&f,sizeof(f)) && zero_bytes(&o,sizeof(o)) && l.recovery_required);
        CHECK("no replay of uncertain consume",m.consumes==(unsigned int)(n==40U && after!=0));
        m.fail_at=0U;CHECK("recover does not consume",ss_recover(&l)==SS_OK && m.consumes==(unsigned int)(n==40U && after!=0));
        CHECK("no physical commands",m.action_writes==0U && m.permit_writes==0U);
    }
    setup(&m,&l);publish(&m,tetra_packet(45,30,1U));l.bus.operation_timeout_ms=40U;
    CHECK("whole budget includes consume",ss_spatial_poll(&l,&cfg,&f,&o)==SS_TIMEOUT && m.consumes==1U && zero_bytes(&o,sizeof(o)));
    setup(&m,&l);publish(&m,tetra_packet(45,30,1U));m.clock_ms=UINT32_MAX-10U;
    CHECK("wrap",ss_spatial_poll(&l,&cfg,&f,&o)==SS_OK && o.direction_valid && m.consumes==1U && m.count==40U);
    setup(&m,&l);publish(&m,tetra_packet(45,30,1U));cfg.sample_rate_hz=44100.0f;
    CHECK("solver API error isolates without consume",ss_spatial_poll(&l,&cfg,&f,&o)==SS_SOLVER_ERROR && m.consumes==0U && l.recovery_required && zero_bytes(&o,sizeof(o)));
    puts("D1_FAULTS,PASS,160_before_after_IO_timeout,shared_budget,wrap,solver_error");
}
static void statistics_failure(void)
{
    mock_t m;ss_app_t a;
    app_setup(&m,&a);m.duration_ms=0U;publish(&m,tetra_packet(45,30,1U));m.fail_at=m.count+42U;
    CHECK("statistics read error",ss_app_step(&a)==SS_APP_ERROR && m.consumes==1U && !a.fresh && zero_bytes(&a.spatial_result,sizeof(a.spatial_result)));
    m.fail_at=0U;
    CHECK("stats error recover to idle",ss_app_recover(&a)==SS_OK && a.runtime.state==SS_RT_IDLE);
}
int main(void)
{
    directions();rejected_and_recovery();faults_and_budget();statistics_failure();
    printf("D1_RESULT,%s,checks=%u,failures=%u\n",failures?"FAIL":"PASS",checks,failures);
    return failures?1:0;
}
