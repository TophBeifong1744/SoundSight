#define main s2_model_regression_main
#include "test_fpga_link.c"
#undef main
#include "ss_motion.h"
#include "../src/fpga_link_internal.h"

/* Extend the existing literal-register model with a separate actuator model.
 * Not RTL/PWM simulation. accepted below is model truth, not a wire receipt. */
typedef struct {
    mock_t bus;
    uint32_t shadow, last_accepted, remaining, tick_ms;
    unsigned int commits, accepted, watchdog_loads, nonzero_watchdog_writes;
    unsigned int drop_permit_at, fault_at, ignore_commit, bad_shadow;
    int bound, have_command, stop_latched;
} motion_mock_t;
static void tick(motion_mock_t *m)
{
    uint32_t elapsed=m->bus.clock_ms-m->tick_ms;
    uint64_t ticks=(uint64_t)elapsed*UINT64_C(61440);
    m->tick_ms=m->bus.clock_ms;
    if(m->bus.act!=0U && m->have_command!=0) {
        if(ticks >= m->remaining) {
            m->remaining=0U; m->bus.act=0U; m->have_command=0; m->bus.fault|=256U;
        } else m->remaining-=(uint32_t)ticks;
    }
}
static void motion_write(motion_mock_t *m,uint32_t a,uint32_t v)
{
    mock_t *b=&m->bus;
    if(a==0x18U) {
        ++b->action_writes;
        if((v&UINT32_C(0xFFF80000))!=0U) { b->fault|=2U; return; }
        m->shadow=m->bad_shadow!=0U ? v^1U : v;
    } else if(a==0x60U) {
        if(b->act!=0U) { b->fault|=2U; return; }
        if(v!=0U) ++m->nonzero_watchdog_writes;
        b->watchdog=v;
        if(v==0U) { b->act=0U; m->have_command=0; }
    } else if(a==0x58U) {
        if(v==0U || (v&6U)!=0U) {
            b->act=0U; m->have_command=0; m->remaining=0U;
            if((v&2U)!=0U) { m->stop_latched=1; b->fault|=64U; }
        } else if(v==1U) {
            ++b->permit_writes;
            if(b->ctrl==9U && b->fault==0U && b->watchdog!=0U && m->bound && !m->stop_latched)
                b->act=1U;
            else { b->fault|=128U; b->act=0U; }
        } else if(v==8U) {
            int k=locked(b); unsigned int i,q=0U;
            ++m->commits;
            if(m->ignore_commit!=0U) return; /* Deliberately silent lost write. */
            if(k>=0) for(i=0U;i<6U;++i) {
                uint32_t w=b->slot[k].data.word[i][0];
                if((w&UINT32_C(0xFF00E800))==UINT32_C(0x11002800) && ((w>>16)&127U)>=12U) ++q;
            }
            if(b->act==1U && b->ctrl==9U && b->fault==0U && m->bound && !m->stop_latched &&
               b->watchdog!=0U && k>=0 && q>=3U &&
               (b->slot[k].data.flags&UINT32_C(0xFF100018))==16U &&
               b->slot[k].data.id!=0U && b->slot[k].data.id!=m->last_accepted &&
               (m->shadow&UINT32_C(0xC0000))==UINT32_C(0x40000) &&
               (m->shadow&511U)<=180U && (b->status_or&UINT32_C(0x8000))==0U) {
                ++m->accepted; m->last_accepted=b->slot[k].data.id;
                m->remaining=b->watchdog; m->have_command=1; ++m->watchdog_loads;
            } else { b->fault|=128U; b->act=0U; }
        } else { ++b->bad_tx; b->fault|=2U; }
    } else write_word(b,a,v);
    if(b->fault!=0U) { b->act=0U; m->have_command=0; }
}
static ss_bus_status_t motion_transfer(void *user,const uint8_t tx[5],uint8_t rx[5],uint32_t timeout)
{
    motion_mock_t *m=(motion_mock_t *)user; mock_t *b=&m->bus;
    uint32_t a=(uint32_t)(tx[0]&127U),v; int fail_now;
    ++b->count;
    CHECK("bounded adapter timeout",timeout>0U && timeout<=5U);
    if(b->transcript_count<512U) memcpy(b->transcript[b->transcript_count++],tx,5U);
    b->clock_ms+=b->duration_ms; tick(m);
    if(b->count==m->drop_permit_at) { b->act=0U; m->have_command=0; }
    if(b->count==m->fault_at) { b->fault|=16U; b->act=0U; }
    fail_now=b->count==b->fail_at;
    memset(rx,0,5U);
    if(fail_now && b->fail_after==0) return b->timeout_error ? SS_BUS_TIMEOUT : SS_BUS_ERROR;
    if((tx[0]&128U)!=0U) motion_write(m,a,load32(&tx[1]));
    else {
        CHECK("read payload zero",load32(&tx[1])==0U);
        v=a==0x18U ? m->shadow : read_word(b,a);
        if(a==0x34U && m->bound) v|=UINT32_C(0x80000);
        if(b->count==b->mutate_at) v=b->mutate_word;
        store32(&rx[1],v);
    }
    if(fail_now) return b->timeout_error ? SS_BUS_TIMEOUT : SS_BUS_ERROR;
    return SS_BUS_OK;
}
static uint32_t motion_now(void *user) { return ((motion_mock_t *)user)->bus.clock_ms; }
static void motion_fixture(motion_mock_t *m,ss_link_t *l,ss_motion_t *a)
{
    ss_bus_t b; ss_motion_config_t c;
    memset(m,0,sizeof(*m)); memset(a,0,sizeof(*a));
    m->bus.magic=UINT32_C(0x5A5A2026); m->bus.version=UINT32_C(0x10000);
    m->bus.ctrl=8U; m->bus.duration_ms=1U; m->bound=1;
    b.user=m; b.transfer=motion_transfer; b.now_ms=motion_now;
    b.transfer_timeout_ms=5U; b.operation_timeout_ms=200U;
    CHECK("link init",ss_init(l,&b)==SS_OK);
    CHECK("link probe",ss_probe(l)==SS_OK);
    CHECK("start real",ss_start(l,SS_RUN_REAL)==SS_OK);
    c.servo=servo_config(); c.watchdog_ticks=UINT32_C(6144000);
    c.max_frame_hold_ms=120U; c.allow_submission=1U;
    CHECK("motion init",ss_motion_init(a,l,&c)==SS_OK);
    CHECK("default disarmed",a->state==SS_MOTION_DISARMED && m->bus.act==0U);
    m->bus.count=0U; m->bus.transcript_count=0U;
}
static void gate_test(void)
{
    motion_mock_t m; ss_link_t l; ss_motion_t a; ss_motion_config_t c;
    motion_fixture(&m,&l,&a); c=a.config; c.allow_submission=0U;
    CHECK("runtime gate init",ss_motion_init(&a,&l,&c)==SS_OK);
    CHECK("runtime gate blocks",ss_motion_arm(&a)==SS_ARGUMENT && a.outcome==SS_MOTION_GATE_CLOSED && m.bus.count==0U);
    if(!ss_motion_build_enabled()) {
        c.allow_submission=1U; CHECK("build gate init",ss_motion_init(&a,&l,&c)==SS_OK);
        CHECK("build gate blocks",ss_motion_arm(&a)==SS_ARGUMENT && m.bus.count==0U);
        CHECK("low-level shadow gate",ss_link_motion_write_at(&l,motion_now(&m),0x18U,UINT32_C(0x4005A))==SS_ARGUMENT);
        CHECK("low-level permit gate",ss_link_motion_write_at(&l,motion_now(&m),0x58U,1U)==SS_ARGUMENT);
        CHECK("low-level commit gate",ss_link_motion_write_at(&l,motion_now(&m),0x58U,8U)==SS_ARGUMENT);
        CHECK("low-level watchdog gate",ss_link_motion_write_at(&l,motion_now(&m),0x60U,100U)==SS_ARGUMENT);
        CHECK("zero motion writes",m.bus.count==0U && m.accepted==0U);
        CHECK("STOP remains available",ss_motion_stop(&a)==SS_OK && m.stop_latched!=0);
    }
    puts("P2_GATES,PASS,build_default_off,runtime_opt_in,physical_adapter_unchanged");
}
static unsigned int good_run(unsigned int *commit_pos)
{
    motion_mock_t m; ss_link_t l; ss_motion_t a; doa_frame_input_t f; doa_solve_output_t r;
    unsigned int i,before,transfers;
    motion_fixture(&m,&l,&a); CHECK("arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); before=m.bus.count; m.bus.transcript_count=0U;
    CHECK("good poll",ss_motion_poll(&a,&f,&r)==SS_OK);
    transfers=m.bus.count-before; *commit_pos=0U;
    for(i=0U;i<m.bus.transcript_count;++i)
        if(m.bus.transcript[i][0]==UINT8_C(0xD8) && load32(&m.bus.transcript[i][1])==8U) *commit_pos=i+1U;
    CHECK("commit exists before consumption",*commit_pos>39U && *commit_pos<transfers &&
          m.bus.transcript[transfers-1U][0]==UINT8_C(0xB8));
    CHECK("horizontal90",r.horizontal_servo_deg==90U && r.servo_cmd_valid==1U && m.shadow==UINT32_C(0x4005A));
    CHECK("same frame exactly once",m.accepted==1U && m.last_accepted==f.frame_id && m.bus.consumes==1U);
    CHECK("no false receipt",a.outcome==SS_MOTION_SUBMITTED_UNCONFIRMED && a.commit_transfer_completed!=0U);
    CHECK("fence",a.last_attempted_frame==1U && a.have_attempted!=0U);
    printf("P2_VALID,frame=1,angle=0,target=90,model_accepted=%u,consumed=%u,transfers=%u,commit_position=%u,wire_acceptance=UNCONFIRMED\n",
           m.accepted,m.bus.consumes,transfers,*commit_pos);
    for(i=0U;i<2U;++i) {
        packet_t p=packet(1,0,i+2U); unsigned int j;
        const int lag[2][6]={{0,4,4,4,4,0},{0,-4,-4,-4,-4,0}};
        for(j=0U;j<6U;++j) p.word[j][0]=(p.word[j][0]&~UINT32_C(255)) |
            (uint32_t)(lag[i][j]<0 ? lag[i][j]+256 : lag[i][j]);
        publish(&m.bus,p);
        CHECK("nonzero angle",ss_motion_poll(&a,&f,&r)==SS_OK && r.horizontal_servo_deg==(i==0U?180U:0U));
        CHECK("new frames renew only by commit",m.accepted==i+2U && m.watchdog_loads==i+2U && m.nonzero_watchdog_writes==1U);
        printf("P2_NONZERO,frame=%" PRIu32 ",angle_q8=%" PRId32 ",target=%u\n",f.frame_id,r.angle_q8,(unsigned int)r.horizontal_servo_deg);
    }
    CHECK("explicit disarm",ss_motion_disarm(&a)==SS_OK && m.bus.act==0U && m.bus.watchdog==0U);
    CHECK("no bad requests",m.bus.bad_tx==0U);
    return transfers;
}
static void poll_matrix(unsigned int total,unsigned int commit_pos)
{
    unsigned int n; int after,timeout;
    for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=total;++n) {
        motion_mock_t m; ss_link_t l; ss_motion_t a; doa_frame_input_t f; doa_solve_output_t r;
        unsigned int before,accepted,consumed;
        motion_fixture(&m,&l,&a); CHECK("matrix arm",ss_motion_arm(&a)==SS_OK);
        publish(&m.bus,packet(1,0,1U)); m.bus.fail_at=m.bus.count+n;
        m.bus.fail_after=after; m.bus.timeout_error=timeout;
        CHECK("poll injected error",ss_motion_poll(&a,&f,&r)==(timeout?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("quarantine",a.state==SS_MOTION_FAULT && l.recovery_required!=0U);
        CHECK("no output on error",zero_bytes(&f,sizeof(f)) && zero_bytes(&r,sizeof(r)));
        accepted=(n>commit_pos || (n==commit_pos && after!=0))?1U:0U;
        consumed=(n==total && after!=0)?1U:0U;
        CHECK("actual effect bounded",m.accepted==accepted && m.bus.consumes==consumed && m.bus.act==0U);
        CHECK("ambiguity explicit",a.commit_attempted==(n>=commit_pos?1U:0U));
        before=m.bus.count;
        CHECK("no poll retry",ss_motion_poll(&a,&f,&r)==SS_RECOVERY_REQUIRED && m.bus.count==before);
        CHECK("no rearm without recover",ss_motion_arm(&a)==SS_RECOVERY_REQUIRED && m.bus.count==before);
        m.bus.fail_at=0U;
        CHECK("explicit recover",ss_motion_recover(&a)==SS_OK && a.state==SS_MOTION_DISARMED);
        CHECK("recovery never commit/consume",m.accepted==accepted && m.bus.consumes==consumed && m.bus.act==0U);
        before=m.bus.count; CHECK("no automatic rearm",ss_motion_poll(&a,&f,&r)==SS_BUSY && m.bus.count==before);
        CHECK("explicit arm again",ss_motion_arm(&a)==SS_OK);
        if(n>=commit_pos && consumed==0U) {
            before=m.commits;
            CHECK("uncertain frame cannot resubmit",ss_motion_poll(&a,&f,&r)==SS_STALE_FRAME && m.commits==before);
            CHECK("fence survives recovery",a.have_attempted!=0U && a.last_attempted_frame==1U);
        } else if(consumed!=0U) {
            CHECK("already consumed no frame",ss_motion_poll(&a,&f,&r)==SS_NO_FRAME && m.accepted==1U);
        } else {
            CHECK("precommit retry after explicit recovery",ss_motion_poll(&a,&f,&r)==SS_OK && m.accepted==1U && m.bus.consumes==1U);
        }
        CHECK("no malformed model operations",m.bus.bad_tx==0U);
    }
    printf("P2_POLL_FAULT_MATRIX,PASS,cases=%u,before_after_x_IO_timeout,no_duplicate_commit\n",total*4U);
}
static void controls_matrix(void)
{
    unsigned int phase,n,cases=0U; int after,timeout;
    for(phase=0U;phase<3U;++phase) {
        motion_mock_t m; ss_link_t l; ss_motion_t a; unsigned int total,before;
        motion_fixture(&m,&l,&a);
        if(phase!=0U) CHECK("control prearm",ss_motion_arm(&a)==SS_OK);
        before=m.bus.count;
        CHECK("control reference",(phase==0U?ss_motion_arm(&a):phase==1U?ss_motion_disarm(&a):ss_motion_stop(&a))==SS_OK);
        total=m.bus.count-before;
        for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=total;++n) {
            motion_fixture(&m,&l,&a);
            if(phase!=0U) CHECK("control matrix prearm",ss_motion_arm(&a)==SS_OK);
            m.bus.fail_at=m.bus.count+n; m.bus.fail_after=after; m.bus.timeout_error=timeout;
            CHECK("control failure propagated",(phase==0U?ss_motion_arm(&a):phase==1U?ss_motion_disarm(&a):ss_motion_stop(&a))==(timeout?SS_TIMEOUT:SS_IO_ERROR));
            CHECK("control failure isolated",a.state==SS_MOTION_FAULT && m.accepted==0U && m.bus.act==0U);
            ++cases;
        }
    }
    printf("P2_CONTROL_FAULT_MATRIX,PASS,cases=%u,arm_disarm_stop\n",cases);
}
static void rejects_and_limits(unsigned int commit_pos)
{
    motion_mock_t m; ss_link_t l; ss_motion_t a; doa_frame_input_t f; doa_solve_output_t r;
    unsigned int i,before; ss_motion_config_t c;
    for(i=0U;i<4U;++i) {
        packet_t p=packet(i!=0U,i==1U,1U);
        motion_fixture(&m,&l,&a); CHECK("reject arm",ss_motion_arm(&a)==SS_OK);
        if(i==2U) p.flags|=UINT32_C(0x01100000);
        if(i==3U) a.config.servo.domain_min_q8=256; /* valid config excludes 0deg */
        publish(&m.bus,p);
        CHECK("reject consumes without motion",ss_motion_poll(&a,&f,&r)==SS_OK && a.outcome==SS_MOTION_REJECTED &&
              m.accepted==0U && m.commits==0U && m.bus.consumes==1U && m.bus.act==0U && m.bus.watchdog==0U);
        CHECK("rejection requires rearm",a.state==SS_MOTION_DISARMED);
    }
    motion_fixture(&m,&l,&a); m.bound=0;
    CHECK("unbound arm refused",ss_motion_arm(&a)==SS_DEVICE_FAULT && m.bus.permit_writes==0U);
    motion_fixture(&m,&l,&a); m.bus.ctrl=11U;
    CHECK("BIST arm refused",ss_motion_arm(&a)==SS_DEVICE_FAULT && m.bus.permit_writes==0U);
    motion_fixture(&m,&l,&a); c=a.config; c.watchdog_ticks=0U;
    CHECK("zero watchdog config refused",ss_motion_init(&a,&l,&c)==SS_ARGUMENT);
    c.watchdog_ticks=1U; c.servo.direction=0;
    CHECK("invalid mapping refused",ss_motion_init(&a,&l,&c)==SS_ARGUMENT);
    motion_fixture(&m,&l,&a); a.config.max_frame_hold_ms=20U;
    CHECK("age arm",ss_motion_arm(&a)==SS_OK); publish(&m.bus,packet(1,0,1U));
    CHECK("old host-held frame not committed",ss_motion_poll(&a,&f,&r)==SS_TIMEOUT && m.commits==0U && m.bus.consumes==0U);
    motion_fixture(&m,&l,&a); CHECK("budget arm",ss_motion_arm(&a)==SS_OK);
    l.bus.operation_timeout_ms=15U; publish(&m.bus,packet(1,0,1U));
    CHECK("whole operation budget",ss_motion_poll(&a,&f,&r)==SS_TIMEOUT && m.commits==0U);
    motion_fixture(&m,&l,&a); CHECK("shadow arm",ss_motion_arm(&a)==SS_OK);
    m.bad_shadow=1U; publish(&m.bus,packet(1,0,1U));
    CHECK("shadow mismatch rejected",ss_motion_poll(&a,&f,&r)==SS_DEVICE_FAULT && m.commits==0U);
    motion_fixture(&m,&l,&a); CHECK("late loss arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); m.drop_permit_at=m.bus.count+commit_pos;
    CHECK("late permit loss",ss_motion_poll(&a,&f,&r)==SS_DEVICE_FAULT && m.accepted==0U && a.outcome==SS_MOTION_UNCERTAIN);
    motion_fixture(&m,&l,&a); CHECK("silent lost write arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); m.ignore_commit=1U;
    CHECK("lack of ACK remains explicit",ss_motion_poll(&a,&f,&r)==SS_OK && m.accepted==0U && a.outcome==SS_MOTION_SUBMITTED_UNCONFIRMED);
    motion_fixture(&m,&l,&a); CHECK("watchdog arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); CHECK("watchdog first command",ss_motion_poll(&a,&f,&r)==SS_OK);
    before=m.nonzero_watchdog_writes;
    CHECK("empty no refresh",ss_motion_poll(&a,&f,&r)==SS_NO_FRAME && m.nonzero_watchdog_writes==before);
    m.bus.clock_ms+=100U;
    CHECK("watchdog expiry faults",ss_motion_poll(&a,&f,&r)==SS_DEVICE_FAULT && (m.bus.fault&256U)!=0U && m.bus.act==0U);
    CHECK("sticky watchdog recovery blocked",ss_motion_recover(&a)==SS_DEVICE_FAULT && a.state==SS_MOTION_FAULT);
    motion_fixture(&m,&l,&a); m.bus.clock_ms=UINT32_MAX-20U; m.tick_ms=m.bus.clock_ms;
    CHECK("wrap arm",ss_motion_arm(&a)==SS_OK); publish(&m.bus,packet(1,0,1U));
    CHECK("wrap poll",ss_motion_poll(&a,&f,&r)==SS_OK && m.accepted==1U);
    CHECK("STOP",ss_motion_stop(&a)==SS_OK && m.bus.act==0U && m.stop_latched!=0);
    before=m.bus.count; CHECK("STOP no replay",ss_motion_stop(&a)==SS_OK && m.bus.count==before);
    CHECK("sticky STOP blocks recovery",ss_motion_recover(&a)==SS_DEVICE_FAULT && (m.bus.fault&64U)!=0U);
    puts("P2_BOUNDARIES,PASS,BIST/reject/cancel/mapping/bound/age/budget/shadow/permit/ACK/watchdog/wrap/STOP");
}
static void recovery_fixture(motion_mock_t *m,ss_link_t *l,ss_motion_t *a,unsigned int commit_pos)
{
    doa_frame_input_t f; doa_solve_output_t r;
    motion_fixture(m,l,a); CHECK("recovery fixture arm",ss_motion_arm(a)==SS_OK);
    publish(&m->bus,packet(1,0,1U));
    m->bus.fail_at=m->bus.count+commit_pos; m->bus.fail_after=1;
    CHECK("uncertain commit fixture",ss_motion_poll(a,&f,&r)==SS_IO_ERROR && m->accepted==1U);
    m->bus.fail_at=0U;
}
static void recovery_matrix(unsigned int commit_pos)
{
    motion_mock_t m; ss_link_t l; ss_motion_t a; unsigned int n,total,before;
    int after,timeout;
    recovery_fixture(&m,&l,&a,commit_pos); before=m.bus.count;
    CHECK("recovery reference",ss_motion_recover(&a)==SS_OK);
    total=m.bus.count-before;
    for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1U;n<=total;++n) {
        recovery_fixture(&m,&l,&a,commit_pos);
        m.bus.fail_at=m.bus.count+n; m.bus.fail_after=after; m.bus.timeout_error=timeout;
        CHECK("recovery errors propagate",ss_motion_recover(&a)==(timeout?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("recovery stays isolated",a.state==SS_MOTION_FAULT && l.recovery_required!=0U);
        CHECK("attempt fence never reset",a.have_attempted!=0U && a.last_attempted_frame==1U);
        CHECK("no retry/consume during recovery",m.accepted==1U && m.commits==1U && m.bus.consumes==0U);
        CHECK("original error stays",a.first_error==SS_IO_ERROR);
    }
    printf("P2_RECOVERY_FAULT_MATRIX,PASS,cases=%u,commit_fence_preserved\n",total*4U);
}
static void identity_and_races(unsigned int commit_pos)
{
    motion_mock_t m; ss_link_t l; ss_motion_t a; doa_frame_input_t f; doa_solve_output_t r;
    unsigned int before,i,last_frame_read=0U;
    motion_fixture(&m,&l,&a); CHECK("race reference arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); m.bus.transcript_count=0U;
    CHECK("race reference",ss_motion_poll(&a,&f,&r)==SS_OK);
    for(i=0U;i<m.bus.transcript_count;++i)
        if(m.bus.transcript[i][0]==UINT8_C(8)) last_frame_read=i+1U;
    motion_fixture(&m,&l,&a); CHECK("swap arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); m.bus.mutate_at=m.bus.count+last_frame_read; m.bus.mutate_word=2U;
    CHECK("changed locked frame before commit",ss_motion_poll(&a,&f,&r)==SS_STALE_FRAME && m.commits==0U && m.bus.consumes==0U);
    motion_fixture(&m,&l,&a); CHECK("fault race arm",ss_motion_arm(&a)==SS_OK);
    publish(&m.bus,packet(1,0,1U)); m.fault_at=m.bus.count+commit_pos;
    CHECK("fault at commit hardware rejects",ss_motion_poll(&a,&f,&r)==SS_DEVICE_FAULT && m.accepted==0U && a.outcome==SS_MOTION_UNCERTAIN);
    motion_fixture(&m,&l,&a); a.config.watchdog_ticks=61440U;
    CHECK("short watchdog arm",ss_motion_arm(&a)==SS_OK); publish(&m.bus,packet(1,0,1U));
    CHECK("expiry right after accepted commit",ss_motion_poll(&a,&f,&r)==SS_DEVICE_FAULT && m.accepted==1U && m.bus.act==0U && a.outcome==SS_MOTION_UNCERTAIN);
    recovery_fixture(&m,&l,&a,commit_pos); m.bus.magic=0U; before=m.bus.count;
    CHECK("wrong identity recovery no write",ss_motion_recover(&a)==SS_IDENTITY && m.bus.count==before+1U && m.commits==1U);
    CHECK("wrong identity cannot rearm",ss_motion_arm(&a)==SS_RECOVERY_REQUIRED);
    recovery_fixture(&m,&l,&a,commit_pos); m.bus.ignore_release=1;
    CHECK("stuck lock keeps isolation",ss_motion_recover(&a)==SS_DEVICE_FAULT && a.state==SS_MOTION_FAULT);
    motion_fixture(&m,&l,&a); CHECK("no default lease refresh arm",ss_motion_arm(&a)==SS_OK);
    before=m.bus.count;
    CHECK("duplicate arm no writes",ss_motion_arm(&a)==SS_BUSY && m.bus.count==before);
    CHECK("invalid private address",ss_link_motion_write_at(&l,motion_now(&m),0x04U,9U)==SS_BAD_REGISTER && m.bus.count==before);
    CHECK("combined commit permit forbidden",ss_link_motion_write_at(&l,motion_now(&m),0x58U,9U)==SS_ARGUMENT && m.bus.count==before);
    CHECK("vertical forbidden",ss_link_motion_write_at(&l,motion_now(&m),0x18U,UINT32_C(0xC005A))==SS_ARGUMENT && m.bus.count==before);
    CHECK("null APIs",ss_motion_init(NULL,NULL,NULL)==SS_ARGUMENT && ss_motion_arm(NULL)==SS_ARGUMENT &&
          ss_motion_disarm(NULL)==SS_ARGUMENT && ss_motion_stop(NULL)==SS_ARGUMENT &&
          ss_motion_recover(NULL)==SS_ARGUMENT && ss_motion_poll(NULL,&f,&r)==SS_ARGUMENT);
    puts("P2_RACES,PASS,locked_frame_swap,late_fault,post_commit_expiry,wrong_ID,stuck_lock,no_combined_commit");
}
int main(void)
{
    gate_test();
    if(ss_motion_build_enabled()) {
        unsigned int commit_pos,total=good_run(&commit_pos);
        poll_matrix(total,commit_pos); controls_matrix(); rejects_and_limits(commit_pos);
        recovery_matrix(commit_pos); identity_and_races(commit_pos);
    }
    printf("P2_RESULT,%s,build_gate=%d,checks=%u,failures=%u\n",failures==0U?"PASS":"FAIL",ss_motion_build_enabled(),checks,failures);
    return failures==0U?0:1;
}
