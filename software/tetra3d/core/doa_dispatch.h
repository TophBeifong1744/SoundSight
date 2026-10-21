#ifndef SOUNDSIGHT_DOA_DISPATCH_H
#define SOUNDSIGHT_DOA_DISPATCH_H
#include "doa_solver_3d.h"
#define SS_DOA_PLANAR 0
#define SS_DOA_TETRAHEDRAL 1
#ifndef SS_DOA_PROFILE
#define SS_DOA_PROFILE SS_DOA_PLANAR
#endif
#if SS_DOA_PROFILE != SS_DOA_PLANAR && SS_DOA_PROFILE != SS_DOA_TETRAHEDRAL
#error Unsupported SS_DOA_PROFILE
#endif
typedef struct {
    uint8_t profile, direction_valid, azimuth_valid, elevation_valid;
    int32_t azimuth_q8, elevation_q8;
    /* Profile-specific originals retained; unused branch remains zero. */
    doa_solve_output_t planar;
    doa3d_output_t spatial;
} doa_dispatch_output_t;
/* Compile ALL users and doa_dispatch.c with the same SS_DOA_PROFILE.
 * Does not change the old ss_poll_solve API, which remains 2D.
 * For 3D use S2 acquire -> this call -> finish(CONSUME); no action submission. */
doa_status_t doa_dispatch_solve(const doa_frame_input_t *frame,
    const doa_servo_config_t *planar_servo, const doa3d_config_t *spatial_config,
    doa_dispatch_output_t *result);
#endif
