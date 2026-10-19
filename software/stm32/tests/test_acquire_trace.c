#define main original_register_test_main
#include "test_fpga_link.c"
#undef main

static unsigned int format_cases;
static void rejected(unsigned int mutate_step,uint32_t value,unsigned int fail_step,
                     ss_acquire_check_t check,unsigned int pair,uint32_t address,
                     uint32_t recorded)
{
    mock_t m;ss_link_t l;doa_frame_input_t f;ss_acquire_trace_t saved;
    setup(&m,&l);publish(&m,packet(1,1,1U));
    m.mutate_at=mutate_step;m.mutate_word=value;
    memset(&f,0xA5,sizeof(f));
    CHECK("format rejection",ss_acquire_frame(&l,&f)==SS_WIRE_FORMAT);
    CHECK("no partial frame",zero_bytes(&f,sizeof(f)));
    CHECK("specific check",l.acquire_trace.check==(uint8_t)check);
    CHECK("exact address pair word",l.acquire_trace.address==address &&
          l.acquire_trace.pair==pair && l.acquire_trace.word==recorded);
    CHECK("raw snapshot retained",l.acquire_trace.snapshot==(mutate_step==2U?value:UINT32_C(0x17F39)));
    CHECK("frame known only after read",l.acquire_trace.frame_id==(fail_step>3U?1U:0U));
    CHECK("no extra transactions except revoke",m.count==fail_step+1U);
    CHECK("isolated no consume or motion",l.recovery_required && m.consumes==0U &&
          m.action_writes==0U && m.permit_writes==0U);
    saved=l.acquire_trace;
    CHECK("repeat acquire blocked",ss_acquire_frame(&l,&f)==SS_RECOVERY_REQUIRED);
    CHECK("isolation preserves first failure",memcmp(&saved,&l.acquire_trace,sizeof(saved))==0);
    CHECK("recover",ss_recover(&l)==SS_OK);
    CHECK("recovery preserves trace",memcmp(&saved,&l.acquire_trace,sizeof(saved))==0);
    CHECK("new attempt succeeds",ss_acquire_frame(&l,&f)==SS_OK);
    CHECK("new attempt clears old error",l.acquire_trace.check==0U && f.frame_id==1U);
    ++format_cases;
}
int main(void)
{
    const uint32_t st=UINT32_C(0x17F39);
    const uint32_t addresses[4]={0x10U,0x20U,0x24U,0x28U};
    unsigned int i,j,step,after,timeout;
    mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t out;
    doa_servo_config_t cfg=servo_config();packet_t p=packet(1,1,1U);
    rejected(2,st|0x40U,2,SS_ACQ_STATUS_RESERVED,255,0x34,st|0x40U);
    rejected(2,st&~UINT32_C(0x10000),2,SS_ACQ_PROFILE,255,0x34,st&~UINT32_C(0x10000));
    rejected(2,st&~UINT32_C(0x10),2,SS_ACQ_TERMINAL,255,0x34,st&~UINT32_C(0x10));
    rejected(2,st&~UINT32_C(8),2,SS_ACQ_ENERGY,255,0x34,st&~UINT32_C(8));
    for(i=0;i<6U;++i) {
        uint32_t w=p.word[i][0]; unsigned int n=5U+6U*i;
        rejected(n,w|UINT32_C(0x800000),n,SS_ACQ_FEATURE_RESERVED,i,0x0C,w|UINT32_C(0x800000));
        rejected(n,w^UINT32_C(0x100),n,SS_ACQ_PAIR,i,0x0C,w^UINT32_C(0x100));
        for(j=0;j<2U;++j) {
            uint32_t ph=(w&UINT32_C(0xF0FFFFFF))|(j?UINT32_C(0x07000000):0U);
            uint32_t iff=(w&UINT32_C(0x0FFFFFFF))|(j?UINT32_C(0x70000000):0U);
            uint32_t lag=(w&UINT32_C(0xFFFFFF00))|(j?UINT32_C(0xDF):UINT32_C(0x20));
            rejected(n,ph,n,SS_ACQ_PHAT_STAGE,i,0x0C,ph);
            rejected(n,iff,n,SS_ACQ_IFFT_STAGE,i,0x0C,iff);
            rejected(n,lag,n,SS_ACQ_LAG,i,0x0C,lag);
        }
        w=(w&UINT32_C(0xFF80FFFF))|UINT32_C(0x00500000);
        rejected(n,w,n,SS_ACQ_MASK_COUNT,i,0x0C,w);
        for(j=0;j<4U;++j) {
            rejected(n+1U+j,UINT32_C(0x01000000),n+1U+j,SS_ACQ_S25,i,addresses[j],UINT32_C(0x01000000));
            rejected(n+1U+j,UINT32_C(0xFEFFFFFF),n+1U+j,SS_ACQ_S25,i,addresses[j],UINT32_C(0xFEFFFFFF));
        }
    }
    rejected(2,st^UINT32_C(0x100),39,SS_ACQ_VALID_PAIRS,255,0x34,0x3FU);
    for(step=1U;step<=39U;++step) for(after=0U;after<2U;++after) for(timeout=0U;timeout<2U;++timeout) {
        setup(&m,&l);publish(&m,p);m.fail_at=step;m.fail_after=(int)after;m.timeout_error=(int)timeout;
        CHECK("transport result unchanged",ss_acquire_frame(&l,&f)==(timeout?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("no fabricated format diagnosis",l.acquire_trace.check==0U);
        CHECK("transport failure bounded",m.count==step+1U && l.recovery_required);
        CHECK("no partial output or consume",zero_bytes(&f,sizeof(f)) && m.consumes==0U);
    }
    setup(&m,&l);
    CHECK("empty queue",ss_acquire_frame(&l,&f)==SS_NO_FRAME && m.count==2U && !l.acquire_trace.check);
    publish(&m,p);m.count=0U;
    CHECK("successful acquisition",ss_acquire_frame(&l,&f)==SS_OK && m.count==39U && !l.acquire_trace.check);
    CHECK("busy no transfers",ss_acquire_frame(&l,&f)==SS_BUSY && m.count==39U && !l.acquire_trace.check);
    CHECK("release",ss_finish_frame(&l,SS_RELEASE)==SS_OK);
    m.count=0U;
    CHECK("successful solve unchanged",ss_poll_solve(&l,&cfg,&f,&out)==SS_OK && m.count==40U && out.direction_valid);
    setup(&m,&l);publish(&m,p);m.mutate_at=5U;m.mutate_word=p.word[0][0]^UINT32_C(0x100);
    CHECK("poll solve retains diagnosis",ss_poll_solve(&l,&cfg,&f,&out)==SS_WIRE_FORMAT && l.acquire_trace.check==SS_ACQ_PAIR);
    CHECK("poll solve clears outputs",zero_bytes(&f,sizeof(f)) && zero_bytes(&out,sizeof(out)));
    printf("ACQUIRE_TRACE_RESULT,%s,checks=%u,failures=%u,format_cases=%u,transport_cases=156\n",
           failures?"FAIL":"PASS",checks,failures,format_cases);
    return failures?1:0;
}
