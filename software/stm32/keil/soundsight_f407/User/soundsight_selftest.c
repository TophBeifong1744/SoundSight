#include "soundsight_board.h"
#include "ss_app.h"
#include "SYSTEM/usart/usart.h"
#include <stdio.h>
#include <string.h>

static unsigned int passes,fails,skips;
static int board_ok;
static ss_app_t application;
#define link (application.runtime.link)
static doa_frame_input_t frame,held;
static doa_solve_output_t solved;
static const doa_servo_config_t map={1U,23040,1,-23040,23040,0U,180U,180U};

static void item(const char *name,int ok)
{
    if(ok) ++passes;else ++fails;
    printf("CHECK,%s,%s\r\n",name,ok?"PASS":"FAIL");
}
static void skip(const char *name,const char *why)
{ ++skips;printf("CHECK,%s,SKIP,%s\r\n",name,why); }
static void synthetic(int pass)
{
    const int32_t reject[6]=ABI_BIST_REJECT_LAGS_INITIALIZER;
    const int32_t accept[6]=ABI_BIST_PASS_LAGS_INITIALIZER;
    unsigned int i;
    memset(&frame,0,sizeof(frame));frame.frame_id=1U;frame.flags=ABI_BIST_FRAME_FLAGS;
    for(i=0U;i<6U;++i) {
        frame.pair[i].lag=pass?accept[i]:reject[i];
        frame.pair[i].peak=ABI_BIST_PEAK;frame.pair[i].r_minus=ABI_BIST_LEFT;
        frame.pair[i].r_plus=pass?ABI_BIST_PASS_RIGHT:ABI_BIST_REJECT_RIGHT;
        frame.pair[i].second_peak=ABI_BIST_SECOND;frame.pair[i].mask_count=ABI_BIST_MASK_COUNT;
        frame.pair[i].flags=ABI_BIST_PAIR_FLAGS;
    }
}
static int expected(int pass)
{
    const int32_t rt[6]=ABI_BIST_REJECT_TAU_INITIALIZER;
    const int32_t pt[6]=ABI_BIST_PASS_TAU_INITIALIZER;
    unsigned int i;
    if(solved.ux_q20!=(pass?ABI_BIST_PASS_UX_Q20:ABI_BIST_REJECT_UX_Q20) ||
       solved.uy_q20!=(pass?0:ABI_BIST_REJECT_UY_Q20) ||
       solved.residual_square_q24!=(pass?0:ABI_BIST_REJECT_RESIDUAL_Q24) ||
       solved.direction_valid!=(uint8_t)pass || solved.direction_reason!=(pass?0:3) ||
       solved.servo_cmd_valid!=0U || solved.vertical_valid!=0U ||
       solved.valid_pair_count!=6U || solved.residual_limit_q24!=ABI_BIST_RESIDUAL_LIMIT_Q24)
        return 0;
    if(pass && (solved.norm_square_q40!=ABI_BIST_PASS_NORM_Q40 || solved.angle_q8!=0)) return 0;
    for(i=0U;i<6U;++i) if(solved.pair[i].tau_q12!=(pass?pt[i]:rt[i]) ||
        solved.pair[i].margin_q15!=ABI_BIST_MARGIN_Q15 ||
        solved.pair[i].delta_q12!=(pass?0:ABI_BIST_REJECT_DELTA_Q12) ||
        solved.pair[i].qualified!=1U) return 0;
    return 1;
}
static void numerical_line(const char *tag,uint32_t cycles,uint32_t us)
{
    printf("DATA,%s,frame=%lu,ux=%ld,uy=%ld,residual=%llu,valid=%u,reason=%u,angle_q8=%ld,servo_valid=%u,cycles=%lu,us=%lu\r\n",
        tag,(unsigned long)solved.frame_id,(long)solved.ux_q20,(long)solved.uy_q20,
        (unsigned long long)solved.residual_square_q24,(unsigned int)solved.direction_valid,
        (unsigned int)solved.direction_reason,(long)solved.angle_q8,
        (unsigned int)solved.servo_cmd_valid,(unsigned long)cycles,(unsigned long)us);
}
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
static void spatial_local_checks(void)
{
    static const int32_t tau[3][6]={{-5139,-19180,1254,-14041,6393,20434},{-19180,-5139,-17467,14041,1713,-12327},{0,0,18721,0,18721,18721}};
    static const int32_t expected_az[3]={11520,-11520,0};
    static const int32_t expected_el[3]={7680,-7680,23040};
    static const char *names[3]={"D1_TETRA_UP","D1_TETRA_DOWN","D1_TETRA_POLE"};
    doa3d_config_t cfg; doa_dispatch_output_t out;
    unsigned int k,i; uint32_t cycles,us; int ok;
    doa3d_default_config(&cfg);
    for(k=0U;k<3U;++k) {
        memset(&frame,0,sizeof(frame)); frame.frame_id=k+1U; frame.flags=SNAP_STATUS_ALL_TERMINAL;
        for(i=0U;i<6U;++i) {
            int32_t q=tau[k][i],lag=(q>=0?q+2048:q-2048)/4096,delta=q-lag*4096;
            doa_pair_input_t *p=&frame.pair[i];
            p->lag=lag;p->peak=100000;p->r_minus=95904-2*delta;p->r_plus=95904+2*delta;
            p->second_peak=10000;p->mask_count=79;
            p->flags=FEATURE_0_RAW_PEAK_VALID|FEATURE_0_SECOND_VALID|FEATURE_0_IFFT_QUALIFIED|
                (UINT32_C(1)<<FEATURE_0_PHAT_STAGE_SHIFT)|(UINT32_C(1)<<FEATURE_0_IFFT_STAGE_SHIFT);
        }
        cycles=DWT->CYCCNT;us=ss_board_us();
        ok=doa_dispatch_solve(&frame,NULL,&cfg,&out)==DOA_OK;
        cycles=DWT->CYCCNT-cycles;us=ss_board_us()-us;
        ok=ok && out.profile==1U && out.direction_valid && out.elevation_valid &&
            out.spatial.reason==DOA3D_VALID && out.spatial.coordinates_measured==0U &&
            out.elevation_q8>=expected_el[k]-8 && out.elevation_q8<=expected_el[k]+8 &&
            out.azimuth_valid==(uint8_t)(k!=2U) && out.azimuth_q8>=expected_az[k]-8 &&
            out.azimuth_q8<=expected_az[k]+8;
        item(names[k],ok);
        printf("DATA,TETRA_SYNTHETIC,frame=%lu,az_q8=%ld,el_q8=%ld,az_valid=%u,el_valid=%u,reason=%u,cycles=%lu,us=%lu,NOMINAL_NOT_MEASURED,NO_SPI_NO_ACTION\r\n",
            (unsigned long)frame.frame_id,(long)out.azimuth_q8,(long)out.elevation_q8,
            (unsigned int)out.azimuth_valid,(unsigned int)out.elevation_valid,(unsigned int)out.spatial.reason,
            (unsigned long)cycles,(unsigned long)us);
    }
}
#endif
static void fpga_skips(const char *why)
{
    skip("FPGA_ID_ABI",why);skip("FPGA_SPI_BIST_REJECT",why);skip("FPGA_SPI_BIST_PASS",why);
    skip("FPGA_RELEASE_CONSUME",why);skip("FPGA_IRQ_LEVEL_EDGE",why);
    skip("FPGA_TIMEOUT_RECOVERY",why);skip("FPGA_MOTION_DISABLED",why);
}
static int irq_equals_status(void)
{
    uint32_t s=0U,start=ss_board_us(),spins=1000000U;
    if(ss_read_register(&link,REG_SNAP_STATUS,&s)!=SS_OK) return 0;
    do {
        if(ss_board_irq()==((s&SNAP_STATUS_IRQ)!=0U)) return 1;
    } while((uint32_t)(ss_board_us()-start)<5000U && --spins!=0U);
    return 0;
}
static ss_status_t wait_frame(int hold_lock)
{
    uint32_t start=ss_board_us();ss_status_t s;
    do {
        s=hold_lock?ss_acquire_frame(&link,&frame):ss_poll_solve(&link,&map,&frame,&solved);
        if(s!=SS_NO_FRAME) return s;
        if(!ss_board_wait_us(100U)) return SS_TIMEOUT;
    } while((uint32_t)(ss_board_us()-start)<500000U);
    return SS_TIMEOUT;
}
static int live_probe(void)
{
    ss_status_t s;uint32_t id=0U,abi=0U;
    s=ss_probe(&link);
    if(s==SS_OK)s=ss_read_register(&link,REG_MAGIC_ID,&id);
    if(s==SS_OK)s=ss_read_register(&link,REG_ABI_VERSION,&abi);
    printf("DATA,FPGA_ID_ABI,status=%u,id=0x%08lX,abi=0x%08lX\r\n",
           (unsigned int)s,(unsigned long)id,(unsigned long)abi);
    item("FPGA_ID_ABI",s==SS_OK && id==FPGA_ABI_MAGIC_VALUE && abi==FPGA_ABI_VERSION_VALUE);
    return s==SS_OK && id==FPGA_ABI_MAGIC_VALUE && abi==FPGA_ABI_VERSION_VALUE;
}
/* Each requested FPGA diagnostic explicitly disables and acknowledges ONLY
 * the resulting isolated STOP before selecting the next BIST. */
static int prepare_diagnostic(void)
{
    ss_status_t s=ss_disable(&link); uint32_t t=ss_board_us();
    if(s!=SS_OK) return 0;
    do {
        s=ss_acknowledge_stop(&link);
        if(s!=SS_BUSY) break;
        if(!ss_board_wait_us(100U)) return 0;
    } while((uint32_t)(ss_board_us()-t)<500000U);
    printf("DATA,DIAGNOSTIC_PREPARE,status=%u,only_isolated_STOP_acknowledged\r\n",(unsigned int)s);
    return s==SS_OK;
}
static void start_trace_line(void)
{
    const ss_start_trace_t *d=&link.start_trace;
    printf("DATA,START_TRACE,step=%u,op=%c,addr=0x%02lX,expected=0x%08lX,mask=0x%08lX,actual_valid=%u,actual=0x%08lX,bus_status=%u,result=%u,recovery=%u\r\n",
        (unsigned int)d->step,d->write?'W':'R',(unsigned long)d->address,
        (unsigned long)d->expected,(unsigned long)d->mask,(unsigned int)d->actual_valid,
        (unsigned long)d->actual,(unsigned int)d->bus_status,(unsigned int)d->result,
        (unsigned int)link.recovery_required);
}
static int live_bist(int pass)
{
    ss_status_t s;uint32_t first_id,before,us,cycles,irq_before=ss_board_stats.irq_edges;
    const char *name=pass?"FPGA_SPI_BIST_PASS":"FPGA_SPI_BIST_REJECT";
    if(!prepare_diagnostic()) {item(name,0);return 0;}
    s=ss_start(&link,pass?SS_RUN_BIST_PASS:SS_RUN_BIST_REJECT);
    start_trace_line();
    if(s!=SS_OK) {printf("DATA,START,status=%u,inspect_START_TRACE_do_not_auto_reset\r\n",(unsigned int)s);item(name,0);return 0;}
    s=wait_frame(1);
    if(s!=SS_OK) {printf("DATA,ACQUIRE,status=%u\r\n",(unsigned int)s);item(name,0);return 0;}
    held=frame;first_id=frame.frame_id;
    item("FPGA_IRQ_WHILE_LOCKED",ss_board_irq() && irq_equals_status());
    s=ss_finish_frame(&link,SS_RELEASE);
    if(s!=SS_OK) {item("FPGA_RELEASE",0);return 0;}
    /* Immediate reread of released READY frame must take exactly 40 transfers. */
    before=ss_board_stats.completed;us=ss_board_us();cycles=DWT->CYCCNT;
    s=ss_poll_solve(&link,&map,&frame,&solved);
    cycles=DWT->CYCCNT-cycles;us=ss_board_us()-us;
    printf("DATA,%s,transfers=%lu,status=%u\r\n",name,
           (unsigned long)(ss_board_stats.completed-before),(unsigned int)s);
    item("FPGA_RELEASE_SAME_FRAME",s==SS_OK && frame.frame_id==first_id && memcmp(&frame,&held,sizeof(frame))==0);
    item("SPI_SOFTWARE_40_TRANSACTIONS",s==SS_OK && ss_board_stats.completed-before==40U);
    item(name,s==SS_OK && expected(pass));
    if(s==SS_OK)numerical_line(name,cycles,us);
    item("FPGA_IRQ_AFTER_CONSUME",irq_equals_status() && !ss_board_irq());
    item("FPGA_IRQ_EXTI_EDGES",ss_board_stats.irq_edges>irq_before);
    return s==SS_OK && expected(pass);
}
static void live_timeout(void)
{
    ss_status_t s;uint32_t injected=ss_board_stats.timeout_count;
    if(!prepare_diagnostic()) {item("FPGA_TIMEOUT_PREPARE",0);return;}
    s=ss_start(&link,SS_RUN_BIST_PASS);
    if(s!=SS_OK) {item("FPGA_TIMEOUT_PREPARE",0);return;}
    ss_board_stats.inject_timeout=1U;
    memset(&solved,0x5A,sizeof(solved));
    s=ss_poll_solve(&link,&map,&frame,&solved);
    printf("DATA,TIMEOUT_TEST,kind=SOFTWARE_INJECT_BEFORE_CS,not_physical_bus_timeout\r\n");
    item("INJECTED_TIMEOUT_ISOLATION",s==SS_TIMEOUT && link.recovery_required &&
        solved.direction_valid==0U && solved.servo_cmd_valid==0U && frame.frame_id==0U &&
        ss_board_stats.timeout_count==injected+1U && (GPIOG->IDR&GPIO_PIN_7)!=0U);
    s=ss_recover(&link);
    item("FPGA_EXPLICIT_RECOVERY",s==SS_OK);
    if(s==SS_OK) {
        s=wait_frame(0);item("FPGA_AFTER_RECOVERY_BIST",s==SS_OK && expected(1));
    } else skip("FPGA_AFTER_RECOVERY_BIST","RECOVERY_FAILED");
}
static void safety_readback(void)
{
    uint32_t act=UINT32_MAX,wd=UINT32_MAX,fault=UINT32_MAX;
    ss_status_t a=ss_read_register(&link,REG_ACT_CTRL,&act);
    ss_status_t b=ss_read_register(&link,REG_WATCHDOG_TICKS,&wd);
    ss_status_t c=ss_read_register(&link,REG_FAULT_STATUS,&fault);
    printf("DATA,SAFETY_READ_STATUS,act=%u,watchdog=%u,fault=%u,last_error=%u,recovery=%u\r\n",
        (unsigned int)a,(unsigned int)b,(unsigned int)c,(unsigned int)link.last_error,
        (unsigned int)link.recovery_required);
    if(a==SS_OK && b==SS_OK && c==SS_OK)
        printf("DATA,SAFETY,act=%lu,watchdog=%lu,fault=0x%08lX\r\n",
            (unsigned long)act,(unsigned long)wd,(unsigned long)fault);
    else printf("DATA,SAFETY,INVALID_READBACK,values_not_reported\r\n");
    item("FPGA_MOTION_DISABLED",a==SS_OK && b==SS_OK && act==0U && wd==0U);
    item("FPGA_NO_UNEXPECTED_FAULT",c==SS_OK && fault==0U);
}
void ss_selftest_run(int live_fpga)
{
    uint32_t t0,u0,dt,du,c0,cy,min,max;unsigned int i,b;int timing,ok,all;
    ss_bus_t bus;ss_link_t local;uint8_t tx[5]={0x98U,0U,0U,0U,0U},rx[5];
    if(application.initialized!=0U && application.active!=0U) {printf("COMMAND,BUSY,stop_stream_first\r\n");return;}
    passes=0U;fails=0U;skips=0U;board_ok=0;
    printf("FIRMWARE_DIAG,P4_TIM2_GUARD_V2\r\n");
    printf("\r\nSELFTEST,BEGIN,mode=%s,motion_submission=DISABLED\r\n",live_fpga?"FPGA":"BOARD_ONLY");
    printf("CLOCK,sys=%lu,hclk=%lu,pclk1=%lu,pclk2=%lu,spi_calc=%lu\r\n",
        (unsigned long)HAL_RCC_GetSysClockFreq(),(unsigned long)HAL_RCC_GetHCLKFreq(),
        (unsigned long)HAL_RCC_GetPCLK1Freq(),(unsigned long)HAL_RCC_GetPCLK2Freq(),
        (unsigned long)(HAL_RCC_GetPCLK2Freq()/64U));
    item("CLOCK_128_32_64",HAL_RCC_GetSysClockFreq()==128000000U &&
        HAL_RCC_GetHCLKFreq()==128000000U && HAL_RCC_GetPCLK1Freq()==32000000U &&
        HAL_RCC_GetPCLK2Freq()==64000000U);
    item("TIM2_1US_COUNTER",ss_board_stats.timer_ready!=0U);
    t0=HAL_GetTick();u0=ss_board_us();c0=DWT->CYCCNT;
    timing=ss_board_wait_us(50000U);cy=DWT->CYCCNT-c0;
    du=ss_board_us()-u0;dt=HAL_GetTick()-t0;
    printf("TIMEBASE,hal_ms=%lu,tim2_us=%lu,dwt_cycles=%lu\r\n",
        (unsigned long)dt,(unsigned long)du,(unsigned long)cy);
    item("HAL_MILLISECOND_TICK",timing && dt>=48U && dt<=52U && du>=50000U && du<55000U &&
        SysTick->LOAD==127999U && (SysTick->CTRL&7U)==7U && __get_PRIMASK()==0U);
    item("DWT_COUNTER",timing && cy>6000000U && cy<7200000U);
    item("SPI_GPIO_CONFIGURATION",ss_board_configuration_ok());
    printf("REG,SPI1_CR1=0x%08lX,CR2=0x%08lX,GPIOB_MODER=0x%08lX,GPIOG_MODER=0x%08lX\r\n",
        (unsigned long)SPI1->CR1,(unsigned long)SPI1->CR2,(unsigned long)GPIOB->MODER,(unsigned long)GPIOG->MODER);
    item("CS_FLASH_SAFE_HIGH",(GPIOG->IDR&GPIO_PIN_7)!=0U && (GPIOB->IDR&GPIO_PIN_14)!=0U);
    bus=ss_board_bus();item("S2_CONTEXT_INIT",ss_init(&local,&bus)==SS_OK && !local.probed && !local.locked);
    /* These are blocked locally: ZERO physical SPI transactions. */
    item("ACTUATOR_WRITE_BLOCKED",bus.transfer(bus.user,tx,rx,5U)==SS_BUS_ERROR);
    tx[0]=0xD8U;tx[4]=1U;
    item("MOTION_PERMIT_BLOCKED",bus.transfer(bus.user,tx,rx,5U)==SS_BUS_ERROR);
    for(b=0U;b<2U;++b) {
        synthetic((int)b);min=UINT32_MAX;max=0U;all=1;cy=0U;du=0U;
        for(i=0U;i<32U;++i) {
            u0=ss_board_us();c0=DWT->CYCCNT;
            ok=doa_solve(&frame,&map,&solved)==DOA_OK;
            cy=DWT->CYCCNT-c0;du=ss_board_us()-u0;
            if(cy<min)min=cy;
            if(cy>max)max=cy;
            if(!ok || !expected((int)b))all=0;
        }
        item(b?"S1_BOARD_BIST_PASS":"S1_BOARD_BIST_REJECT",all);
        numerical_line(b?"S1_PASS":"S1_REJECT",cy,du);
        printf("PERF,S1_%s,runs=32,min_cycles=%lu,max_cycles=%lu,clock_hz=128000000\r\n",
               b?"PASS":"REJECT",(unsigned long)min,(unsigned long)max);
    }
    printf("APP_PROFILE,%u,legacy_BIST=PLANAR_TRANSPORT,motion=DISABLED\r\n",(unsigned int)SS_DOA_PROFILE);
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    spatial_local_checks();
#endif
    if(application.initialized==0U) {
        bus=ss_board_bus(); item("P3_APP_INIT",ss_app_init(&application,&bus)==SS_OK);
    } else item("P3_APP_INIT",1);
    item("P2_BUILD_GATE_CLOSED",ss_motion_build_enabled()==0);
    board_ok=fails==0U;
    if(!live_fpga) fpga_skips("FPGA_NOT_REQUESTED_OR_CONNECTED");
    else if(!board_ok) fpga_skips("BOARD_CHECKS_FAILED");
    else if(!live_probe()) {
        skip("FPGA_SPI_BIST_REJECT","ID_ABI_FAILED");skip("FPGA_SPI_BIST_PASS","ID_ABI_FAILED");
        skip("FPGA_RELEASE_CONSUME","ID_ABI_FAILED");skip("FPGA_IRQ_LEVEL_EDGE","ID_ABI_FAILED");
        skip("FPGA_TIMEOUT_RECOVERY","ID_ABI_FAILED");skip("FPGA_MOTION_DISABLED","ID_ABI_FAILED");
    } else {
        if(live_bist(0) && live_bist(1)) {
            live_timeout();
            if(fails==0U) item("FPGA_IDLE_AFTER_TEST",prepare_diagnostic());
        }
        else { skip("REMAINING_FPGA_TESTS","PRIOR_BIST_FAILED");(void)ss_stop(&link); }
        safety_readback();
    }
    skip("SPI_PHYSICAL_WAVEFORM","REQUIRES_SCOPE_OR_LOGIC_ANALYZER_1MHz_40CLOCKS_CS_SETUP_HOLD");
    skip("PHYSICAL_BUS_STALL_TIMEOUT","SOFTWARE_INJECTION_IS_NOT_ELECTRICAL_STALL_TEST");
    skip("REAL_STREAM_QUEUE","RUN_stream_COMMAND_WITH_READY_REAL_SOURCE");
    skip("ACTUAL_PWM_MOVEMENT","INTENTIONALLY_DISABLED");
    printf("SUMMARY,scope=%s,pass=%u,fail=%u,skip=%u,result=%s,NOT_SYSTEM_ACCEPTANCE\r\n",
        live_fpga?"FPGA_DIAGNOSTIC":"BOARD_ONLY",passes,fails,skips,
        fails?"FAIL":skips?"PASS_WITH_SKIPS":"PASS");
    printf("COMMANDS,board / fpga / stream / status / stop / recover / ackstop / discard / config N MS EVERY / motion (CRLF)\r\n");
}
static void app_status(void)
{
    printf("LINK_DIAG,last_error=%u,recovery=%u,start_result=%u,start_step=%u\r\n",
        (unsigned int)link.last_error,(unsigned int)link.recovery_required,
        (unsigned int)link.start_trace.result,(unsigned int)link.start_trace.step);
    printf("APP,status=%u,state=%u,active=%u,frames=%lu,rejected=%lu,queued=%lu,drops=%lu,max_step_ms=%lu,producer_idle=%u,motion_gate=%d,motion_state=%u,commit_outcome=%u,fault=0x%08lX,first_error=%u,max_frames=%lu,duration_ms=%lu,print_every=%lu\r\n",
        (unsigned int)application.last_status,(unsigned int)application.runtime.state,(unsigned int)application.active,
        (unsigned long)application.frames,(unsigned long)application.rejected,(unsigned long)application.queued,
        (unsigned long)application.drop_count,(unsigned long)application.max_step_ms,
        (unsigned int)application.runtime.producer_idle_observed,ss_motion_build_enabled(),
        (unsigned int)application.motion.state,(unsigned int)application.motion.outcome,
        (unsigned long)link.faults,(unsigned int)application.runtime.first_error,
        (unsigned long)application.config.max_frames,(unsigned long)application.config.duration_ms,
        (unsigned long)application.config.print_every);
}
void ss_selftest_stream(void)
{
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    printf("STREAM,SKIP,THREE_DIMENSIONAL_PROFILE_NOT_ALIGNED_WITH_A\r\n");
#else
    ss_status_t s;
    if(!board_ok) {printf("STREAM,SKIP,RUN_BOARD_CHECKS_FIRST\r\n");return;}
    s=ss_app_start(&application);
    printf("STREAM,BEGIN,status=%u,max_frames=%lu,deadline_ms=%lu,print_every=%lu,motion=DISABLED\r\n",
        (unsigned int)s,(unsigned long)application.config.max_frames,(unsigned long)application.config.duration_ms,
        (unsigned long)application.config.print_every);
#endif
}
static void app_tick(void)
{
    uint32_t t=ss_board_us();
    ss_app_event_t event=ss_app_step(&application);
    uint32_t us=ss_board_us()-t;
    if(event==SS_APP_FRAME && (application.frames==1U || application.frames%application.config.print_every==0U)) {
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
        printf("STREAM3D,frame=%lu,valid=%u,reason=%u,az_q8=%ld,el_q8=%ld,az_valid=%u,el_valid=%u,geometry_measured=%u,step_us=%lu,NO_ACTION_SUBMITTED\r\n",
            (unsigned long)application.frame.frame_id,(unsigned int)application.spatial_result.direction_valid,
            (unsigned int)application.spatial_result.spatial.reason,(long)application.spatial_result.azimuth_q8,
            (long)application.spatial_result.elevation_q8,(unsigned int)application.spatial_result.azimuth_valid,
            (unsigned int)application.spatial_result.elevation_valid,(unsigned int)application.spatial_result.spatial.coordinates_measured,
            (unsigned long)us);
#else
        printf("STREAM,frame=%lu,valid=%u,reason=%u,angle_q8=%ld,step_us=%lu,NO_ACTION_SUBMITTED\r\n",
            (unsigned long)application.frame.frame_id,(unsigned int)application.result.direction_valid,
            (unsigned int)application.result.direction_reason,(long)application.result.angle_q8,(unsigned long)us);
#endif
    }
    if(event==SS_APP_ENDED || event==SS_APP_ERROR) {
        const char *result=event==SS_APP_ERROR?"FAIL":application.user_stopped?"STOPPED":
            application.frames>=application.config.max_frames?"DIAGNOSTIC_COMPLETE":application.frames==0U?"SKIP_NO_FRAMES":"INCOMPLETE";
        app_status();
        printf("STREAM,END,result=%s,NOT_SYSTEM_ACCEPTANCE,ackstop_then_stream_for_next_run\r\n",result);
    }
}
void ss_selftest_command_poll(void)
{
    char command[64];uint16_t state,n;uint32_t mask;
    ss_status_t s=SS_OK; int handled=0;
    if((*(volatile uint16_t *)&g_usart_rx_sta & 0x8000U)!=0U) {
        mask=__get_PRIMASK();__disable_irq();
        state=g_usart_rx_sta;n=state&0x3FFFU;
        if(n<sizeof(command)) {memcpy(command,g_usart_rx_buf,n);command[n]='\0';}
        g_usart_rx_sta=0U;__set_PRIMASK(mask);
        if(n>=sizeof(command)) printf("COMMAND,REJECT,LENGTH\r\n");
        else if(strcmp(command,"status")==0)app_status();
        else if(strcmp(command,"stop")==0) {s=ss_app_stop(&application);handled=1;}
        else if(strcmp(command,"recover")==0) {s=ss_app_recover(&application);handled=1;}
        else if(strcmp(command,"ackstop")==0) {s=ss_app_ack_stop(&application);handled=1;}
        else if(strcmp(command,"discard")==0) {
            s=ss_app_discard(&application);handled=1;
            printf("DISCARD,status=%u,frame=%lu,NO_ACTION\r\n",(unsigned int)s,(unsigned long)application.frame.frame_id);
        }
        else if(strcmp(command,"motion")==0) {s=ss_app_arm(&application);handled=1;printf("MOTION,DISABLED,build_gate=%d\r\n",ss_motion_build_enabled());}
        else if(strncmp(command,"config ",7U)==0) {
            ss_app_config_t c;s=ss_app_parse_config(command+7,&c);
            if(s==SS_OK)s=ss_app_configure(&application,&c);
            handled=1;
        }
        else if(strcmp(command,"board")==0)ss_selftest_run(0);
        else if(strcmp(command,"fpga")==0)ss_selftest_run(1);
        else if(strcmp(command,"stream")==0)ss_selftest_stream();
        else printf("COMMANDS,board / fpga / stream / status / stop / recover / ackstop / discard / config N MS EVERY / motion; CRLF\r\n");
        if(handled)printf("COMMAND,%s,status=%u\r\n",command,(unsigned int)s);
    }
    if(application.initialized!=0U)app_tick();
}
