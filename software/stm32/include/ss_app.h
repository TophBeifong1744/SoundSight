#ifndef SS_APP_H
#define SS_APP_H
#include "ss_runtime.h"
#include "ss_motion.h"
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
#include "doa_geometry.h"
#endif
/* One main-loop owner only. IRQ may notify, but must not call this API.
 * Context members are diagnostic/read-only to callers; never re-init to clear
 * sequence/commit history. Only consume frame/result on SS_APP_FRAME (fresh).
 * All I/O is bounded and synchronous per step; UART logging is outside timing.
 * Production motion config is closed; example mapping is not calibrated.
 */
typedef struct { uint32_t max_frames, duration_ms, print_every; } ss_app_config_t;
typedef enum { SS_APP_NONE=0, SS_APP_FRAME, SS_APP_ENDED, SS_APP_ERROR } ss_app_event_t;
typedef struct {
    ss_runtime_t runtime;
    ss_motion_t motion;
    ss_app_config_t config;
    uint32_t started_ms, frames, rejected, queued, drop_count, max_step_ms;
    ss_status_t last_status;
    uint8_t initialized, active, fresh, user_stopped;
    doa_frame_input_t frame;
    doa_solve_output_t result; /* planar only; zero in 3D */
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    doa_dispatch_output_t spatial_result;
    doa_geometry_record_t geometry;
    doa_geometry_report_t geometry_report;
    uint8_t geometry_locked; /* sticky for this app lifetime; recovery never clears */
#endif
} ss_app_t;
ss_status_t ss_app_init(ss_app_t *,const ss_bus_t *);
ss_status_t ss_app_parse_config(const char *,ss_app_config_t *);
ss_status_t ss_app_configure(ss_app_t *,const ss_app_config_t *);
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
/* Cold-only, before any session/bus operation. No I/O; invalid/busy candidate
 * leaves installed record/config/report untouched. Do not re-init to unlock.
 * Source/revision describe declarations, not verified real-world calibration. */
ss_status_t ss_app_set_geometry(ss_app_t *,const doa_geometry_record_t *,
                                doa_geometry_report_t *);
#endif
ss_status_t ss_app_start(ss_app_t *);
ss_status_t ss_app_stop(ss_app_t *);
ss_status_t ss_app_arm(ss_app_t *); /* production config/build both closed */
ss_status_t ss_app_recover(ss_app_t *);
ss_status_t ss_app_ack_stop(ss_app_t *); /* explicit, only isolated STOP */
ss_status_t ss_app_discard(ss_app_t *); /* explicit diagnostic consume, no action */
ss_app_event_t ss_app_step(ss_app_t *);
#endif
