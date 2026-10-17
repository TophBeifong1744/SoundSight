#ifndef SOUNDSIGHT_RUNTIME_H
#define SOUNDSIGHT_RUNTIME_H
#include "fpga_link.h"
#include "doa_dispatch.h"

/* P1: diagnostic runtime, exclusive main-loop ownership of link/bus.
 * Zero-initialize before first init. Never call from IRQ or concurrently.
 * All fields below are read-only to callers after successful init.
 * Re-init is a deliberate new session, NOT error recovery. No allocation/HAL.
 */
typedef enum {
    SS_RT_IDLE = 0, SS_RT_PROBING, SS_RT_STARTING, SS_RT_RUNNING,
    SS_RT_STOPPING, SS_RT_DRAINING, SS_RT_STOPPED, SS_RT_FAULT,
    SS_RT_RECOVERING, SS_RT_RESUMING
} ss_runtime_state_t;
typedef enum {
    SS_RT_NONE = 0, SS_RT_STATE_CHANGED, SS_RT_FRAME_VALID,
    SS_RT_FRAME_REJECTED, SS_RT_ERROR
} ss_runtime_event_t;
typedef struct {
    uint32_t poll_interval_ms, start_timeout_ms, drain_timeout_ms;
} ss_runtime_config_t; /* each >0 and <2^31; monotonic clock required */
typedef struct {
    ss_link_t link;
    ss_runtime_config_t config;
    ss_runtime_state_t state;
    ss_run_t mode;
    ss_status_t first_error, last_error;
    uint32_t state_since_ms, last_poll_ms;
    uint32_t frames, rejected_frames, empty_polls, errors, recoveries;
    uint8_t initialized, poll_pending, fresh_result;
    uint8_t resume_allowed, stop_attempted, stop_sent, producer_idle_observed;
    doa_frame_input_t frame;
    doa_solve_output_t result; /* planar only; stays zero in 3D */
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    doa3d_config_t spatial_config; /* D1 nominal geometry, read-only */
    doa_dispatch_output_t spatial_result;
#endif
} ss_runtime_t;

ss_status_t ss_runtime_init(ss_runtime_t *runtime, const ss_bus_t *bus,
                            const ss_runtime_config_t *config);
/* Requests queue a transition, perform NO I/O, invalidate the current result.
 * start: IDLE/STOPPED only. recover: FAULT/STOPPED only, never clears faults.
 * resume: IDLE after explicit recovery, previously started same session only;
 * checks existing enabled mode and never writes enable or replays CONSUME.
 */
ss_status_t ss_runtime_start(ss_runtime_t *runtime, ss_run_t mode);
ss_status_t ss_runtime_stop(ss_runtime_t *runtime);
ss_status_t ss_runtime_recover(ss_runtime_t *runtime);
ss_status_t ss_runtime_resume(ss_runtime_t *runtime);
/* Bounded synchronous work; no loop waiting for a frame/IRQ. Call regularly
 * (elapsed intervals must stay <2^31 ms). Result lasts only until next step or
 * request, including a rejected request. Frame events mean ALREADY CONSUMED;
 * result must never be used for a later actuator commit. No servo mapping.
 * RUNNING reads faults then calls S2: 1 guard + 40 frame transfers on success.
 * FAULT/IDLE/STOPPED perform no automatic traffic. STOPPED only describes host;
 * producer_idle_observed additionally means disabled + no drain was read back,
 * NOT a physical PWM measurement. A completed STOP transfer alone is not proof.
 */
ss_runtime_event_t ss_runtime_step(ss_runtime_t *runtime);
#endif
