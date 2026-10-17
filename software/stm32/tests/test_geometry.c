#define SS_SPATIAL_TEST_ENTRY d1_regression_entry
#include "test_ss_spatial.c"
#undef SS_SPATIAL_TEST_ENTRY
#include "doa_geometry.h"

static void reject_config(const char *name,doa_geometry_record_t *r,doa_geometry_status_t expect)
{
    doa3d_config_t c;doa_geometry_report_t report;
    memset(&c,0x5a,sizeof(c));
    CHECK(name,doa_geometry_build(r,&c,&report)==expect && !report.valid && zero_bytes(&c,sizeof(c)));
    printf("D2_REJECT,%s,status=%d,bad_pair=%u\n",name,(int)report.status,(unsigned)report.bad_pair);
}
static void geometry_tests(void)
{
    doa_geometry_record_t r,base;doa_geometry_report_t report;doa3d_config_t c,original;
    unsigned int i,j;
    doa_geometry_nominal(&base);r=base;doa3d_default_config(&original);
    CHECK("nominal",doa_geometry_build(&r,&c,&report)==DOA_GEOMETRY_OK && report.valid);
    CHECK("nominal equals D1",memcmp(&c,&original,sizeof(c))==0);
    CHECK("unknown uncertainty not zero",!report.uncertainty_known && report.bounded_delay_samples[0]==-1.0f && !c.coordinates_measured);
    CHECK("normal condition",fabs(report.normal_condition-1.0)<1e-5);
    for(i=0U;i<6U;++i) {
        CHECK("40mm six pairs",fabs(report.distance_mm[i]-40.0)<1e-5);
        CHECK("delay",fabs(report.nominal_delay_samples[i]-40.0*48.0/343.0)<1e-6);
    }
    printf("D2_NOMINAL,mm=%.6f,delay=%.6f,condition=%.6f,uncertainty_known=%u\n",
        (double)report.distance_mm[0],(double)report.nominal_delay_samples[0],(double)report.normal_condition,(unsigned)report.uncertainty_known);
    r.mic[0]=base.mic[3];r.mic[3]=base.mic[0];
    CHECK("row order invariant",doa_geometry_build(&r,&c,&report)==DOA_GEOMETRY_OK && memcmp(&c,&original,sizeof(c))==0);
    r=base;r.provenance=DOA_GEOMETRY_MEASURED;r.position_error_mm=0.5f;
    CHECK("declared measurement",doa_geometry_build(&r,&c,&report)==DOA_GEOMETRY_OK && c.coordinates_measured && report.uncertainty_known);
    CHECK("error envelope",fabs(report.bounded_delay_samples[0]-41.0*48.0/343.0)<1e-6);
    printf("D2_UNCERTAINTY,error_mm=0.5,bounded_samples=%.6f,accepted=1,DECLARED_ONLY\n",(double)report.bounded_delay_samples[0]);
    r.position_error_mm=2.0f;reject_config("2mm_error_exceeds_pair01_window",&r,DOA_GEOMETRY_WINDOW);
    r=base;r.mic[0].channel=1;reject_config("duplicate_channel",&r,DOA_GEOMETRY_CHANNEL);
    r=base;r.mic[0].channel=4;reject_config("out_of_range_channel",&r,DOA_GEOMETRY_CHANNEL);
    r=base;r.revision=0;reject_config("zero_revision",&r,DOA_GEOMETRY_METADATA);
    r=base;r.schema=2;reject_config("unknown_schema",&r,DOA_GEOMETRY_METADATA);
    r=base;r.provenance=(doa_geometry_source_t)3;reject_config("unknown_provenance",&r,DOA_GEOMETRY_METADATA);
    r=base;r.source_id[0]=0;reject_config("empty_source",&r,DOA_GEOMETRY_METADATA);
    r=base;memset(r.source_id,'x',sizeof(r.source_id));reject_config("unterminated_source",&r,DOA_GEOMETRY_METADATA);
    r=base;r.source_id[0]='\n';reject_config("control_in_source",&r,DOA_GEOMETRY_METADATA);
    r=base;r.sample_rate_hz=44100;reject_config("wrong_rate",&r,DOA_GEOMETRY_RANGE);
    r=base;r.sound_speed_m_s=0;reject_config("zero_speed",&r,DOA_GEOMETRY_RANGE);
    r=base;r.sound_speed_m_s=NAN;reject_config("NaN_speed",&r,DOA_GEOMETRY_RANGE);
    r=base;r.mic[0].xyz_mm[0]=NAN;reject_config("NaN_coordinate",&r,DOA_GEOMETRY_RANGE);
    r=base;r.mic[0].xyz_mm[0]=INFINITY;reject_config("Inf_coordinate",&r,DOA_GEOMETRY_RANGE);
    r=base;r.mic[0].xyz_mm[0]=1001;reject_config("coordinate_range",&r,DOA_GEOMETRY_RANGE);
    r=base;r.provenance=DOA_GEOMETRY_MEASURED;reject_config("measured_without_error_bound",&r,DOA_GEOMETRY_RANGE);
    r.position_error_mm=0;reject_config("measured_zero_error_bound",&r,DOA_GEOMETRY_RANGE);
    r=base;r.position_error_mm=NAN;reject_config("NaN_error_bound",&r,DOA_GEOMETRY_RANGE);
    r=base;r.position_error_mm=-0.5f;reject_config("invalid_unknown_sentinel",&r,DOA_GEOMETRY_RANGE);
    r=base;memcpy(r.mic[1].xyz_mm,r.mic[0].xyz_mm,sizeof(r.mic[0].xyz_mm));reject_config("coincident",&r,DOA_GEOMETRY_WINDOW);
    r=base;for(i=0U;i<4U;++i)r.mic[i].xyz_mm[2]=0;reject_config("coplanar",&r,DOA_GEOMETRY_SINGULAR);
    r=base;for(i=0U;i<4U;++i)r.mic[i].xyz_mm[2]*=0.01f;reject_config("ill_conditioned",&r,DOA_GEOMETRY_CONDITION);
    r=base;for(i=0U;i<4U;++i)for(j=0U;j<3U;++j)r.mic[i].xyz_mm[j]*=2.0f;reject_config("oversized",&r,DOA_GEOMETRY_WINDOW);
    memset(&c,1,sizeof(c));CHECK("null record",doa_geometry_build(NULL,&c,&report)==DOA_GEOMETRY_ARGUMENT && zero_bytes(&c,sizeof(c)));
    CHECK("null output",doa_geometry_build(&base,NULL,&report)==DOA_GEOMETRY_ARGUMENT);
    CHECK("null report",doa_geometry_build(&base,&c,NULL)==DOA_GEOMETRY_ARGUMENT && zero_bytes(&c,sizeof(c)));
}
/* Independent forward arrivals from physical rows plus their channel labels.
 * Does not use built config or inverse solver to produce the features. */
static packet_t mapped_packet(const doa_geometry_record_t *r,double az,double el)
{
    const unsigned int a[6]={0,0,0,1,1,2},b[6]={1,2,3,2,3,3};
    double arrival[4],u[3],rad=0.017453292519943295769;unsigned int i,j;
    packet_t p=packet(1,0,1U);
    u[0]=cos(az*rad)*cos(el*rad);u[1]=sin(az*rad)*cos(el*rad);u[2]=sin(el*rad);
    for(i=0U;i<4U;++i) {
        double dot=0;for(j=0U;j<3U;++j)dot+=(double)r->mic[i].xyz_mm[j]*u[j];
        arrival[r->mic[i].channel]=-dot*(double)r->sample_rate_hz/(1000.0*(double)r->sound_speed_m_s);
    }
    for(i=0U;i<6U;++i) {
        long q=lround((arrival[a[i]]-arrival[b[i]])*4096.0),lag=lround((double)q/4096.0),d=q-lag*4096L;
        p.word[i][0]=(p.word[i][0]&UINT32_C(0xFFFFFF00))|(uint32_t)(lag<0?lag+256:lag);
        p.word[i][1]=100000U;p.word[i][2]=(uint32_t)(95904L-2L*d);p.word[i][3]=(uint32_t)(95904L+2L*d);p.word[i][4]=10000U;
    }
    return p;
}
static void mapped_directions(void)
{
    doa_geometry_record_t r;doa_geometry_report_t report;ss_app_t app;mock_t m;ss_link_t link;
    unsigned int variant,i;const double angles[2][2]={{45,30},{-70,-25}};
    for(variant=0U;variant<4U;++variant)for(i=0U;i<2U;++i) {
        doa_geometry_nominal(&r);
        if(variant==1U) { r.mic[0].channel=3;r.mic[3].channel=0; }
        if(variant==2U) { unsigned int row;for(row=0U;row<4U;++row){r.mic[row].xyz_mm[0]+=123.0f;r.mic[row].xyz_mm[2]-=77.0f;} }
        if(variant==3U) {r.mic[1].xyz_mm[0]+=0.3f;r.mic[2].xyz_mm[2]-=0.2f;r.provenance=DOA_GEOMETRY_MEASURED;r.position_error_mm=0.5f;}
        setup(&m,&link);m.strict_control=1;CHECK("cold init",ss_app_init(&app,&link.bus)==SS_OK);
        CHECK("cold geometry",ss_app_set_geometry(&app,&r,&report)==SS_OK && m.count==0U);
        CHECK("start",ss_app_start(&app)==SS_OK);CHECK("probe",ss_app_step(&app)==SS_APP_NONE);
        CHECK("starting",ss_app_step(&app)==SS_APP_NONE);++m.clock_ms;
        publish(&m,mapped_packet(&r,angles[i][0],angles[i][1]));
        CHECK("mapped frame",ss_app_step(&app)==SS_APP_FRAME && app.spatial_result.direction_valid && m.consumes==1U);
        CHECK("mapped az",fabs((double)app.spatial_result.azimuth_q8/256.0-angles[i][0])<0.04);
        CHECK("mapped el",fabs((double)app.spatial_result.elevation_q8/256.0-angles[i][1])<0.04);
        CHECK("no motion",m.action_writes==0U && m.permit_writes==0U);
        printf("D2_DIRECTION,variant=%u,expected=%.2f/%.2f,actual=%.6f/%.6f,SYNTHETIC\n",variant,angles[i][0],angles[i][1],(double)app.spatial_result.azimuth_q8/256.0,(double)app.spatial_result.elevation_q8/256.0);
    }
}
static void cold_only(void)
{
    ss_app_t app;mock_t m;ss_link_t link;doa_geometry_record_t r,saved;doa_geometry_report_t report,saved_report;
    doa3d_config_t saved_config;unsigned int n,before;
    setup(&m,&link);CHECK("init",ss_app_init(&app,&link.bus)==SS_OK);doa_geometry_nominal(&r);
    r.revision=12U;CHECK("install revision",ss_app_set_geometry(&app,&r,&report)==SS_OK && app.geometry.revision==12U && m.count==0U);
    saved=app.geometry;saved_report=app.geometry_report;saved_config=app.runtime.spatial_config;
    r.mic[0].channel=1;
    CHECK("invalid candidate",ss_app_set_geometry(&app,&r,&report)==SS_ARGUMENT && report.status==DOA_GEOMETRY_CHANNEL);
    CHECK("atomic keep installed",memcmp(&saved,&app.geometry,sizeof(saved))==0 && memcmp(&saved_config,&app.runtime.spatial_config,sizeof(saved_config))==0 && memcmp(&saved_report,&app.geometry_report,sizeof(saved_report))==0 && m.count==0U);
    doa_geometry_nominal(&r);
    for(n=0U;n<7U;++n) {
        CHECK("fresh app",ss_app_init(&app,&link.bus)==SS_OK);
        if(n==0U)app.runtime.link.probed=1U;
        if(n==1U)app.runtime.link.identity_verified=1U;
        if(n==2U)app.runtime.link.locked=1U;
        if(n==3U)app.runtime.link.have_consumed=1U;
        if(n==4U)app.runtime.link.recovery_required=1U;
        if(n==5U)app.runtime.recoveries=1U;
        if(n==6U)app.active=1U;
        CHECK("session state blocked",ss_app_set_geometry(&app,&r,&report)==SS_BUSY && m.count==0U);
    }
    app_setup(&m,&app);before=m.count;
    CHECK("started blocked",ss_app_set_geometry(&app,&r,&report)==SS_BUSY && m.count==before);
    publish(&m,tetra_packet(45,30,1U));m.fail_at=m.count+10U;
    CHECK("fault",ss_app_step(&app)==SS_APP_ERROR);m.fail_at=0;
    CHECK("recover",ss_app_recover(&app)==SS_OK && app.runtime.state==SS_RT_IDLE);
    before=m.count;CHECK("recover never unlocks",ss_app_set_geometry(&app,&r,&report)==SS_BUSY && m.count==before);
    /* Even empty/busy/error public bus operations permanently close setter. */
    for(n=0U;n<4U;++n) {
        setup(&m,&link);CHECK("new isolated fixture",ss_app_init(&app,&link.bus)==SS_OK);
        if(n==0U)(void)ss_app_discard(&app);
        if(n==1U)(void)ss_app_recover(&app);
        if(n==2U)(void)ss_app_ack_stop(&app);
        if(n==3U)(void)ss_app_stop(&app);
        before=m.count;CHECK("operation locks",ss_app_set_geometry(&app,&r,&report)==SS_BUSY && m.count==before);
    }
    puts("D2_COLD_CONFIG,PASS,atomic_reject,no_bus_traffic,no_recovery_unlock");
}
int main(void)
{
    geometry_tests();mapped_directions();cold_only();
    printf("D2_RESULT,%s,checks=%u,failures=%u\n",failures?"FAIL":"PASS",checks,failures);
    return failures?1:0;
}
