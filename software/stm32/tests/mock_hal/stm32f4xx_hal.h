/* Host-only orchestration stub. NEVER add this directory to Keil includes. */
#ifndef HOST_HAL_H
#define HOST_HAL_H
#include <stdint.h>
typedef struct { uint32_t IDR,MODER; } GPIO_TypeDef;
typedef struct { uint32_t CR1,CR2; } SPI_TypeDef;
typedef struct { uint32_t LOAD,CTRL; } SysTick_Type;
typedef struct { uint32_t CYCCNT; } DWT_Type;
extern GPIO_TypeDef host_b,host_g;
extern SPI_TypeDef host_spi;
extern SysTick_Type host_tick;
extern DWT_Type host_dwt;
#define GPIOB (&host_b)
#define GPIOG (&host_g)
#define SPI1 (&host_spi)
#define SysTick (&host_tick)
#define DWT (&host_dwt)
#define GPIO_PIN_7 (UINT32_C(1)<<7)
#define GPIO_PIN_14 (UINT32_C(1)<<14)
uint32_t HAL_GetTick(void);
uint32_t HAL_RCC_GetSysClockFreq(void);
uint32_t HAL_RCC_GetHCLKFreq(void);
uint32_t HAL_RCC_GetPCLK1Freq(void);
uint32_t HAL_RCC_GetPCLK2Freq(void);
static inline uint32_t __get_PRIMASK(void) { return 0U; }
static inline void __disable_irq(void) { }
static inline void __set_PRIMASK(uint32_t n) { (void)n; }
#endif
