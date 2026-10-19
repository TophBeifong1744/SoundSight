/* Tests selftest orchestration using the existing independent register model.
 * Does not compile/emulate soundsight_board.c or prove GPIO/SPI timing. */
#define main s2_register_regression_main
#include "test_fpga_link.c"
#undef main
#include "soundsight_board.h"
#include "doa_dispatch.h"
#include <stdlib.h>

GPIO_TypeDef host_b,host_g;
SPI_TypeDef host_spi;
SysTick_Type host_tick;
DWT_Type host_dwt;
uint16_t g_usart_rx_sta;
uint8_t g_usart_rx_buf[200];
volatile ss_board_stats_t ss_board_stats;
static mock_t device;
static int bad_tick,bad_config,bad_start,bad_acquire;
uint32_t HAL_GetTick(void) { return bad_tick?0U:device.clock_ms; }
uint32_t HAL_RCC_GetSysClockFreq(void) { return 128000000U; }
uint32_t HAL_RCC_GetHCLKFreq(void) { return 128000000U; }
uint32_t HAL_RCC_GetPCLK1Freq(void) { return 32000000U; }
uint32_t HAL_RCC_GetPCLK2Freq(void) { return 64000000U; }
int ss_board_init(void) { return 1; }
int ss_board_configuration_ok(void) { return !bad_config; }
uint32_t ss_board_us(void) { return device.clock_ms*1000U; }
int ss_board_wait_us(uint32_t us)
{ device.clock_ms+=(us+999U)/1000U;host_dwt.CYCCNT+=us*128U;return 1; }
int ss_board_irq(void) { return (status(&device)&UINT32_C(0x4000))!=0U; }
static ss_bus_status_t host_transfer(void *unused,const uint8_t tx[5],uint8_t rx[5],uint32_t timeout)
{
    int old_irq=ss_board_irq();ss_bus_status_t r;uint32_t a=tx[0]&0x7FU,v=load32(&tx[1]);
    (void)unused;++ss_board_stats.attempts;
    if((tx[0]&0x80U)!=0U && (a==0x18U || (a==0x58U && v!=0U && v!=2U && v!=4U) || (a==0x60U && v!=0U))) {
        ++ss_board_stats.blocked_actions;return SS_BUS_ERROR;
    }
    if(ss_board_stats.inject_timeout) {
        ss_board_stats.inject_timeout=0U;++ss_board_stats.timeout_count;return SS_BUS_TIMEOUT;
    }
    r=transfer(&device,tx,rx,timeout);
    if(bad_start && r==SS_BUS_OK && tx[0]==0x04U && device.ctrl==10U) {
        store32(&rx[1],8U); bad_start=0; /* mode write/readback mismatch */
    }
    if(bad_acquire && r==SS_BUS_OK && tx[0]==0x0CU && device.bist==1U && device.select==3U) {
        store32(&rx[1],load32(&rx[1])^UINT32_C(0x100)); bad_acquire=0;
    }
    if(r==SS_BUS_OK)++ss_board_stats.completed;
    if(ss_board_irq()!=old_irq)++ss_board_stats.irq_edges;
    return r;
}
ss_bus_t ss_board_bus(void)
{ ss_bus_t b={NULL,host_transfer,NULL,5U,100U};b.now_ms=now_ms;b.user=&device;return b; }
static void command(const char *s)
{
    size_t n=strlen(s);
    CHECK("test command fits UART",n<sizeof(g_usart_rx_buf));
    memcpy(g_usart_rx_buf,s,n);g_usart_rx_sta=(uint16_t)(UINT16_C(0x8000)|(uint16_t)n);
    ++device.clock_ms;ss_selftest_command_poll();
}
static void command_tests(void)
{
    unsigned int before=device.count;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    command("stream"); command("motion"); command("status");
    CHECK("3D live gate no bus I/O",device.count==before && device.consumes==0U);
    puts("D1_COMMANDS,PASS,unaligned_3D_stream_blocked,no_motion");
#else
    command("config -1 2000 4");command("config 2 2000 1");
    command("streamXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX");
    CHECK("bad command no I/O",device.count==before);
    command("stream");++device.clock_ms;ss_selftest_command_poll();
    command("board"); /* busy, not an interleaved owner */
    publish(&device,packet(1,0,1U));++device.clock_ms;ss_selftest_command_poll();
    publish(&device,packet(1,0,2U));++device.clock_ms;ss_selftest_command_poll();
    ++device.clock_ms;ss_selftest_command_poll();
    ++device.clock_ms;ss_selftest_command_poll();
    CHECK("command stream consumed exactly twice",device.consumes==2U && device.ctrl==8U && device.fault==64U);
    command("status");command("ackstop");
    CHECK("explicit command clears only STOP",device.fault==0U);
    command("stream");++device.clock_ms;ss_selftest_command_poll();command("motion");command("stop");
    ++device.clock_ms;ss_selftest_command_poll();
    CHECK("command stop reaches disabled",device.ctrl==8U && device.consumes==2U);
    CHECK("no forbidden writes",device.action_writes==0U && device.permit_writes==0U);
    printf("COMMAND_TESTS,PASS,nonblocking_stream,busy_board,strict_config,length,STOP_ack,no_motion\n");
#endif
}
int main(int argc,char **argv)
{
    int live=0;
    memset(&device,0,sizeof(device));
    device.magic=UINT32_C(0x5A5A2026);device.version=UINT32_C(0x10000);device.ctrl=8U;device.duration_ms=1U;device.strict_control=1;
    ss_board_stats.timer_ready=1U;ss_board_stats.spi_ready=1U;
    host_g.IDR=GPIO_PIN_7;host_b.IDR=GPIO_PIN_14;host_tick.LOAD=127999U;host_tick.CTRL=7U;
    if(argc>1) {
        live=strcmp(argv[1],"board")!=0;
        if(strcmp(argv[1],"commands")==0)live=0;
        if(strcmp(argv[1],"no_peer")==0)device.magic=UINT32_MAX;
        if(strcmp(argv[1],"dead_tick")==0)bad_tick=1;
        if(strcmp(argv[1],"bad_config")==0)bad_config=1;
        if(strcmp(argv[1],"bad_start")==0)bad_start=1;
        if(strcmp(argv[1],"bad_acquire")==0)bad_acquire=1;
    }
    printf("HOST_MODEL_ONLY,NOT_BOARD_MEASUREMENT\n");
    ss_selftest_run(live);
    if(argc>1 && strcmp(argv[1],"commands")==0)command_tests();
    printf("HOST_MODEL,physical_model_transfers=%u,forbidden_writes=%u,checks=%u,failures=%u\n",
           device.count,device.action_writes+device.permit_writes,checks,failures);
    return failures==0U?0:1;
}
