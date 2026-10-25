#ifndef SS_SOLVER_3D_BRIDGE_H
#define SS_SOLVER_3D_BRIDGE_H
#include <stdint.h>
/* Local ctypes API, NOT a PL register ABI. All buffers are caller-owned,
 * non-overlapping and at least the stated size. No hardware access. */
#define SS3D_BRIDGE_VERSION UINT32_C(0x00010000)
#define SS3D_INFO_COUNT 14
#define SS3D_VALUE_COUNT 8
#define SS3D_PAIR_VALUE_COUNT 30
uint32_t ss3d_bridge_version(void);
/* geo: 4 physical rows xyz(mm), Fs(Hz), c(m/s), position error bound(mm).
 * meta: schema, revision, provenance (0 nominal/1 measured/2 synthetic),
 *       channel numbers for the four rows. source: 64 bytes, NUL terminated.
 * info: API status, valid, reason, az_valid, el_valid, az_q8, el_q8,
 *       pair_count, pair_mask, measured, first_error, bad_pair,
 *       geometry_status, geometry_bad_pair.
 * values: ux,uy,uz,norm,residual RMS(samples),normal condition,az(deg),el(deg).
 * pairs: six groups [delta_q12,tau_q12,margin_q15,qualified,reason].
 * Negative return: -1 argument, -2 status reserved bits, -3 not locked,
 * -4 feature reserved bits/pair echo, -5 geometry; ignore solve outputs.
 * Nonnegative return is doa_status_t; 0 may still carry direction_valid=0.
 * Geometry thresholds retain the original defaults. No motion targets. */
int ss3d_solve_words(uint32_t sequence, uint32_t status,
    const uint32_t words[30], const float geo[15], const uint32_t meta[7],
    const char source[64], int32_t info[SS3D_INFO_COUNT],
    float values[SS3D_VALUE_COUNT], int64_t pairs[SS3D_PAIR_VALUE_COUNT]);
/* Additive context API. The legacy symbol/version and output arrays above are
 * unchanged. Each context owns immutable geometry and mask caches; destroy only
 * when no caller is solving. No global shared cache, I/O, or fault clearing.
 * options_meta: schema(1), quality_weighting(0/1), min_pairs(4..6).
 * options: max_condition, residual_limit, norm_min, norm_max, tau_slack,
 *          quality_weight_floor, channel_delay_samples[0..3].
 * max_condition controls the frame fit only. The existing geometry builder
 * still applies its original full-geometry condition limit of 100 at create;
 * this option does not relax geometry acceptance.
 * NULL options_meta AND options select legacy defaults. Supplying only one is
 * invalid. Calibration sign/bounds follow doa_solver_3d.h. Raw pair tau fields
 * remain raw; residual and direction use corrected tau. Residual remains the
 * unweighted RMS over ALL qualified pairs, even when weighting is enabled.
 * create writes an opaque pointer on success, NULL otherwise: -5 geometry,
 * -6 options, -7 allocation; info contains geometry diagnostics as above.
 * Explicitly destroy the handle before unloading the dynamic library. */
#define SS3D_OPTIONS_SCHEMA UINT32_C(1)
#define SS3D_OPTIONS_META_COUNT 3
#define SS3D_OPTIONS_VALUE_COUNT 10
int ss3d_context_create(const float geo[15],const uint32_t meta[7],
    const char source[64],const uint32_t options_meta[3],const float options[10],
    int32_t info[SS3D_INFO_COUNT],void **context);
int ss3d_context_solve(const void *context,uint32_t sequence,uint32_t status,
    const uint32_t words[30],int32_t info[SS3D_INFO_COUNT],
    float values[SS3D_VALUE_COUNT],int64_t pairs[SS3D_PAIR_VALUE_COUNT]);
void ss3d_context_destroy(void *context);
#endif
