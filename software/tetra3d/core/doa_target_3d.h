#ifndef SS_DOA_TARGET_3D_H
#define SS_DOA_TARGET_3D_H
#include "doa_solver_3d.h"
#define DOA_TARGET3D_API_VERSION UINT32_C(0x00010000)
/* Pure software pointing model: aligned orthogonal yaw/pitch axes, 1:1 angle
 * scale. No SPI format, motion permit, PWM, rate limiting or freshness proof. */
typedef struct {
    uint32_t revision; /* nonzero; change with calibration/configuration */
    uint8_t enable_mapping; /* 0 default; mathematical mapping only, NOT arm */
    doa_servo_config_t horizontal;
    doa_servo_config_t vertical; /* domain restricted to [-90,+90] degrees */
} doa_target3d_config_t;
typedef enum {
    DOA_TARGET3D_OK=0, DOA_TARGET3D_ARGUMENT, DOA_TARGET3D_DISABLED,
    DOA_TARGET3D_CONFIG, DOA_TARGET3D_SOLVER_ERROR, DOA_TARGET3D_DIRECTION_REJECTED,
    DOA_TARGET3D_AXIS_UNOBSERVABLE, DOA_TARGET3D_ANGLE_RANGE,
    DOA_TARGET3D_AXIS_LIMIT
} doa_target3d_status_t;
typedef struct {
    uint32_t frame_id, config_revision;
    doa_target3d_status_t status;
    uint8_t software_target_valid, axes_evaluated;
    doa_map_status_t horizontal_status, vertical_status;
    uint16_t horizontal_deg, vertical_deg; /* both zero unless aggregate valid */
} doa_target3d_output_t;
/* Example only: zero=90, direction=+1, input [-90,+90], output [0,180].
 * NOT mechanical calibration. enable_mapping remains 0. */
void doa_target3d_example_config(doa_target3d_config_t *);
/* Return 1 only for a structurally legal enabled configuration. */
int doa_target3d_config_valid(const doa_target3d_config_t *);
/* Call with actual status/output of doa3d_solve. Always clears output first.
 * Both axes required; no hold-last, clamping, wrap-around or partial target.
 * Stateless: frame_id is a label, NOT freshness/consume/commit authorization.
 * Inputs and output must not overlap; caller retains ownership of config.
 * A valid result must never be passed to P2 as a delayed device command. */
doa_target3d_status_t doa_target3d_map(doa_status_t solve_status,
    const doa3d_output_t *,const doa_target3d_config_t *,doa_target3d_output_t *);
#endif
