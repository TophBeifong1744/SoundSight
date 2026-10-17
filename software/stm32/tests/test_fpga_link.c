#include "fpga_link.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static unsigned int checks, failures;
#define CHECK(label, expression) do { ++checks; if (!(expression)) { ++failures; \
    fprintf(stderr, "FAIL line %d %s\n", __LINE__, label); } } while (0)

/* A separate register-level peripheral model. Wire addresses/packing below are
 * literal ABI values so a shared encoder/decoder cannot hide a packing error.
 * This is NOT an RTL/SPI timing simulation. */
typedef struct { uint32_t id, flags, word[6][5]; } packet_t;
typedef struct { int state; packet_t data; } slot_t; /* 0 FREE, 1 READY, 2 LOCKED */
typedef struct {
    slot_t slot[2];
    uint32_t magic, version, ctrl, act, watchdog, bist, select, fault, drops;
    uint32_t sequence, clock_ms, duration_ms, status_or, status_xor;
    unsigned int count, fail_at, mutate_at, arrival_at;
    int fail_after, timeout_error, arrival_on_consume, ignore_release;
    uint32_t mutate_word;
    unsigned int consumes, releases, acquires, action_writes, permit_writes;
    unsigned int bad_tx, transcript_count;
    uint8_t transcript[512][5];
} mock_t;

static uint32_t load32(const uint8_t *p)
{ return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
static void store32(uint8_t *p, uint32_t x)
{ p[0]=(uint8_t)(x>>24); p[1]=(uint8_t)(x>>16); p[2]=(uint8_t)(x>>8); p[3]=(uint8_t)x; }
static packet_t packet(int pass, int bist, uint32_t id)
{
    const int lag_pass[6] = {4,4,0,0,-4,-4};
    const int lag_reject[6] = {5,-3,0,1,-1,2};
    packet_t p;
    unsigned int i;
    memset(&p, 0, sizeof(p)); p.id=id;
    p.flags = UINT32_C(0x10) | (bist != 0 ? UINT32_C(0x28) : 0U);
    for(i=0;i<6U;++i) {
        int lag = pass != 0 ? lag_pass[i] : lag_reject[i];
        uint32_t byte = (uint32_t)(lag < 0 ? lag+256 : lag);
        p.word[i][0] = byte | ((uint32_t)i << 8) | UINT32_C(0x004F1800) |
                       (bist != 0 ? UINT32_C(0x66000000) : UINT32_C(0x11002000));
        p.word[i][1]=1000U; p.word[i][2]=800U;
        p.word[i][3]=pass != 0 ? 800U : 600U; p.word[i][4]=100U;
    }
    return p;
}
static int locked(mock_t *m)
{ int i; for(i=0;i<2;++i) if(m->slot[i].state==2) return i; return -1; }
static void publish(mock_t *m, packet_t p)
{
    int i;
    m->sequence=p.id;
    for(i=0;i<2;++i) if(m->slot[i].state==0) { m->slot[i].data=p; m->slot[i].state=1; return; }
    if(m->drops != UINT32_MAX) ++m->drops;
    m->fault |= 8U;
}
static uint32_t status(mock_t *m)
{
    uint32_t s=UINT32_C(0x10000);
    int i, k=locked(m);
    for(i=0;i<2;++i) if(m->slot[i].state==1) s|=2U;
    if(k>=0) {
        unsigned int j;
        s |= 1U | m->slot[k].data.flags;
        for(j=0;j<6U;++j) if((m->slot[k].data.word[j][0]&UINT32_C(0x800))!=0U)
            s |= UINT32_C(1)<<(8U+j);
    }
    if(m->drops!=0U) s|=4U;
    if((s&3U)!=0U || m->fault!=0U) s|=UINT32_C(0x4000);
    if(m->act!=0U) s|=UINT32_C(0x80);
    return (s | m->status_or) ^ m->status_xor;
}
static uint32_t read_word(mock_t *m, uint32_t a)
{
    int k=locked(m);
    switch(a) {
    case 0x00: return m->magic;
    case 0x04: return m->ctrl;
    case 0x08: return k>=0 ? m->slot[k].data.id : 0U;
    case 0x0C: case 0x10: case 0x20: case 0x24: case 0x28:
        if(k<0 || m->select>=6U) return 0U;
        return m->slot[k].data.word[m->select][a==0x0CU?0:a==0x10U?1:a==0x20U?2:a==0x24U?3:4];
    case 0x14: return k>=0 && (m->slot[k].data.flags&8U)!=0U ? 100000U : 0U;
    case 0x18: case 0x38: return 0U;
    case 0x1C: return m->select;
    case 0x2C: return m->bist;
    case 0x34: return status(m);
    case 0x58: return m->act;
    case 0x60: return m->watchdog;
    case 0x64: return m->fault;
    case 0x68: return m->drops;
    case 0x6C: return m->version;
    default: ++m->bad_tx; m->fault|=2U; return UINT32_C(0xDEADBEEF);
    }
}
static void write_word(mock_t *m,uint32_t a,uint32_t v)
{
    int k=locked(m);
    if(a==0x04U) {
        uint32_t old=m->ctrl;
        if((v&~UINT32_C(0xB))!=0U || (v&8U)==0U) { ++m->bad_tx; return; }
        m->ctrl=v;
        if((old&1U)==0U && (v&3U)==3U)
            publish(m,packet(m->bist==1U,1,m->sequence+1U));
    } else if(a==0x1CU) {
        if(v>=6U) ++m->bad_tx; else m->select=v;
    } else if(a==0x2CU) {
        if(v>1U || (m->ctrl&1U)!=0U || (status(m)&3U)!=0U) { ++m->bad_tx; return; }
        m->bist=v;
    } else if(a==0x38U) {
        if(v==1U) {
            int first=-1,i;
            ++m->acquires;
            if(k>=0) return;
            for(i=0;i<2;++i) if(m->slot[i].state==1 &&
                (first<0 || m->slot[i].data.id<m->slot[first].data.id)) first=i;
            if(first>=0) m->slot[first].state=2;
        } else if(v==2U || v==4U) {
            if(k<0) { ++m->bad_tx; m->fault|=4U; return; }
            if(v==2U) { ++m->releases; if(m->ignore_release==0) m->slot[k].state=1; }
            else { ++m->consumes; m->slot[k].state=0;
                if(m->arrival_on_consume!=0) {
                    m->arrival_on_consume=0; publish(m,packet(1,1,m->sequence+1U));
                }
            }
        } else if(v!=0U) ++m->bad_tx;
    } else if(a==0x58U) {
        if((v&UINT32_C(9))!=0U) ++m->permit_writes;
        if(v==2U) { m->act=0U; m->ctrl&=~UINT32_C(1); m->fault|=64U; }
        else if(v==4U || v==0U) m->act=0U;
        else { ++m->bad_tx; }
    } else if(a==0x60U) { m->watchdog=v; if(v==0U) m->act=0U; }
    else if(a==0x18U) { ++m->action_writes; }
    else { ++m->bad_tx; }
}
static ss_bus_status_t transfer(void *user,const uint8_t tx[5],uint8_t rx[5],uint32_t timeout)
{
    mock_t *m=(mock_t *)user;
    uint32_t a=(uint32_t)(tx[0]&UINT8_C(0x7F)), v;
    int injected;
    ++m->count;
    CHECK("bounded nonzero callback timeout",timeout>0U && timeout<=5U);
    if(m->transcript_count<512U) memcpy(m->transcript[m->transcript_count++],tx,5U);
    m->clock_ms+=m->duration_ms;
    injected=m->count==m->fail_at;
    memset(rx,0,5U); rx[0]=UINT8_C(0xA5); /* ignored header byte */
    if(injected!=0 && m->fail_after==0)
        return m->timeout_error!=0 ? SS_BUS_TIMEOUT : SS_BUS_ERROR;
    if((tx[0]&UINT8_C(0x80))!=0U) write_word(m,a,load32(&tx[1]));
    else {
        if(load32(&tx[1])!=0U) ++m->bad_tx;
        v=read_word(m,a);
        if(m->count==m->mutate_at) v=m->mutate_word;
        store32(&rx[1],v);
    }
    if(m->count==m->arrival_at) publish(m,packet(0,1,m->sequence+1U));
    if(injected!=0) return m->timeout_error!=0 ? SS_BUS_TIMEOUT : SS_BUS_ERROR;
    return SS_BUS_OK;
}
static uint32_t now_ms(void *user) { return ((mock_t *)user)->clock_ms; }
static void setup(mock_t *m,ss_link_t *l)
{
    ss_bus_t bus;
    memset(m,0,sizeof(*m));
    m->magic=UINT32_C(0x5A5A2026);m->version=UINT32_C(0x10000);m->ctrl=8U;m->duration_ms=1U;
    bus.user=m;bus.transfer=transfer;bus.now_ms=now_ms;
    bus.transfer_timeout_ms=5U;bus.operation_timeout_ms=100U;
    CHECK("init",ss_init(l,&bus)==SS_OK);
    CHECK("probe",ss_probe(l)==SS_OK);
    CHECK("probe disables movement",m->act==0U && m->watchdog==0U);
    m->count=0U;m->transcript_count=0U;
}
static doa_servo_config_t servo_config(void)
{ doa_servo_config_t c={1U,23040,1,-23040,23040,0U,180U,180U};return c; }
static int zero_bytes(const void *p,size_t n)
{ const unsigned char *b=(const unsigned char *)p;size_t i;for(i=0;i<n;++i) if(b[i]!=0U)return 0;return 1; }

static void test_bist(void)
{
    mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t r;
    doa_servo_config_t cfg=servo_config();
    const int32_t tau[2][6]={{19797,-12971,-683,3413,-4779,7509},{16384,16384,0,0,-16384,-16384}};
    unsigned int b,i;
    setup(&m,&l);
    for(b=0;b<2U;++b) {
        unsigned int before;
        CHECK("start BIST",ss_start(&l,b==0U?SS_RUN_BIST_REJECT:SS_RUN_BIST_PASS)==SS_OK);
        before=m.count;m.transcript_count=0U;
        CHECK("poll BIST",ss_poll_solve(&l,&cfg,&f,&r)==SS_OK);
        CHECK("exactly 40 transactions",m.count-before==40U);
        CHECK("consume in SNAP_CMD",m.transcript[39][0]==UINT8_C(0xB8) && load32(&m.transcript[39][1])==4U);
        CHECK("acquire first",m.transcript[0][0]==UINT8_C(0xB8) && load32(&m.transcript[0][1])==1U);
        for(i=0;i<6U;++i) {
            unsigned int pos=3U+i*6U;
            const uint8_t expected[5]={0x0C,0x10,0x20,0x24,0x28};unsigned int j;
            CHECK("select packet",m.transcript[pos][0]==UINT8_C(0x9C) && load32(&m.transcript[pos][1])==i);
            for(j=0;j<5U;++j) CHECK("payload read order",m.transcript[pos+1U+j][0]==expected[j]);
            CHECK("tau matches frozen hand result",r.pair[i].tau_q12==tau[b][i]);
            CHECK("margin",r.pair[i].margin_q15==29491);
            CHECK("delta",r.pair[i].delta_q12==(b==0U?-683:0));
        }
        CHECK("ux",r.ux_q20==(b==0U?46831:749295));
        CHECK("uy",r.uy_q20==(b==0U?-171729:0));
        CHECK("residual",r.residual_square_q24==(b==0U?UINT64_C(590912626):UINT64_C(0)));
        CHECK("direction",r.direction_valid==b && r.direction_reason==(b==0U?3:0));
        CHECK("BIST no servo",r.servo_cmd_valid==0U && m.action_writes==0U && m.permit_writes==0U);
        CHECK("no unexpected register traffic",m.bad_tx==0U);
        CHECK("control preserved by consume",m.ctrl==11U);
        printf("BIST,%s,transactions=%u,ux=%" PRId32 ",uy=%" PRId32 ",residual=%" PRIu64
               ",valid=%u,reason=%d,angle_q8=%" PRId32 ",servo_cmd_valid=%u\n",
               b==0U?"REJECT":"PASS",m.count-before,r.ux_q20,r.uy_q20,r.residual_square_q24,
               (unsigned int)r.direction_valid,(int)r.direction_reason,r.angle_q8,(unsigned int)r.servo_cmd_valid);
    }
}
static void test_failure_matrix(void)
{
    unsigned int n;int after,timeout;
    for(timeout=0;timeout<2;++timeout) for(after=0;after<2;++after) for(n=1;n<=40U;++n) {
        mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t r;unsigned int attempted;
        setup(&m,&l);publish(&m,packet(1,1,1U));
        m.fail_at=n;m.fail_after=after;m.timeout_error=timeout;
        memset(&f,0x5A,sizeof(f));memset(&r,0x5A,sizeof(r));
        CHECK("injected error propagated",ss_poll_solve(&l,NULL,&f,&r)==(timeout!=0?SS_TIMEOUT:SS_IO_ERROR));
        CHECK("no partial/stale result",zero_bytes(&f,sizeof(f)) && zero_bytes(&r,sizeof(r)));
        CHECK("quarantine",l.recovery_required==1U);
        CHECK("no motion after failure",m.action_writes==0U && m.permit_writes==0U);
        CHECK("at most original consume",m.consumes==(n==40U && after!=0?1U:0U));
        attempted=m.count;
        CHECK("poll gated until recovery",ss_poll_solve(&l,NULL,&f,&r)==SS_RECOVERY_REQUIRED);
        CHECK("no retry traffic",m.count==attempted);
        m.fail_at=0U;
        CHECK("explicit recovery",ss_recover(&l)==SS_OK);
        CHECK("recover never consumes",m.consumes==(n==40U && after!=0?1U:0U));
        if(n==40U && after!=0) {
            CHECK("postcommit failure yields empty",ss_poll_solve(&l,NULL,&f,&r)==SS_NO_FRAME);
        } else CHECK("recover reread full frame",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==1U);
        CHECK("no bogus snapshot operations",m.bad_tx==0U);
    }
    printf("FAULT_MATRIX,CHECKED,40_positions,x2_before_after_commit,x2_io_timeout=160\n");
}
static void mutation(unsigned int at,uint32_t word,ss_status_t expected)
{
    mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t r;
    setup(&m,&l);publish(&m,packet(1,1,1U));m.mutate_at=at;m.mutate_word=word;
    memset(&r,0x7E,sizeof(r));
    CHECK("malformed wire rejected",ss_poll_solve(&l,NULL,&f,&r)==expected);
    CHECK("malformed never consumes",m.consumes==0U);
    CHECK("malformed result cleared",zero_bytes(&r,sizeof(r)) && zero_bytes(&f,sizeof(f)));
}
static void test_wire_rejections(void)
{
    packet_t p=packet(1,1,1U);
    mutation(2U,UINT32_C(0xFF000051),SS_WIRE_FORMAT); /* reserved status bit */
    mutation(2U,UINT32_C(0x10001),SS_WIRE_FORMAT); /* missing all terminal */
    mutation(2U,UINT32_C(0x13E19),SS_WIRE_FORMAT); /* raw-valid summary disagrees with pair0 */
    mutation(3U,0U,SS_STALE_FRAME);
    mutation(5U,p.word[0][0]|UINT32_C(0x800000),SS_WIRE_FORMAT);
    mutation(5U,p.word[0][0]^UINT32_C(0x100),SS_WIRE_FORMAT); /* echo */
    mutation(5U,(p.word[0][0]&~UINT32_C(255))|32U,SS_WIRE_FORMAT);
    mutation(5U,(p.word[0][0]&~UINT32_C(255))|UINT32_C(0xDF),SS_WIRE_FORMAT); /* -33 */
    mutation(5U,(p.word[0][0]&~UINT32_C(0x7F0000))|UINT32_C(0x500000),SS_WIRE_FORMAT);
    mutation(5U,p.word[0][0]&~UINT32_C(0x0F000000),SS_WIRE_FORMAT);
    mutation(5U,p.word[0][0]|UINT32_C(0x90000000),SS_WIRE_FORMAT);
    mutation(6U,UINT32_C(0x01000000),SS_WIRE_FORMAT); /* S25 overflow */
    mutation(7U,UINT32_C(0xFEFFFFFF),SS_WIRE_FORMAT); /* S25 underflow */
    mutation(8U,UINT32_C(0x01FFFFFF),SS_WIRE_FORMAT); /* missing negative S25 sign extension */
    mutation(9U,UINT32_C(0xDEADBEEF),SS_WIRE_FORMAT);
    /* A 0xFFFFFFFF correlation is legal -1, not globally a disconnect marker. */
    {
        mock_t m;ss_link_t l;doa_frame_input_t f;
        setup(&m,&l);p.word[0][1]=UINT32_C(0xFFFFFFFF);p.word[0][2]=UINT32_C(0xFF000000);
        p.word[0][3]=UINT32_C(0xFFFFFFFE);p.word[0][4]=UINT32_C(0x00FFFFFF)-UINT32_C(0x00800000);
        publish(&m,p);
        CHECK("legal signed values",ss_acquire_frame(&l,&f)==SS_OK);
        CHECK("signed -1 preserved",f.pair[0].peak==-1 && f.pair[0].r_minus==-16777216 && f.pair[0].r_plus==-2);
        CHECK("release",ss_finish_frame(&l,SS_RELEASE)==SS_OK);
    }
    printf("WIRE_CHECKS,CHECKED,pair_echo,reserved_bits,S6,S25,mask,stages,frame_id,sign_extension\n");
}
static void test_queue(void)
{
    mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t r;unsigned int before;
    setup(&m,&l);
    memset(&r,0x5A,sizeof(r));
    CHECK("empty queue",ss_poll_solve(&l,NULL,&f,&r)==SS_NO_FRAME && m.count==2U);
    CHECK("empty zero output",zero_bytes(&f,sizeof(f)) && zero_bytes(&r,sizeof(r)));
    publish(&m,packet(1,1,1U));publish(&m,packet(0,1,2U));publish(&m,packet(1,1,3U));
    CHECK("overflow drops new",m.drops==1U);
    CHECK("oldest kept",ss_acquire_frame(&l,&f)==SS_OK && f.frame_id==1U);
    before=m.count;CHECK("no nested lock",ss_acquire_frame(&l,&f)==SS_BUSY && m.count==before);
    CHECK("release does not consume",ss_finish_frame(&l,SS_RELEASE)==SS_OK && m.consumes==0U);
    CHECK("reread released oldest",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==1U);
    CHECK("second next no new IRQ edge needed",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==2U);
    CHECK("fault keeps IRQ high",(status(&m)&UINT32_C(0x4000))!=0U);
    CHECK("fault-only IRQ no frame",ss_poll_solve(&l,NULL,&f,&r)==SS_NO_FRAME);
    setup(&m,&l);publish(&m,packet(1,1,1U));m.arrival_at=6U;
    CHECK("arrival while locked",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && r.ux_q20==749295 && f.frame_id==1U);
    CHECK("new frame was separate",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==2U && r.direction_reason==3);
    setup(&m,&l);publish(&m,packet(1,1,1U));m.arrival_on_consume=1;
    CHECK("consume coincident arrival",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==1U);
    CHECK("pending IRQ survives",(status(&m)&UINT32_C(0x4000))!=0U);
    CHECK("arrival after consume processed",ss_poll_solve(&l,NULL,&f,&r)==SS_OK && f.frame_id==2U);
    publish(&m,packet(1,1,2U));
    CHECK("duplicate rejected",ss_poll_solve(&l,NULL,&f,&r)==SS_STALE_FRAME);
    CHECK("recovery preserves watermark",ss_recover(&l)==SS_OK && l.last_consumed_id==2U);
    CHECK("duplicate still rejected",ss_poll_solve(&l,NULL,&f,&r)==SS_STALE_FRAME);
    setup(&m,&l);publish(&m,packet(1,1,UINT32_MAX));
    CHECK("last legal frame",ss_poll_solve(&l,NULL,&f,&r)==SS_OK);
    publish(&m,packet(1,1,1U));
    CHECK("reset sequence needs new session",ss_poll_solve(&l,NULL,&f,&r)==SS_STALE_FRAME);
    printf("QUEUE,CHECKED,empty,oldest,release,overflow,concurrent_arrival,level_IRQ,duplicate,reset\n");
}
static void test_control_and_deadlines(void)
{
    mock_t m;ss_link_t l;doa_frame_input_t f;doa_solve_output_t r;uint32_t v;unsigned int before;
    setup(&m,&l);
    before=m.count;
    CHECK("unaligned blocked locally",ss_read_register(&l,1U,&v)==SS_BAD_REGISTER);
    CHECK("undefined blocked locally",ss_read_register(&l,0x30U,&v)==SS_BAD_REGISTER);
    CHECK("out of range blocked locally",ss_read_register(&l,0x80U,&v)==SS_BAD_REGISTER);
    CHECK("no malformed bus traffic",m.count==before);
    m.drops=UINT32_C(0x12345678);
    CHECK("big-endian read",ss_read_register(&l,REG_DROP_COUNT,&v)==SS_OK && v==UINT32_C(0x12345678));
    m.magic=UINT32_C(0xFFFFFFFF);before=m.count;
    CHECK("identity mismatch",ss_probe(&l)==SS_IDENTITY && m.count==before+1U);
    m.magic=UINT32_C(0x5A5A2026);m.version=2U;before=m.count;
    CHECK("wrong ABI gated",ss_recover(&l)==SS_IDENTITY && m.count==before+2U);
    setup(&m,&l);publish(&m,packet(1,1,1U));
    CHECK("cannot change BIST with queued frame",ss_start(&l,SS_RUN_BIST_PASS)==SS_BUSY);
    CHECK("pending frame retained",m.slot[0].state==1 && m.bist==0U);
    setup(&m,&l);m.status_or=UINT32_C(0x8000);
    CHECK("draining bounded BUSY",ss_start(&l,SS_RUN_REAL)==SS_BUSY);
    setup(&m,&l);m.fault=8U;
    CHECK("fault blocks run",ss_start(&l,SS_RUN_REAL)==SS_DEVICE_FAULT && (m.ctrl&1U)==0U);
    setup(&m,&l);CHECK("start real",ss_start(&l,SS_RUN_REAL)==SS_OK && m.ctrl==9U);
    CHECK("explicit stop",ss_stop(&l)==SS_OK && (m.ctrl&1U)==0U && m.act==0U);
    setup(&m,&l);publish(&m,packet(1,1,1U));m.clock_ms=UINT32_MAX-10U;
    CHECK("clock wrap",ss_poll_solve(&l,NULL,&f,&r)==SS_OK);
    setup(&m,&l);publish(&m,packet(1,1,1U));l.bus.operation_timeout_ms=10U;
    CHECK("whole-frame timeout",ss_poll_solve(&l,NULL,&f,&r)==SS_TIMEOUT);
    CHECK("timeout no consume/output",m.consumes==0U && zero_bytes(&r,sizeof(r)));
    setup(&m,&l);publish(&m,packet(1,1,1U));m.duration_ms=6U;
    CHECK("late callback success rejected",ss_poll_solve(&l,NULL,&f,&r)==SS_TIMEOUT);
    CHECK("failed revoke separately visible",l.revoke_result==SS_TIMEOUT);
    CHECK("late callback no output",zero_bytes(&r,sizeof(r)) && m.consumes==0U);
    setup(&m,&l);m.fail_at=2U;before=m.count;
    CHECK("identity read error",ss_probe(&l)==SS_IO_ERROR);
    CHECK("no write before identity known",m.count==before+2U && l.revoke_result==SS_NOT_PROBED);
    CHECK("stop unknown device blocked",ss_stop(&l)==SS_NOT_PROBED && m.count==before+2U);
    setup(&m,&l);publish(&m,packet(1,1,1U));m.fail_at=5U;
    CHECK("force recovery",ss_poll_solve(&l,NULL,&f,&r)==SS_IO_ERROR);
    m.fail_at=0U;m.ignore_release=1;
    CHECK("release readback detects stuck slot",ss_recover(&l)==SS_DEVICE_FAULT && l.recovery_required==1U);
    CHECK("null arguments",ss_poll_solve(NULL,NULL,&f,&r)==SS_ARGUMENT && ss_init(NULL,NULL)==SS_ARGUMENT);
    printf("CONTROL,CHECKED,identity,ABI,address,disabled_config,queue_busy,stop,time_wrap,deadline,recovery\n");
}
static void test_source_outcomes(void)
{
    mock_t m;ss_link_t l;packet_t p;doa_frame_input_t f;doa_solve_output_t r;
    doa_servo_config_t cfg=servo_config();unsigned int i;
    setup(&m,&l);p=packet(1,0,1U);publish(&m,p);
    CHECK("real synthetic frame",ss_poll_solve(&l,&cfg,&f,&r)==SS_OK && r.direction_valid==1U && r.servo_cmd_valid==1U);
    CHECK("solver eligibility is not action submission",m.action_writes==0U && m.permit_writes==0U);
    setup(&m,&l);p=packet(1,0,1U);p.flags|=UINT32_C(0x01100000);publish(&m,p);
    CHECK("frame cancel preserves priority",ss_poll_solve(&l,&cfg,&f,&r)==SS_OK && r.direction_reason==6 && r.servo_cmd_valid==0U);
    setup(&m,&l);p=packet(1,0,1U);p.flags|=UINT32_C(0x07000000);publish(&m,p);
    CHECK("first error preserved",ss_poll_solve(&l,&cfg,&f,&r)==SS_OK && r.direction_reason==7 && r.first_error_code==7U);
    setup(&m,&l);p=packet(1,0,1U);
    for(i=0;i<6U;++i) p.word[i][0]=(p.word[i][0]&~UINT32_C(0x7F0000))|UINT32_C(0xB0000);
    publish(&m,p);
    CHECK("mask algorithm rejection consumed",ss_poll_solve(&l,&cfg,&f,&r)==SS_OK && r.direction_reason==1 && m.consumes==1U);
    printf("SOURCE,CHECKED,real_synthetic,cancel_priority,first_error,mask_rejection,no_actuation\n");
}
int main(void)
{
    test_bist();test_failure_matrix();test_wire_rejections();test_queue();
    test_control_and_deadlines();test_source_outcomes();
    printf("RESULT,%s,checks=%u,failures=%u\n",failures==0U?"PASS":"FAIL",checks,failures);
    return failures==0U?0:1;
}
