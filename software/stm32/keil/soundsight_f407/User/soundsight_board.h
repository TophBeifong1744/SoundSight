#ifndef SOUNDSIGHT_BOARD_H
#define SOUNDSIGHT_BOARD_H
#include "stm32f4xx_hal.h"
#include "fpga_link.h"

typedef struct {
    uint32_t attempts, completed, timeout_count, io_errors, blocked_actions;
    uint32_t last_bytes, max_us, irq_edges;
    uint8_t timer_ready, spi_ready, inject_timeout;
} ss_board_stats_t;
extern volatile ss_board_stats_t ss_board_stats;
int ss_board_init(void);
int ss_board_configuration_ok(void);
uint32_t ss_board_us(void);
int ss_board_wait_us(uint32_t us);
int ss_board_irq(void);
ss_bus_t ss_board_bus(void);
void ss_selftest_run(int live_fpga);
void ss_selftest_stream(void);
void ss_selftest_command_poll(void);
#endif
