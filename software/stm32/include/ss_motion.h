#ifndef SOUNDSIGHT_MOTION_H
#define SOUNDSIGHT_MOTION_H
#include "fpga_link.h"

/* P2 standalone command manager. Exclusive link ownership while in use;
 * P1 must NOT concurrently call poll_solve/step on this link. P3 integrates.
 * Build gate SS_ENABLE_MOTION_WRITES defaults to 0. The board adapter's
 * independent physical write gate is unchanged. Init never arms the device.
 */
typedef enum { SS_MOTION_DISARMED=0, SS_MOTION_ARMED, SS_MOTION_FAULT } ss_motion_state_t;
typedef enum {
    SS_MOTION_NONE=0, SS_MOTION_GATE_CLOSED, SS_MOTION_EMPTY,
    SS_MOTION_REJECTED, SS_MOTION_SUBMITTED_UNCONFIRMED,
    SS_MOTION_UNCERTAIN, SS_MOTION_ERROR
} ss_motion_outcome_t;
typedef struct {
    doa_servo_config_t servo; /* explicit mechanical calibration, no default */
    uint32_t watchdog_ticks; /* PL processing clocks, never HAL milliseconds */
    uint32_t max_frame_hold_ms; /* acquisition-to-COMMIT bound, NOT capture age */
    uint8_t allow_submission; /* runtime opt-in, must ALSO pass build gate */
} ss_motion_config_t;
typedef struct {
    ss_link_t *link;
    ss_motion_config_t config;
    ss_motion_state_t state;
    ss_motion_outcome_t outcome;
    ss_status_t first_error, last_error, stop_result;
    uint32_t last_attempted_frame, report_frame;
    uint16_t report_target;
    uint8_t initialized, have_attempted, stop_attempted;
    uint8_t commit_attempted, commit_transfer_completed, consume_completed;
} ss_motion_t; /* fields read-only after init; no memset/reinit to bypass fence */

int ss_motion_build_enabled(void);
ss_status_t ss_motion_init(ss_motion_t *, ss_link_t *, const ss_motion_config_t *);
/* Arm only after S2 probe/start REAL. Revoke, configure/verify watchdog, then
 * request/read back permit. No auto rearm, no heartbeat/watchdog refresh writes.
 */
ss_status_t ss_motion_arm(ss_motion_t *);
ss_status_t ss_motion_disarm(ss_motion_t *);
/* One STOP attempt until explicit recover; completion is NOT PWM stop proof. */
ss_status_t ss_motion_stop(ss_motion_t *);
/* Recover releases actual locked slot, preserves attempted-frame fence and
 * faults, ends DISARMED. No restart/rearm/replay. Sticky faults stay FAULT. */
ss_status_t ss_motion_recover(ss_motion_t *);
/* Bounded acquire/solve/check/shadow/COMMIT/check/CONSUME under one S2 budget.
 * No caller-supplied result may be committed. Rejected direction revokes and
 * consumes once, ends DISARMED. NO_FRAME leaves watchdog running, no refresh.
 * Errors clear output, quarantine and best-effort revoke; diagnostics above
 * preserve commit ambiguity. SS_OK + SUBMITTED_UNCONFIRMED is transport plus
 * postchecks only: frozen ABI has no acceptance receipt or capture timestamp.
 */
ss_status_t ss_motion_poll(ss_motion_t *, doa_frame_input_t *, doa_solve_output_t *);
#endif
