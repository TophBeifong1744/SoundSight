#include "soundsight_board.h"
#include <string.h>

/* Board ownership: SPI1 PB3/4/5, CS PG7, EXTI8 PG8, Flash deselect PB14,
 * TIM2 free-running 1MHz time guard. No DMA, no SPI IRQ, no actuator writes.
 * Clock tree/USART1/SysTick remain owned by the verified base project.
 */
volatile ss_board_stats_t ss_board_stats;
#define SS_SPI_CR1 (SPI_CR1_MSTR | SPI_CR1_SSM | SPI_CR1_SSI | SPI_CR1_BR_2 | SPI_CR1_BR_0)
#define SS_LOOP_LIMIT UINT32_C(2000000)

uint32_t ss_board_us(void) { return TIM2->CNT; }
int ss_board_wait_us(uint32_t us)
{
    uint32_t start=ss_board_us(), n=SS_LOOP_LIMIT;
    if (!ss_board_stats.timer_ready || us>100000U) return 0;
    while ((uint32_t)(ss_board_us()-start)<us) if (--n==0U) return 0;
    return 1;
}
int ss_board_irq(void) { return (GPIOG->IDR & GPIO_PIN_8)!=0U; }
void EXTI9_5_IRQHandler(void)
{
    if ((EXTI->PR & GPIO_PIN_8)!=0U) {
        EXTI->PR=GPIO_PIN_8;
        ++ss_board_stats.irq_edges;
        __DSB();
    }
}
static void spi_reset(void)
{
    __HAL_RCC_SPI1_FORCE_RESET(); __DSB();
    __HAL_RCC_SPI1_RELEASE_RESET();
    SPI1->CR2=0U;
    SPI1->CR1=SS_SPI_CR1 | SPI_CR1_SPE;
}
int ss_board_init(void)
{
    GPIO_InitTypeDef g;
    uint32_t start,n;
    memset((void *)&ss_board_stats,0,sizeof(ss_board_stats));
    __HAL_RCC_GPIOB_CLK_ENABLE(); __HAL_RCC_GPIOG_CLK_ENABLE();
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    /* Set latches BEFORE switching pads to outputs: no low CS glitch. */
    GPIOB->BSRR=GPIO_PIN_14; GPIOG->BSRR=GPIO_PIN_7;
    memset(&g,0,sizeof(g)); g.Mode=GPIO_MODE_OUTPUT_PP;g.Pull=GPIO_PULLUP;
    g.Speed=GPIO_SPEED_FREQ_HIGH;g.Pin=GPIO_PIN_14;HAL_GPIO_Init(GPIOB,&g);
    g.Pin=GPIO_PIN_7;HAL_GPIO_Init(GPIOG,&g);
    /* No SPI traffic is allowed unless the verified clocks are present. */
    if (HAL_RCC_GetHCLKFreq()!=128000000U || HAL_RCC_GetPCLK1Freq()!=32000000U ||
        HAL_RCC_GetPCLK2Freq()!=64000000U) return 0;
    __HAL_RCC_TIM2_CLK_ENABLE(); __HAL_RCC_TIM2_FORCE_RESET();
    __HAL_RCC_TIM2_RELEASE_RESET();
    TIM2->CR1=0U;TIM2->PSC=63U;TIM2->ARR=UINT32_MAX;TIM2->DIER=0U;
    TIM2->EGR=TIM_EGR_UG;TIM2->SR=0U;TIM2->CNT=0U;TIM2->CR1=TIM_CR1_CEN;
    start=TIM2->CNT;
    for(n=0U;n<10000U && TIM2->CNT==start;++n) { __NOP(); }
    if(TIM2->CNT==start) return 0;
    ss_board_stats.timer_ready=1U;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    /* No SWO output is configured; PB3 remains SPI1 SCK. */
    DWT->CYCCNT=0U;DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    g.Pin=GPIO_PIN_3|GPIO_PIN_4|GPIO_PIN_5;g.Mode=GPIO_MODE_AF_PP;
    g.Pull=GPIO_PULLUP;g.Speed=GPIO_SPEED_FREQ_HIGH;g.Alternate=GPIO_AF5_SPI1;
    HAL_GPIO_Init(GPIOB,&g);
    /* SCK idle-low; MISO pull-up makes an unplugged peer read as all ones. */
    GPIOB->PUPDR &= ~(UINT32_C(3) << 6);
    __HAL_RCC_SPI1_CLK_ENABLE();spi_reset();
    g.Pin=GPIO_PIN_8;g.Mode=GPIO_MODE_IT_RISING_FALLING;g.Pull=GPIO_PULLDOWN;
    HAL_GPIO_Init(GPIOG,&g);
    EXTI->PR=GPIO_PIN_8;
    HAL_NVIC_SetPriority(EXTI9_5_IRQn,5U,0U);HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);
    ss_board_stats.spi_ready=1U;
    return ss_board_configuration_ok();
}
static uint32_t mode(GPIO_TypeDef *p,unsigned int pin)
{ return (p->MODER>>(pin*2U))&3U; }
static uint32_t af(GPIO_TypeDef *p,unsigned int pin)
{ return (p->AFR[pin/8U]>>((pin%8U)*4U))&15U; }
int ss_board_configuration_ok(void)
{
    return ss_board_stats.timer_ready && ss_board_stats.spi_ready &&
        SPI1->CR1==(SS_SPI_CR1|SPI_CR1_SPE) && SPI1->CR2==0U &&
        (SPI1->I2SCFGR & SPI_I2SCFGR_I2SMOD)==0U &&
        mode(GPIOB,3U)==2U && mode(GPIOB,4U)==2U && mode(GPIOB,5U)==2U &&
        af(GPIOB,3U)==5U && af(GPIOB,4U)==5U && af(GPIOB,5U)==5U &&
        mode(GPIOG,7U)==1U && mode(GPIOB,14U)==1U && mode(GPIOG,8U)==0U &&
        (GPIOG->OTYPER&GPIO_PIN_7)==0U && (GPIOB->OTYPER&GPIO_PIN_14)==0U &&
        ((GPIOG->PUPDR>>16)&3U)==2U &&
        (GPIOG->ODR&GPIO_PIN_7)!=0U && (GPIOB->ODR&GPIO_PIN_14)!=0U &&
        ((SYSCFG->EXTICR[2]&15U)==6U) && (EXTI->IMR&GPIO_PIN_8)!=0U &&
        (EXTI->RTSR&GPIO_PIN_8)!=0U && (EXTI->FTSR&GPIO_PIN_8)!=0U &&
        TIM2->PSC==63U && TIM2->ARR==UINT32_MAX && (TIM2->CR1&TIM_CR1_CEN)!=0U;
}
static int wait_sr(uint32_t mask,int set,uint32_t start,uint32_t budget)
{
    uint32_t n=SS_LOOP_LIMIT;
    while (((SPI1->SR&mask)!=0U)!=set) {
        if ((SPI1->SR&(SPI_SR_MODF|SPI_SR_OVR))!=0U) return -1;
        if ((uint32_t)(ss_board_us()-start)>=budget || --n==0U) return 0;
    }
    return (uint32_t)(ss_board_us()-start)<budget ? 1 : 0;
}
static int forbidden(const uint8_t tx[5])
{
    uint32_t a=tx[0]&0x7FU;
    uint32_t v=((uint32_t)tx[1]<<24)|((uint32_t)tx[2]<<16)|((uint32_t)tx[3]<<8)|tx[4];
    if((tx[0]&0x80U)==0U) return 0;
    if(a==REG_ACTUATOR_CMD) return 1;
    if(a==REG_ACT_CTRL && v!=0U && v!=ACT_CTRL_STOP && v!=ACT_CTRL_REVOKE) return 1;
    if(a==REG_WATCHDOG_TICKS && v!=0U) return 1;
    return 0;
}
static ss_bus_status_t transfer5(void *user,const uint8_t tx[5],uint8_t rx[5],uint32_t timeout_ms)
{
    uint32_t start,budget,elapsed;unsigned int i;int w=1;
    ss_bus_status_t result=SS_BUS_ERROR;
    (void)user;
    ++ss_board_stats.attempts;ss_board_stats.last_bytes=0U;
    if(tx==NULL || rx==NULL) return SS_BUS_ERROR;
    memset(rx,0,5U);
    if(forbidden(tx)) { ++ss_board_stats.blocked_actions;return SS_BUS_ERROR; }
    if(!ss_board_stats.spi_ready || !ss_board_stats.timer_ready || timeout_ms==0U ||
        timeout_ms>1000U || __get_IPSR()!=0U || __get_PRIMASK()!=0U) return SS_BUS_ERROR;
    if(ss_board_stats.inject_timeout) {
        ss_board_stats.inject_timeout=0U;GPIOG->BSRR=GPIO_PIN_7;
        ++ss_board_stats.timeout_count;return SS_BUS_TIMEOUT; /* clearly labelled software test */
    }
    start=ss_board_us();budget=timeout_ms*1000U;
    /* Flush any stale RX/OVR once, then restore exact SPI mode if unhealthy. */
    if((SPI1->SR&(SPI_SR_RXNE|SPI_SR_OVR|SPI_SR_MODF|SPI_SR_BSY))!=0U) spi_reset();
    if(!ss_board_wait_us(1U)) goto finish;
    GPIOG->BSRR=(uint32_t)GPIO_PIN_7<<16;
    if(!ss_board_wait_us(1U)) goto finish;
    for(i=0U;i<5U;++i) {
        w=wait_sr(SPI_SR_TXE,1,start,budget);if(w!=1) goto finish;
        *(__IO uint8_t *)&SPI1->DR=tx[i];
        w=wait_sr(SPI_SR_RXNE,1,start,budget);if(w!=1) goto finish;
        rx[i]=*(__IO uint8_t *)&SPI1->DR;
        ++ss_board_stats.last_bytes;
    }
    w=wait_sr(SPI_SR_TXE,1,start,budget);if(w!=1) goto finish;
    w=wait_sr(SPI_SR_BSY,0,start,budget);if(w!=1) goto finish;
    if((SPI1->SR&(SPI_SR_OVR|SPI_SR_MODF))!=0U) goto finish;
    result=SS_BUS_OK;
finish:
    if(!ss_board_wait_us(1U)) result=SS_BUS_ERROR;
    GPIOG->BSRR=GPIO_PIN_7; /* EVERY asserted-CS exit releases the peer */
    if(!ss_board_wait_us(1U)) result=SS_BUS_ERROR;
    elapsed=ss_board_us()-start;
    if(w==0 || elapsed>=budget) result=SS_BUS_TIMEOUT;
    if(elapsed>ss_board_stats.max_us) ss_board_stats.max_us=elapsed;
    if(result==SS_BUS_OK) ++ss_board_stats.completed;
    else {
        spi_reset();memset(rx,0,5U);
        if(result==SS_BUS_TIMEOUT) ++ss_board_stats.timeout_count;
        else ++ss_board_stats.io_errors;
    }
    return result;
}
static uint32_t board_ms(void *user) { (void)user;return HAL_GetTick(); }
ss_bus_t ss_board_bus(void)
{
    ss_bus_t b;
    b.user=NULL;b.transfer=transfer5;b.now_ms=board_ms;
    b.transfer_timeout_ms=5U;b.operation_timeout_ms=100U;
    return b;
}
