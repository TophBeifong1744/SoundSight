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
#endif

