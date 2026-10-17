/* Reuse the literal-address peripheral model, not a second fake S2 API.
 * The original S2 regression runs separately; renamed main is not called here. */
#define main s2_register_regression_main
#include "test_fpga_link.c"
#undef main
#include "ss_runtime.h"

static void fixture(mock_t *m, ss_runtime_t *r)
{
    ss_bus_t b;
    ss_runtime_config_t c = {10U, 200U, 100U};
    memset(m, 0, sizeof(*m)); memset(r, 0, sizeof(*r));
    m->magic=UINT32_C(0x5A5A2026); m->version=UINT32_C(0x10000);
    m->ctrl=8U; m->duration_ms=1U;
    b.user=m; b.transfer=transfer; b.now_ms=now_ms;
    b.transfer_timeout_ms=5U; b.operation_timeout_ms=100U;
    CHECK("runtime init", ss_runtime_init(r,&b,&c)==SS_OK);
    CHECK("init no bus",m->count==0U && r->state==SS_RT_IDLE);
}
static void begin(mock_t *m, ss_runtime_t *r, ss_run_t mode)
{
    unsigned int before=m->count;
    CHECK("start accepted",ss_runtime_start(r,mode)==SS_OK);
    CHECK("request no I/O",m->count==before);
    CHECK("probe state",ss_runtime_step(r)==SS_RT_STATE_CHANGED && r->state==SS_RT_STARTING);
    CHECK("running state",ss_runtime_step(r)==SS_RT_STATE_CHANGED && r->state==SS_RT_RUNNING);
}
static void safe_bus(mock_t *m)
{
    unsigned int i;
    CHECK("never actuate or permit",m->action_writes==0U && m->permit_writes==0U);
    CHECK("no bad bus requests",m->bad_tx==0U);
    for(i=0U;i<m->transcript_count;++i) {
        uint8_t a=m->transcript[i][0];
        if(a==UINT8_C(0xD8))
            CHECK("only STOP/revoke control",load32(&m->transcript[i][1])==2U || load32(&m->transcript[i][1])==4U);
        if(a==UINT8_C(0xE0)) CHECK("watchdog always zero",load32(&m->transcript[i][1])==0U);
    }
}
static void advance(mock_t *m, ss_runtime_t *r) { m->clock_ms+=r->config.poll_interval_ms; }
static void rt_bist_and_source(void)
{
    mock_t m; ss_runtime_t r; unsigned int i,before;
    for(i=0U;i<2U;++i) {
        fixture(&m,&r); begin(&m,&r,i==0U?SS_RUN_BIST_REJECT:SS_RUN_BIST_PASS);
        before=m.count;
        CHECK("BIST event",ss_runtime_step(&r)==(i==0U?SS_RT_FRAME_REJECTED:SS_RT_FRAME_VALID));
        CHECK("guard plus frozen 40",m.count-before==41U);
        CHECK("BIST exact result",r.result.ux_q20==(i==0U?46831:749295) &&
              r.result.uy_q20==(i==0U?-171729:0) && r.result.direction_reason==(i==0U?3:0));
        CHECK("BIST residual",r.result.residual_square_q24==(i==0U?UINT64_C(590912626):UINT64_C(0)));
        CHECK("one consume",m.consumes==1U && r.frames==1U && r.fresh_result!=0U);
        CHECK("no servo mapping",r.result.servo_cmd_valid==0U);
        printf("P1_BIST,%s,transfers=%u,ux=%" PRId32 ",uy=%" PRId32
               ",residual=%" PRIu64 ",valid=%u,reason=%d,consumes=%u\n",i==0U?"REJECT":"PASS",m.count-before,
               r.result.ux_q20,r.result.uy_q20,r.result.residual_square_q24,(unsigned int)r.result.direction_valid,
               (int)r.result.direction_reason,m.consumes);
        before=m.count;
        CHECK("throttled next step",ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
        CHECK("fresh output expires",r.fresh_result==0U && zero_bytes(&r.result,sizeof(r.result)));
        advance(&m,&r);
        CHECK("empty waits",ss_runtime_step(&r)==SS_RT_NONE && r.state==SS_RT_RUNNING && r.empty_polls==1U);
        safe_bus(&m);
    }
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL);
    for(i=1U;i<=4U;++i) {
        packet_t p=packet(i!=2U,0,i);
        if(i==3U) p.flags|=UINT32_C(0x01100000);
        if(i==4U) p.flags|=UINT32_C(0x07000000);
        publish(&m,p); advance(&m,&r);
        CHECK("stream events",ss_runtime_step(&r)==(i==1U?SS_RT_FRAME_VALID:SS_RT_FRAME_REJECTED));
        CHECK("same frame",r.frame.frame_id==i && r.result.frame_id==i);
        CHECK("rejections consumed once",m.consumes==i && r.frames==i);
        if(i==3U) CHECK("cancel reason",r.result.direction_reason==DOA_CANCELLED);
        if(i==4U) CHECK("source reason",r.result.direction_reason==DOA_SOURCE_ERROR && r.result.first_error_code==7U);
    }
    CHECK("rejection count",r.rejected_frames==3U && r.errors==0U);
    publish(&m,packet(1,0,4U)); advance(&m,&r);
    CHECK("stale frame fault",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_STALE_FRAME && m.consumes==4U);
    CHECK("recover stale accepted",ss_runtime_recover(&r)==SS_OK);
    CHECK("recover host only",ss_runtime_step(&r)==SS_RT_STATE_CHANGED && r.state==SS_RT_IDLE);
    CHECK("watermark retained",r.link.have_consumed!=0U && r.link.last_consumed_id==4U);
    CHECK("explicit resume",ss_runtime_resume(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    CHECK("stale stays rejected after recovery",ss_runtime_step(&r)==SS_RT_ERROR && m.consumes==4U);
    safe_bus(&m);
    puts("P1_STREAM,PASS,valid/residual/cancel/source_error,stale_after_recovery,no_motion");
}
static void rt_fault_matrix(void)
{
    unsigned int n; int after,timeout;
    for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=41U;++n) {
        mock_t m; ss_runtime_t r; unsigned int before,consumed;
        fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); publish(&m,packet(1,0,1U));
        m.fail_at=m.count+n; m.fail_after=after; m.timeout_error=timeout;
        CHECK("runtime error event",ss_runtime_step(&r)==SS_RT_ERROR && r.state==SS_RT_FAULT);
        CHECK("error classified",r.last_error==(timeout!=0?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("failure clears output",r.fresh_result==0U && zero_bytes(&r.frame,sizeof(r.frame)) && zero_bytes(&r.result,sizeof(r.result)));
        consumed=n==41U && after!=0?1U:0U;
        CHECK("ambiguous effect only once",m.consumes==consumed);
        before=m.count;
        CHECK("fault step quiet",ss_runtime_step(&r)==SS_RT_NONE && ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
        CHECK("cannot auto start or resume",ss_runtime_start(&r,SS_RUN_REAL)==SS_BUSY && ss_runtime_resume(&r)==SS_BUSY);
        m.fail_at=0U;
        CHECK("recover explicit no I/O",ss_runtime_recover(&r)==SS_OK && m.count==before);
        CHECK("recover to idle",ss_runtime_step(&r)==SS_RT_STATE_CHANGED && r.state==SS_RT_IDLE);
        CHECK("recover never consumes",m.consumes==consumed && r.recoveries==1U);
        CHECK("error history retained",r.first_error==(timeout!=0?SS_TIMEOUT:SS_IO_ERROR));
        before=m.count; CHECK("idle never polls",ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
        CHECK("resume explicit",ss_runtime_resume(&r)==SS_OK);
        CHECK("resume readback",ss_runtime_step(&r)==SS_RT_STATE_CHANGED && r.state==SS_RT_RUNNING);
        CHECK("no hidden restart",m.ctrl==9U);
        CHECK("resume expected frame",ss_runtime_step(&r)==(consumed!=0U?SS_RT_NONE:SS_RT_FRAME_VALID));
        CHECK("exactly one device consume",m.consumes==1U);
        if(consumed!=0U) CHECK("ambiguous result not reconstructed",r.frames==0U && r.fresh_result==0U);
        safe_bus(&m);
    }
    puts("P1_FAULT_MATRIX,PASS,41_positions_x_before_after_x_IO_timeout=164,no_blind_consume_retry");
}
static void rt_stop(void)
{
    mock_t m; ss_runtime_t r; unsigned int before;
    fixture(&m,&r);
    CHECK("stop unknown host",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    CHECK("unknown not confirmed",r.state==SS_RT_STOPPED && r.producer_idle_observed==0U && m.count==0U);
    begin(&m,&r,SS_RUN_REAL); publish(&m,packet(1,0,1U));
    CHECK("queue preserved on stop request",ss_runtime_stop(&r)==SS_OK);
    CHECK("stop sent",ss_runtime_step(&r)==SS_RT_STATE_CHANGED && r.stop_sent!=0U && r.state==SS_RT_DRAINING);
    before=m.count; m.status_or=UINT32_C(0x8000);
    CHECK("repeat stop no transition",ss_runtime_stop(&r)==SS_OK && m.count==before && r.state==SS_RT_DRAINING);
    CHECK("drain waits",ss_runtime_step(&r)==SS_RT_NONE && r.producer_idle_observed==0U);
    m.status_or=0U; advance(&m,&r);
    CHECK("producer idle readback",ss_runtime_step(&r)==SS_RT_STATE_CHANGED && r.state==SS_RT_STOPPED && r.producer_idle_observed!=0U);
    CHECK("no flush",m.consumes==0U && m.releases==0U && m.slot[0].state==1);
    before=m.count; CHECK("stopped quiet",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
    CHECK("recover stop fault request",ss_runtime_recover(&r)==SS_OK);
    CHECK("sticky stop stays fault",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_DEVICE_FAULT && m.fault==64U);
    CHECK("stop disallows resume",ss_runtime_resume(&r)==SS_BUSY);
    safe_bus(&m);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL);
    CHECK("stop deadline request",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    m.status_or=UINT32_C(0x8000); CHECK("still draining",ss_runtime_step(&r)==SS_RT_NONE);
    m.clock_ms=r.state_since_ms+r.config.drain_timeout_ms;
    CHECK("drain timeout",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_TIMEOUT && r.producer_idle_observed==0U);
    before=m.count; CHECK("failed stop not replayed",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL);
    m.fail_at=m.count+1U; CHECK("force transport fault",ss_runtime_step(&r)==SS_RT_ERROR);
    m.fail_at=0U; CHECK("stop in quarantine queued",ss_runtime_stop(&r)==SS_OK);
    CHECK("stop sent but unconfirmed",ss_runtime_step(&r)==SS_RT_ERROR && r.stop_sent!=0U && r.producer_idle_observed==0U && r.state==SS_RT_FAULT);
    safe_bus(&m);
    puts("P1_STOP,PASS,host_vs_producer_confirmation,drain_timeout,sticky_fault,backlog_retained");
}
static void rt_boundaries(void)
{
    mock_t m; ss_runtime_t r; unsigned int before; packet_t p;
    fixture(&m,&r); m.magic=0U;
    CHECK("wrong ID start request",ss_runtime_start(&r,SS_RUN_REAL)==SS_OK);
    CHECK("wrong ID fault no writes",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_IDENTITY && m.count==1U);
    CHECK("unknown stop",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_ERROR && m.count==1U);
    m.magic=UINT32_C(0x5A5A2026);
    CHECK("identity explicit recovery",ss_runtime_recover(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    CHECK("not a previously started session",ss_runtime_resume(&r)==SS_BUSY);
    begin(&m,&r,SS_RUN_REAL); safe_bus(&m);
    fixture(&m,&r); m.clock_ms=UINT32_MAX-15U; begin(&m,&r,SS_RUN_REAL);
    CHECK("no frame at wrap",ss_runtime_step(&r)==SS_RT_NONE);
    before=m.count; m.clock_ms+=9U;
    CHECK("poll not due",ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
    ++m.clock_ms; CHECK("poll due",ss_runtime_step(&r)==SS_RT_NONE && m.count==before+3U);
    r.frames=UINT32_MAX; publish(&m,packet(1,0,1U)); advance(&m,&r);
    CHECK("counter saturates",ss_runtime_step(&r)==SS_RT_FRAME_VALID && r.frames==UINT32_MAX);
    CHECK("invalid command clears result",ss_runtime_start(&r,(ss_run_t)99)==SS_ARGUMENT && r.fresh_result==0U);
    fixture(&m,&r); publish(&m,packet(1,0,1U));
    CHECK("busy start",ss_runtime_start(&r,SS_RUN_BIST_PASS)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    CHECK("busy preserves backlog/mode",ss_runtime_step(&r)==SS_RT_NONE && r.state==SS_RT_STARTING && m.bist==0U && m.slot[0].state==1);
    m.clock_ms=r.state_since_ms+r.config.start_timeout_ms;
    CHECK("startup deadline",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_TIMEOUT && m.consumes==0U);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); publish(&m,packet(1,0,1U)); m.fault=8U;
    before=m.count;
    CHECK("fault checked before acquire",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_DEVICE_FAULT && m.count==before+1U && m.acquires==0U);
    CHECK("sticky recovery remains fault",ss_runtime_recover(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_ERROR && m.fault==8U);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); p=packet(1,0,1U); p.word[0][0]^=UINT32_C(0x100); publish(&m,p);
    CHECK("bad echo faults",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_WIRE_FORMAT && m.consumes==0U);
    CHECK("release failure recover",ss_runtime_recover(&r)==SS_OK); m.ignore_release=1;
    CHECK("stuck slot rejected",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_DEVICE_FAULT);
    CHECK("original error retained",r.first_error==SS_WIRE_FORMAT);
    fixture(&m,&r); begin(&m,&r,SS_RUN_BIST_PASS); m.fail_at=m.count+1U;
    CHECK("BIST fault",ss_runtime_step(&r)==SS_RT_ERROR); m.fail_at=0U;
    CHECK("BIST recover",ss_runtime_recover(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    m.bist=0U; CHECK("resume request",ss_runtime_resume(&r)==SS_OK);
    CHECK("resume cannot change BIST",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_DEVICE_FAULT && m.bist==0U);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); m.fail_at=m.count+1U;
    CHECK("real fault",ss_runtime_step(&r)==SS_RT_ERROR); m.fail_at=0U;
    CHECK("real recovery",ss_runtime_recover(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    m.ctrl=8U; CHECK("disabled resume request",ss_runtime_resume(&r)==SS_OK);
    CHECK("resume cannot reenable",ss_runtime_step(&r)==SS_RT_ERROR && m.ctrl==8U);
    safe_bus(&m);
    CHECK("null API",ss_runtime_init(NULL,NULL,NULL)==SS_ARGUMENT && ss_runtime_start(NULL,SS_RUN_REAL)==SS_ARGUMENT &&
          ss_runtime_stop(NULL)==SS_ARGUMENT && ss_runtime_recover(NULL)==SS_ARGUMENT &&
          ss_runtime_resume(NULL)==SS_ARGUMENT && ss_runtime_step(NULL)==SS_RT_ERROR);
    fixture(&m,&r);
    { ss_runtime_config_t c={0U,1U,1U}; ss_bus_t b=r.link.bus;
      CHECK("zero interval rejected",ss_runtime_init(&r,&b,&c)==SS_ARGUMENT);
      CHECK("invalid context cannot step",ss_runtime_step(&r)==SS_RT_ERROR);
      c.poll_interval_ms=UINT32_C(0x80000000);
      CHECK("half range rejected",ss_runtime_init(&r,&b,&c)==SS_ARGUMENT); }
    puts("P1_BOUNDARIES,PASS,identity,wrap,throttle,saturation,busy,deadline,fault,wire,explicit_resume");
}
static void lifecycle_setup(mock_t *m, ss_runtime_t *r, unsigned int phase)
{
    fixture(m,r);
    if(phase<=1U) {
        CHECK("lifecycle start request",ss_runtime_start(r,SS_RUN_BIST_PASS)==SS_OK);
        if(phase==1U) CHECK("lifecycle probe",ss_runtime_step(r)==SS_RT_STATE_CHANGED);
        return;
    }
    begin(m,r,SS_RUN_BIST_PASS);
    if(phase<=3U) {
        CHECK("lifecycle stop request",ss_runtime_stop(r)==SS_OK);
        if(phase==3U) CHECK("lifecycle stop send",ss_runtime_step(r)==SS_RT_STATE_CHANGED);
        return;
    }
    m->fail_at=m->count+6U;
    CHECK("lifecycle lock error",ss_runtime_step(r)==SS_RT_ERROR);
    m->fail_at=0U;
    CHECK("lifecycle recovery request",ss_runtime_recover(r)==SS_OK);
    if(phase==5U) {
        CHECK("lifecycle recovery",ss_runtime_step(r)==SS_RT_STATE_CHANGED);
        CHECK("lifecycle resume request",ss_runtime_resume(r)==SS_OK);
    }
}
static void rt_lifecycle_faults(void)
{
    unsigned int phase, total=0U;
    for(phase=0U;phase<6U;++phase) {
        mock_t m; ss_runtime_t r; unsigned int before,n,transfers; int after,timeout;
        lifecycle_setup(&m,&r,phase); before=m.count;
        CHECK("reference lifecycle success",ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
        transfers=m.count-before;
        for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=transfers;++n) {
            lifecycle_setup(&m,&r,phase);
            m.fail_at=m.count+n; m.fail_after=after; m.timeout_error=timeout;
            CHECK("lifecycle fault",ss_runtime_step(&r)==SS_RT_ERROR && r.state==SS_RT_FAULT);
            CHECK("lifecycle error classification",r.last_error==(timeout!=0?SS_TIMEOUT:SS_IO_ERROR));
            CHECK("lifecycle no consume",m.consumes==0U && r.fresh_result==0U && r.producer_idle_observed==0U);
            before=m.count;
            CHECK("lifecycle no retry",ss_runtime_step(&r)==SS_RT_NONE && m.count==before);
            safe_bus(&m); ++total;
        }
    }
    printf("P1_LIFECYCLE_FAULTS,PASS,cases=%u,probe/start/stop/drain/recover/resume\n",total);
}
static void rt_queue_and_budgets(void)
{
    mock_t m; ss_runtime_t r; unsigned int before;
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL);
    publish(&m,packet(1,0,1U)); publish(&m,packet(1,0,2U));
    CHECK("IRQ initially asserted",(status(&m)&UINT32_C(0x4000))!=0U);
    CHECK("queue first",ss_runtime_step(&r)==SS_RT_FRAME_VALID && r.frame.frame_id==1U);
    CHECK("IRQ remains asserted",(status(&m)&UINT32_C(0x4000))!=0U);
    advance(&m,&r);
    CHECK("queue second without edge",ss_runtime_step(&r)==SS_RT_FRAME_VALID && r.frame.frame_id==2U && m.consumes==2U);
    CHECK("idle queue deasserts IRQ",(status(&m)&UINT32_C(0x4000))==0U);
    publish(&m,packet(1,0,3U)); r.link.bus.operation_timeout_ms=10U; advance(&m,&r);
    CHECK("frame budget expires",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_TIMEOUT && m.consumes==2U);
    CHECK("partial result never published",zero_bytes(&r.result,sizeof(r.result)));
    fixture(&m,&r); m.clock_ms=UINT32_MAX-10U;
    CHECK("wrap start queued",ss_runtime_start(&r,SS_RUN_REAL)==SS_OK);
    CHECK("wrap probe",ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    m.status_or=UINT32_C(0x8000);
    CHECK("wrap busy",ss_runtime_step(&r)==SS_RT_NONE);
    m.clock_ms=r.state_since_ms+r.config.start_timeout_ms;
    CHECK("wrap deadline",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_TIMEOUT);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); m.duration_ms=6U;
    CHECK("late callback rejected",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_TIMEOUT);
    CHECK("failed revoke visible",r.link.revoke_result==SS_TIMEOUT);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL);
    CHECK("drain malformed setup",ss_runtime_stop(&r)==SS_OK && ss_runtime_step(&r)==SS_RT_STATE_CHANGED);
    m.status_or=UINT32_C(0x40);
    CHECK("drain reserved bit not accepted",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_WIRE_FORMAT);
    fixture(&m,&r); begin(&m,&r,SS_RUN_REAL); m.fault=UINT32_C(0x1000); before=m.count;
    CHECK("fault reserved bits",ss_runtime_step(&r)==SS_RT_ERROR && r.last_error==SS_WIRE_FORMAT && m.count==before+1U);
    safe_bus(&m);
    puts("P1_QUEUE_BUDGETS,PASS,continuous_IRQ,whole_frame_timeout,wrap_deadline,late_callback,reserved_bits");
}
int main(void)
{
    rt_bist_and_source(); rt_fault_matrix(); rt_stop(); rt_boundaries();
    rt_lifecycle_faults(); rt_queue_and_budgets();
    printf("P1_RESULT,%s,checks=%u,failures=%u\n",failures==0U?"PASS":"FAIL",checks,failures);
    return failures==0U?0:1;
}
