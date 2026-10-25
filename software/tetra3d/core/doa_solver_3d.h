#ifndef SOUNDSIGHT_DOA_SOLVER_3D_H
#define SOUNDSIGHT_DOA_SOLVER_3D_H
/* Additive development API, not a replacement for frozen S1/SPI ABI v1.
 * Far-field direction only. No hardware I/O and no actuator command output. */
#include "doa_solver.h"
#define DOA3D_API_VERSION UINT32_C(0x00010000)
typedef enum {
    DOA3D_VALID=0, DOA3D_PAIRS=1, DOA3D_SINGULAR=2,
    DOA3D_RESIDUAL=3, DOA3D_NORM=4, DOA3D_LEGACY_BIST=5,
    DOA3D_CANCELLED=6, DOA3D_SOURCE=7, DOA3D_CONFIG=8,
    DOA3D_CONDITION=9
} doa3d_reason_t;
typedef struct {
    /* x forward, y left, z up; sound-hole centres, in channel 0..3 order. */
    float mic_mm[4][3];
    float sample_rate_hz, sound_speed_m_s;
    float max_normal_condition, max_residual_rms_samples;
    float norm_min, norm_max, tau_slack_samples;
    uint8_t min_pairs;
    uint8_t coordinates_measured; /* provenance only; nominal defaults are 0 */
} doa3d_config_t;
typedef struct {
    uint32_t frame_id;
    doa3d_reason_t reason;
    uint8_t direction_valid, azimuth_valid, elevation_valid;
    uint8_t valid_pair_count, valid_pair_mask, coordinates_measured;
    uint8_t first_error_code, bad_pair_index;
    doa_pair_result_t pair[6];
    float ux, uy, uz; /* fitted vector BEFORE normalization; check norm first */
    float norm, residual_rms_samples, normal_condition;
    float azimuth_deg, elevation_deg;
    int32_t azimuth_q8, elevation_q8;
} doa3d_output_t;
/* Additive optional processing. Original config/output structs are unchanged.
 * Delays are indexed by wire channel, not physical geometry row order.
 * Positive delay means captured audio arrives later than ideal; corrected
 * tau_ab = measured_tau_ab - (delay[a] - delay[b]). Values are samples. */
#define DOA3D_OPTIONS_VERSION UINT32_C(1)
typedef struct {
    uint32_t version;
    uint8_t quality_weighting;
    float quality_weight_floor; /* bounded margin weight, NOT probability */
    float channel_delay_samples[4]; /* finite [-1,1], zero means no calibration */
} doa3d_options_t;
/* Instance-owned immutable after init. No global mutable cache. Equal-weight
 * inverse matrices are indexed by all 64 possible qualified-pair masks.
 * Weighted fitting must build its matrix for that frame. */
typedef struct {
    doa3d_config_t config;
    doa3d_options_t options;
    double rows[6][3], bound[6];
    double inverse_by_mask[64][3][3], condition_by_mask[64];
    uint8_t invertible_by_mask[64];
    uint32_t ready;
} doa3d_prepared_t;
void doa3d_default_options(doa3d_options_t *options);
doa_status_t doa3d_prepare(const doa3d_config_t *config,
                         const doa3d_options_t *options,
                         doa3d_prepared_t *prepared);
doa_status_t doa3d_solve_prepared(const doa_frame_input_t *frame,
                                const doa3d_prepared_t *prepared,
                                doa3d_output_t *output);
/* Nominal regular 40 mm tetrahedron; centre at centroid, apex channel 3. */
void doa3d_default_config(doa3d_config_t *config);
/* DOA_OK can carry an algorithm rejection. Always inspect direction_valid.
 * Original PL BIST is rejected as DOA3D_LEGACY_BIST, not reinterpreted as 3D. */
doa_status_t doa3d_solve(const doa_frame_input_t *frame,
                       const doa3d_config_t *config, doa3d_output_t *output);
#endif
