/**
 ****************************************************************************************************
 * @file        main.c
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2021-10-14
 * @brief       template 实验
 * @license     Copyright (c) 2020-2032, 广州市星翼电子科技有限公司
 ****************************************************************************************************
 * @attention
 *
 * 实验平台：正点原子 探索者 F407开发板
 * 在线视频：www.yuanzige.com
 * 技术论坛：http://www.openedv.com/forum.php
 * 公司网址：www.alientek.com
 * 购买地址：zhengdianyuanzi.tmall.com
 *
 ****************************************************************************************************
 */

#include "./SYSTEM/sys/sys.h"
#include "./SYSTEM/usart/usart.h"
#include "./SYSTEM/delay/delay.h"
#include <stdio.h>
#include "soundsight_board.h"


void led_init(void);                    /* LED初始化函数声明 */


int main(void)
{
    uint32_t led_time;
    uint8_t clock_status;
    HAL_Init();
    clock_status = sys_stm32_clock_init(256, 8, 2, 8);
    delay_init(128);
    usart_init(115200);
    led_init();
    HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_SET);
    printf("\r\nSoundSight STM32 boot\r\n");
    printf("SYSCLK = %lu Hz\r\n", (unsigned long)HAL_RCC_GetSysClockFreq());
    printf("HCLK   = %lu Hz\r\n", (unsigned long)HAL_RCC_GetHCLKFreq());
    printf("PCLK1  = %lu Hz\r\n", (unsigned long)HAL_RCC_GetPCLK1Freq());
    printf("PCLK2  = %lu Hz\r\n", (unsigned long)HAL_RCC_GetPCLK2Freq());
    printf("BOOT,clock_init=%u,board_init=%d\r\n", (unsigned int)clock_status, ss_board_init());
    ss_selftest_run(0); /* No FPGA transfer at boot. */
    led_time = HAL_GetTick();
    while (1)
    {
        ss_selftest_command_poll();
        if ((uint32_t)(HAL_GetTick() - led_time) >= 500U)
        {
            led_time = HAL_GetTick();
            HAL_GPIO_TogglePin(GPIOF, GPIO_PIN_9 | GPIO_PIN_10);
        }
    }
}

/**
 * @brief       初始化LED相关IO口, 并使能时钟
 * @param       无
 * @retval      无
 */
void led_init(void)
{
    GPIO_InitTypeDef gpio_init_struct;
    
    __HAL_RCC_GPIOF_CLK_ENABLE();                       /* LED0，LED1时钟使能 */

    gpio_init_struct.Pin = GPIO_PIN_9;                  /* LED0引脚 */
    gpio_init_struct.Mode = GPIO_MODE_OUTPUT_PP;        /* 推挽输出 */
    gpio_init_struct.Pull = GPIO_PULLUP;                /* 上拉 */
    gpio_init_struct.Speed = GPIO_SPEED_FREQ_HIGH;      /* 高速 */
    HAL_GPIO_Init(GPIOF, &gpio_init_struct);            /* 初始化LED0引脚 */

    gpio_init_struct.Pin = GPIO_PIN_10;                 /* LED1引脚 */
    HAL_GPIO_Init(GPIOF, &gpio_init_struct);            /* 初始化LED1引脚 */

    HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET); /* LED0 灭 */
    HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_SET);/* LED1 灭 */
}
