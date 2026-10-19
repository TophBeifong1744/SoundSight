/* Reuse the register model; production driver is compiled separately. */
#define main original_register_test_main
#include "test_fpga_link.c"
#undef main

static void mismatch(unsigned int step, uint32_t actual, uint32_t address,
                     uint32_t expected, ss_status_t result)
{
    mock_t m; ss_link_t l; ss_start_trace_t saved; uint32_t v;
    setup(&m,&l); m.mutate_at=step; m.mutate_word=actual;
    CHECK("injected result",ss_start(&l,SS_RUN_BIST_PASS)==result);
    CHECK("correct failing transaction",l.start_trace.step==step && l.start_trace.address==address);
    CHECK("successful read but rejected value",!l.start_trace.write && l.start_trace.actual_valid &&
        l.start_trace.bus_status==SS_OK && l.start_trace.actual==actual && l.start_trace.expected==expected);
    CHECK("result and capture stopped",l.start_trace.result==result && !l.start_trace.active);
    CHECK("no added diagnostic bus requests",m.count==step+(result==SS_BUSY?0U:1U));
    saved=l.start_trace;
    if(result!=SS_BUSY) {
        unsigned int before=m.count;
        CHECK("read rejected while isolated",ss_read_register(&l,0x64U,&v)==SS_RECOVERY_REQUIRED && v==0U);
        CHECK("no hardware zero claimed",m.count==before);
        CHECK("protected trace unchanged",memcmp(&saved,&l.start_trace,sizeof(saved))==0);
        CHECK("recovery works",ss_recover(&l)==SS_OK);
        CHECK("recovery preserves trace",memcmp(&saved,&l.start_trace,sizeof(saved))==0);
    }
    CHECK("no movement",m.action_writes==0U && m.permit_writes==0U);
}
int main(void)
{
    static const uint32_t addresses[13]={4,4,4,0x34,0x64,0x58,0x60,0x2c,0x2c,4,4,4,4};
    static const unsigned char writes[13]={0,1,0,0,0,1,1,1,0,1,0,1,0};
    unsigned int i,after,timeout; mock_t m;ss_link_t l;
    mismatch(1,0,4,8,SS_WIRE_FORMAT);
    mismatch(3,9,4,8,SS_DEVICE_FAULT);
    mismatch(4,0x10040,0x34,0x10000,SS_WIRE_FORMAT);
    mismatch(4,0x10002,0x34,0x10000,SS_BUSY);
    mismatch(5,2,0x64,0,SS_DEVICE_FAULT);
    mismatch(9,0,0x2c,1,SS_DEVICE_FAULT);
    mismatch(11,8,4,10,SS_DEVICE_FAULT);
    mismatch(13,10,4,11,SS_DEVICE_FAULT);
    for(i=1;i<=13U;++i) for(after=0;after<2U;++after) for(timeout=0;timeout<2U;++timeout) {
        ss_status_t e=timeout?SS_TIMEOUT:SS_IO_ERROR;
        setup(&m,&l);m.fail_at=i;m.fail_after=(int)after;m.timeout_error=(int)timeout;
        CHECK("transport error unchanged",ss_start(&l,SS_RUN_BIST_PASS)==e);
        CHECK("transport trace exact",l.start_trace.step==i && l.start_trace.address==addresses[i-1U] &&
            l.start_trace.write==writes[i-1U] && l.start_trace.bus_status==e && l.start_trace.result==e);
        CHECK("failed read has no valid value",!l.start_trace.actual_valid && l.start_trace.actual==0U);
        CHECK("trace frozen before revoke",!l.start_trace.active && l.recovery_required && m.count==i+1U);
        CHECK("no movement writes",m.action_writes==0U && m.permit_writes==0U);
    }
    setup(&m,&l);
    CHECK("BIST success unchanged",ss_start(&l,SS_RUN_BIST_PASS)==SS_OK);
    CHECK("success uses 13 transfers",m.count==13U && l.start_trace.step==13U &&
        l.start_trace.expected==11U && l.start_trace.actual==11U && l.start_trace.actual_valid && !l.start_trace.active);
    setup(&m,&l);
    CHECK("real mode unchanged",ss_start(&l,SS_RUN_REAL)==SS_OK && m.count==11U);
    CHECK("real enable readback",l.start_trace.step==11U && l.start_trace.expected==9U && l.start_trace.actual==9U);
    CHECK("invalid mode no stale capture",ss_start(&l,(ss_run_t)99)==SS_ARGUMENT && l.start_trace.step==0U && !l.start_trace.actual_valid);
    printf("START_TRACE_RESULT,%s,checks=%u,failures=%u,readback_cases=8,transport_cases=52\n",failures?"FAIL":"PASS",checks,failures);
    return failures?1:0;
}
