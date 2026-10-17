#define SS_MOTION_TEST_MAIN p2_regression_main
#include "test_ss_motion.c"
#include "ss_app.h"
static void app_fixture(motion_mock_t *m,ss_app_t *a)
{
    ss_link_t local; ss_motion_t unused;
    motion_fixture(m,&local,&unused);
    m->bus.ctrl=8U; m->bus.strict_control=1;
    CHECK("app init",ss_app_init(a,&local.bus)==SS_OK);
    CHECK("default motion closed",a->motion.config.allow_submission==0U && a->motion.state==SS_MOTION_DISARMED);
}
static void app_begin(motion_mock_t *m,ss_app_t *a)
{
    CHECK("app start",ss_app_start(a)==SS_OK);
    CHECK("probe step",ss_app_step(a)==SS_APP_NONE);
    CHECK("start step",ss_app_step(a)==SS_APP_NONE && a->runtime.state==SS_RT_RUNNING);
    m->bus.clock_ms+=1U;
}
static void run_stream(void)
{
    motion_mock_t m;ss_app_t a;unsigned int i;
    app_fixture(&m,&a);app_begin(&m,&a);
    CHECK("production arm closed",ss_app_arm(&a)==SS_ARGUMENT && m.bus.permit_writes==0U);
    for(i=1U;i<=8U;++i) {
        publish(&m.bus,packet(i!=3U,0,i));
        CHECK("app frame",ss_app_step(&a)==SS_APP_FRAME && a.frame.frame_id==i && a.fresh!=0U);
        m.bus.clock_ms+=1U;
    }
    CHECK("limit sends stop",ss_app_step(&a)==SS_APP_NONE && a.runtime.state==SS_RT_DRAINING);
    CHECK("STOP explicit disable",m.bus.ctrl==8U && m.bus.fault==64U);
    CHECK("drain ended",ss_app_step(&a)==SS_APP_ENDED && a.runtime.producer_idle_observed!=0U && a.active==0U);
    CHECK("accounting",a.frames==8U && a.rejected==1U && m.bus.consumes==8U && a.drop_count==0U);
    CHECK("no action",m.commits==0U && m.bus.action_writes==0U && m.bus.permit_writes==0U);
    CHECK("explicit ack only stop",ss_app_ack_stop(&a)==SS_OK && m.bus.fault==0U && a.runtime.state==SS_RT_IDLE);
    app_begin(&m,&a);publish(&m.bus,packet(1,0,9U));
    CHECK("new run sequence retained",ss_app_step(&a)==SS_APP_FRAME && a.frame.frame_id==9U);
    CHECK("user stop",ss_app_stop(&a)==SS_OK && a.user_stopped!=0U);
    CHECK("stop step",ss_app_step(&a)==SS_APP_NONE);
    CHECK("stop done",ss_app_step(&a)==SS_APP_ENDED);
    printf("P3_STREAM,PASS,8_frames,1_rejection,explicit_disable,STOP_only_ack,new_run_frame9,no_motion\n");
}
static void config_and_failures(void)
{
    const char *bad[]={"", "0 2000 4", "1 0 1", "1 60001 1", "4097 100 1", "1 100 0",
        "1 100 4097", "-1 20 1", "+1 20 1", "1 2", "1 2 3 4", "1 2 3x", "4294967296 2 3", "1 2\t3"};
    motion_mock_t m;ss_app_t a;ss_app_config_t c;unsigned int i,before;
    for(i=0U;i<sizeof(bad)/sizeof(bad[0]);++i) CHECK("bad config",ss_app_parse_config(bad[i],&c)==SS_ARGUMENT);
    CHECK("good config",ss_app_parse_config(" 8 2000 4 ",&c)==SS_OK && c.max_frames==8U);
    app_fixture(&m,&a);app_begin(&m,&a);
    CHECK("config busy",ss_app_configure(&a,&c)==SS_BUSY);
    CHECK("discard busy",ss_app_discard(&a)==SS_BUSY);
    CHECK("recover busy",ss_app_recover(&a)==SS_BUSY);
    CHECK("ack busy",ss_app_ack_stop(&a)==SS_BUSY);
    publish(&m.bus,packet(1,0,1U));m.bus.fail_at=m.bus.count+10U;
    CHECK("app fault",ss_app_step(&a)==SS_APP_ERROR && a.last_status==SS_IO_ERROR && a.active==0U);
    CHECK("no stale output",a.fresh==0U && zero_bytes(&a.result,sizeof(a.result)));
    before=m.bus.count;CHECK("fault quiet",ss_app_step(&a)==SS_APP_NONE && m.bus.count==before);
    m.bus.fail_at=0U;
    CHECK("recover not restart",ss_app_recover(&a)==SS_OK && a.active==0U && a.runtime.state==SS_RT_IDLE && m.bus.consumes==0U);
    CHECK("explicit discard",ss_app_discard(&a)==SS_OK && a.frame.frame_id==1U && m.bus.consumes==1U && m.commits==0U);
    /* A source fault must never be cleared with the isolated STOP helper. */
    m.bus.fault=96U; m.bus.ctrl=8U;
    CHECK("mixed fault refusal",ss_app_ack_stop(&a)==SS_DEVICE_FAULT && m.bus.fault==96U);
    app_fixture(&m,&a);c.max_frames=8U;c.duration_ms=60U;c.print_every=4U;
    CHECK("no frame config",ss_app_configure(&a,&c)==SS_OK);app_begin(&m,&a);
    for(i=0U;i<100U && a.active;++i) {m.bus.clock_ms+=5U;(void)ss_app_step(&a);}
    CHECK("no frames ends without false acceptance",a.active==0U && a.frames==0U && a.runtime.producer_idle_observed!=0U);
    app_fixture(&m,&a);m.bus.magic=0U;
    CHECK("wrong ID start",ss_app_start(&a)==SS_OK);
    CHECK("wrong ID fail",ss_app_step(&a)==SS_APP_ERROR && a.last_status==SS_IDENTITY);
    CHECK("stop fault does not hang",ss_app_stop(&a)==SS_OK && ss_app_step(&a)==SS_APP_ERROR && a.active==0U);
    puts("P3_CONFIG_RECOVERY,PASS,strict_parser,busy_gates,no_frame,wrong_ID,explicit_discard,mixed_fault_preserved");
}
static void stop_model_and_clear_matrix(void)
{
    motion_mock_t m;ss_app_t a;unsigned int before,n,total;int after,timeout;
    app_fixture(&m,&a);app_begin(&m,&a);
    CHECK("raw STOP sent",ss_stop(&a.runtime.link)==SS_OK);
    CHECK("model preserves enable on STOP",m.bus.ctrl==9U && m.stop_latched!=0);
    CHECK("enable must be explicitly cleared",ss_acknowledge_stop(&a.runtime.link)==SS_BUSY && m.bus.fault==64U);
    CHECK("explicit disable",ss_disable(&a.runtime.link)==SS_OK && m.bus.ctrl==8U);
    m.bus.status_or=UINT32_C(0x8000);
    CHECK("drain prevents ack",ss_acknowledge_stop(&a.runtime.link)==SS_BUSY && m.bus.fault==64U);
    m.bus.status_or=0U; before=m.bus.count;
    CHECK("stop ack reference",ss_acknowledge_stop(&a.runtime.link)==SS_OK && m.bus.fault==0U);
    total=m.bus.count-before;
    for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=total;++n) {
        app_fixture(&m,&a);CHECK("probe for ack",ss_probe(&a.runtime.link)==SS_OK);
        m.bus.fault=64U;m.bus.fail_at=m.bus.count+n;m.bus.fail_after=after;m.bus.timeout_error=timeout;
        CHECK("ack failure propagation",ss_acknowledge_stop(&a.runtime.link)==(timeout?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("ack failure quarantines",a.runtime.link.recovery_required!=0U && m.commits==0U);
    }
    printf("P3_STOP_ACK,PASS,latched_enable,drain_guard,fault_injections=%u\n",total*4U);
}
static void motion_owner(void)
{
    motion_mock_t m;ss_app_t a;unsigned int before;
    app_fixture(&m,&a);
    /* Test-only explicit enabling; production config is immutable and closed. */
    a.motion.config.allow_submission=1U;app_begin(&m,&a);
    CHECK("test-only motion arm",ss_app_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U));before=m.bus.count;
    CHECK("one motion owner",ss_app_step(&a)==SS_APP_FRAME && m.bus.consumes==1U && m.accepted==1U);
    CHECK("58 plus statistics, no diagnostic acquire",m.bus.count-before==59U && a.runtime.frames==0U && a.frames==1U);
    CHECK("stop disarms owner",ss_app_stop(&a)==SS_OK && a.motion.state==SS_MOTION_DISARMED);
    CHECK("stop progress",ss_app_step(&a)==SS_APP_NONE && ss_app_step(&a)==SS_APP_ENDED);
    puts("P3_OWNER,PASS,one_lock_one_consume,no_parallel_diagnostic_poll");
}
int main(void)
{
    run_stream();config_and_failures();stop_model_and_clear_matrix();
    if(ss_motion_build_enabled())motion_owner();
    printf("P3_RESULT,%s,gate=%d,checks=%u,failures=%u\n",failures==0U?"PASS":"FAIL",ss_motion_build_enabled(),checks,failures);
    return failures==0U?0:1;
}
