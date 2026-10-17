#ifndef SS_LINK_INTERNAL_H
#define SS_LINK_INTERNAL_H
/* Private composition API: one owner, one operation deadline. Not wire ABI. */
#include "fpga_link.h"
#ifndef SS_ENABLE_MOTION_WRITES
#define SS_ENABLE_MOTION_WRITES 0
#endif
#if SS_ENABLE_MOTION_WRITES != 0 && SS_ENABLE_MOTION_WRITES != 1
#error SS_ENABLE_MOTION_WRITES must be 0 or 1
#endif
ss_status_t ss_link_acquire_at(ss_link_t *, uint32_t, doa_frame_input_t *);
ss_status_t ss_link_finish_at(ss_link_t *, uint32_t, ss_finish_t);
ss_status_t ss_link_read_at(ss_link_t *, uint32_t, uint32_t, uint32_t *);
ss_status_t ss_link_motion_write_at(ss_link_t *, uint32_t, uint32_t, uint32_t);
ss_status_t ss_link_fail(ss_link_t *, ss_status_t);
#endif
