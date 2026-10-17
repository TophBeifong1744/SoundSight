#include "doa_solver.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

static const int32_t pair_dx[DOA_PAIR_COUNT] = {1, 1, 0, 0, -1, -1};
static const int32_t pair_dy[DOA_PAIR_COUNT] = {0, 1, 1, 1, 1, 0};
/* doa_math_pkg.sv atan_rom, degrees * 65536, entries 0..23. */
static const int32_t atan_q16[24] = {
    2949120, 1740967, 919879, 466945, 234379, 117304,
    58666, 29335, 14668, 7334, 3667, 1833,
    917, 458, 229, 115, 57, 29, 14, 7, 4, 2, 1, 0
};

/* Private bounded arithmetic. Inputs are validated before every call:
 * |n| < 2^46 and 0 < d < 2^31. No INT64_MIN negation or overflow in 2*r.
 */
static int64_t rne_div(int64_t n, int64_t d)
{
    int64_t a, q, r;
    int negative;
    if (d <= 0) return 0; /* Original reference behavior, including den=0. */
    negative = n < 0;
    a = negative ? -n : n;
    q = a / d;
    r = a % d;
    if (r * INT64_C(2) > d ||
        (r * INT64_C(2) == d && q % INT64_C(2) != 0)) ++q;
    return negative ? -q : q;
}

/* Exact SV >>> for the bounded CORDIC operands, independent of C's
 * implementation-defined right shift of a negative signed integer.
 */
static int64_t arithmetic_shift(int64_t n, unsigned int amount)
{
    int64_t divisor = (int64_t)(UINT64_C(1) << amount);
    int64_t q = n / divisor;
    if (n < 0 && n % divisor != 0) --q;
    return q;
}

static int32_t canonical_q8(int64_t angle)
{
    if (angle >= INT64_C(46080)) angle -= INT64_C(92160);
    if (angle < -INT64_C(46080)) angle += INT64_C(92160);
    return (int32_t)angle;
}

static int32_t float_rne_q8(float degrees)
{
    float scaled = degrees * 256.0f;
    float magnitude = fabsf(scaled);
    uint32_t whole = (uint32_t)floorf(magnitude);
    float fraction = magnitude - (float)whole;
    if (fraction > 0.5f || (fraction == 0.5f && (whole % 2U) != 0U)) ++whole;
    return canonical_q8(scaled < 0.0f ? -(int64_t)whole : (int64_t)whole);
}

doa_status_t doa_angles_from_vector(int32_t ux_q20, int32_t uy_q20,
                                   doa_angles_t *result)
{
    int64_t ux = ux_q20, uy = uy_q20;
    int64_t ax, ay, cx, cy, ca = 0, offset, scale;
    uint32_t maximum;
    unsigned int bits = 0, i;
    float difference;
    if (result == NULL) return DOA_BAD_ARGUMENT;
    memset(result, 0, sizeof(*result));
    if (ux < -INT64_C(4194304) || ux > INT64_C(4194303) ||
        uy < -INT64_C(4194304) || uy > INT64_C(4194303) || (ux == 0 && uy == 0))
        return DOA_NUMERIC_RANGE;
    ax = ux < 0 ? -ux : ux;
    ay = uy < 0 ? -uy : uy;
    maximum = (uint32_t)(ax > ay ? ax : ay);
    while (maximum != 0U) { ++bits; maximum /= 2U; }
    scale = (int64_t)(UINT64_C(1) << (24U - bits));
    cx = ax * scale;
    cy = (ux < 0 ? -uy : uy) * scale;
    offset = ux < 0 ? (uy >= 0 ? INT64_C(11796480) : -INT64_C(11796480)) : 0;
    for (i = 0; i < 24U; ++i) {
        int64_t old_cx = cx, old_cy = cy; /* SV nonblocking RHS use old values. */
        if (old_cy > 0) {
            cx = old_cx + arithmetic_shift(old_cy, i);
            cy = old_cy - arithmetic_shift(old_cx, i);
            ca += atan_q16[i];
        } else if (old_cy < 0) {
            cx = old_cx - arithmetic_shift(old_cy, i);
            cy = old_cy + arithmetic_shift(old_cx, i);
            ca -= atan_q16[i];
        }
    }
    result->angle_q8 = canonical_q8(rne_div(ca + offset, INT64_C(256)));
    result->atan2_deg = atan2f((float)uy_q20, (float)ux_q20) *
                         (180.0f / 3.14159265358979323846f);
    if (result->atan2_deg >= 180.0f) result->atan2_deg -= 360.0f;
    if (result->atan2_deg < -180.0f) result->atan2_deg += 360.0f;
    result->atan2_q8 = float_rne_q8(result->atan2_deg);
    difference = (float)result->angle_q8 / 256.0f - result->atan2_deg;
    if (difference >= 180.0f) difference -= 360.0f;
    if (difference < -180.0f) difference += 360.0f;
    result->cordic_minus_atan2_deg = difference;
    return DOA_OK;
}

doa_map_status_t doa_map_angle_q8(int32_t angle_q8,
                                const doa_servo_config_t *config,
                                doa_servo_result_t *result)
{
    int64_t mapped, rounded;
    if (result == NULL) return DOA_MAP_ARGUMENT;
    memset(result, 0, sizeof(*result));
    result->status = DOA_MAP_DISABLED;
    if (config == NULL || config->config_valid == 0U) return result->status;
    result->status = DOA_MAP_CONFIG;
    if (config->config_valid != 1U ||
        (config->direction != 1 && config->direction != -1) ||
        config->offset_q8 < -INT32_C(8388608) || config->offset_q8 > INT32_C(8388607) ||
        config->domain_min_q8 < -INT32_C(46080) || config->domain_max_q8 >= INT32_C(46080) ||
        config->domain_min_q8 > config->domain_max_q8 ||
        config->mechanical_min > config->mechanical_max ||
        config->mechanical_max > config->servo_max || config->servo_max == 0U ||
        config->servo_max > 511U) return result->status;
    result->config_legal = 1U;
    result->status = DOA_MAP_CANONICAL;
    if (angle_q8 < -INT32_C(46080) || angle_q8 >= INT32_C(46080)) return result->status;
    result->status = DOA_MAP_DOMAIN;
    if (angle_q8 < config->domain_min_q8 || angle_q8 > config->domain_max_q8) return result->status;
    mapped = (int64_t)config->offset_q8 + (int64_t)config->direction * angle_q8;
    result->status = DOA_MAP_MECHANICAL;
    if (mapped < (int64_t)config->mechanical_min * INT64_C(256) ||
        mapped > (int64_t)config->mechanical_max * INT64_C(256)) return result->status;
    rounded = rne_div(mapped, INT64_C(256));
    if (rounded > config->servo_max || rounded > 511) return result->status;
    result->angle_deg = (uint16_t)rounded;
    result->valid = 1U;
    result->status = DOA_MAP_OK;
    return result->status;
}

static int s25(int32_t x) { return x >= DOA_S25_MIN && x <= DOA_S25_MAX; }

static doa_status_t validate_pair(const doa_pair_input_t *p)
{
    uint32_t phat = FEATURE_0_GET_PHAT_STAGE(p->flags);
    uint32_t ifft = FEATURE_0_GET_IFFT_STAGE(p->flags);
    if (!s25(p->peak) || !s25(p->r_minus) || !s25(p->r_plus) || !s25(p->second_peak) ||
        p->lag < -32 || p->lag > 31 || p->mask_count > 79U) return DOA_INPUT_RANGE;
    if ((p->flags & ~DOA_PAIR_FLAGS_MASK) != 0U || phat > FPGA_STAGE_SKIPPED ||
        ifft > FPGA_STAGE_SKIPPED || phat == FPGA_STAGE_PENDING || ifft == FPGA_STAGE_PENDING)
        return DOA_INPUT_FLAGS;
    return DOA_OK;
}

static int stage_error(uint32_t stage)
{
    return stage == FPGA_STAGE_NUMERIC || stage == FPGA_STAGE_PROTOCOL;
}

static void evaluate_pair(const doa_pair_input_t *p, unsigned int index,
                          uint8_t bist, doa_pair_result_t *r)
{
    int64_t denominator, numerator, delta, magnitude;
    int32_t tau_limit = (index == 1U || index == 4U) ? 32425 : 22928;
    int stage_ok;
    uint32_t phat = FEATURE_0_GET_PHAT_STAGE(p->flags);
    uint32_t ifft = FEATURE_0_GET_IFFT_STAGE(p->flags);
    r->reason = DOA_PAIR_MASK;
    if (p->mask_count < 12U) return;
    r->reason = DOA_PAIR_STAGE;
    if (bist != 0U) {
        stage_ok = phat == FPGA_STAGE_SKIPPED && ifft == FPGA_STAGE_SKIPPED &&
                   (p->flags & FEATURE_0_IFFT_QUALIFIED) == 0U;
    } else {
        stage_ok = phat == FPGA_STAGE_OK && ifft == FPGA_STAGE_OK &&
                   (p->flags & FEATURE_0_IFFT_QUALIFIED) != 0U;
    }
    if ((p->flags & FEATURE_0_RAW_PEAK_VALID) == 0U || !stage_ok) return;
    denominator = (int64_t)p->r_minus - INT64_C(2) * p->peak + p->r_plus;
    numerator = ((int64_t)p->r_minus - p->r_plus) * INT64_C(2048);
    if (denominator < 0) { denominator = -denominator; numerator = -numerator; }
    delta = rne_div(numerator, denominator);
    if (delta > 2048) delta = 2048;
    if (delta < -2048) delta = -2048;
    r->delta_q12 = (int32_t)delta;
    r->tau_q12 = p->lag * INT32_C(4096) + r->delta_q12;
    numerator = ((int64_t)p->peak - ((p->flags & FEATURE_0_SECOND_VALID) != 0U ? p->second_peak : 0)) * INT64_C(32768);
    magnitude = p->peak < 0 ? -(int64_t)p->peak : (int64_t)p->peak;
    if (magnitude == 0) magnitude = 1;
    r->margin_q15 = rne_div(numerator, magnitude);
    r->reason = DOA_PAIR_TAU;
    if (r->tau_q12 > tau_limit || r->tau_q12 < -tau_limit) return;
    r->qualified = 1U;
    r->reason = DOA_PAIR_OK;
}

doa_status_t doa_solve(const doa_frame_input_t *frame, const doa_servo_config_t *servo,
                       doa_solve_output_t *result)
{
    int64_t sxx = 0, syy = 0, sxy = 0, bx = 0, by = 0, det, ux, uy;
    unsigned int i;
    int cancelled, source_error;
    uint8_t bist;
    doa_status_t status;
    doa_angles_t angles;
    doa_servo_result_t horizontal;
    if (result == NULL) return DOA_BAD_ARGUMENT;
    memset(result, 0, sizeof(*result));
    result->bad_pair_index = DOA_NO_BAD_PAIR;
    result->direction_reason = DOA_SOURCE_ERROR;
    result->servo_map_status = DOA_MAP_DISABLED;
    for (i = 0; i < DOA_PAIR_COUNT; ++i) result->pair[i].reason = DOA_PAIR_NOT_EVALUATED;
    if (frame == NULL) return DOA_BAD_ARGUMENT;
    result->frame_id = frame->frame_id;
    result->first_error_code = (uint8_t)SNAP_STATUS_GET_FIRST_ERROR(frame->flags);
    if ((frame->flags & ~DOA_FRAME_FLAGS_MASK) != 0U) return DOA_INPUT_FLAGS;
    if ((frame->flags & SNAP_STATUS_FRAME_CANCELLED) != 0U) {
        result->direction_reason = DOA_CANCELLED; return DOA_OK;
    }
    if ((frame->flags & SNAP_STATUS_ALL_TERMINAL) == 0U) return DOA_INCOMPLETE_FRAME;
    bist = (uint8_t)((frame->flags & SNAP_STATUS_BIST) != 0U);
    cancelled = 0;
    source_error = result->first_error_code != 0U;
    /* Validate every field before arithmetic, never partially solve a bad frame. */
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        const doa_pair_input_t *p = &frame->pair[i];
        status = validate_pair(p);
        if (status != DOA_OK) { result->bad_pair_index = (uint8_t)i; return status; }
        if ((p->flags & FEATURE_0_CANCELLED) != 0U ||
            FEATURE_0_GET_PHAT_STAGE(p->flags) == FPGA_STAGE_CANCELLED ||
            FEATURE_0_GET_IFFT_STAGE(p->flags) == FPGA_STAGE_CANCELLED) cancelled = 1;
        if ((p->flags & FEATURE_0_NUMERIC_ERROR) != 0U ||
            stage_error(FEATURE_0_GET_PHAT_STAGE(p->flags)) ||
            stage_error(FEATURE_0_GET_IFFT_STAGE(p->flags))) source_error = 1;
    }
    if (cancelled) { result->direction_reason = DOA_CANCELLED; return DOA_OK; }
    if (source_error) return DOA_OK;
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        doa_pair_result_t *p = &result->pair[i];
        evaluate_pair(&frame->pair[i], i, bist, p);
        if (p->qualified != 0U) {
            int64_t dx = pair_dx[i], dy = pair_dy[i];
            bx += dx * p->tau_q12; by += dy * p->tau_q12;
            sxx += dx * dx; syy += dy * dy; sxy += dx * dy;
            ++result->valid_pair_count;
            result->valid_pair_mask = (uint8_t)(result->valid_pair_mask | (uint8_t)(1U << i));
        }
    }
    det = sxx * syy - sxy * sxy;
    result->determinant = (int32_t)det;
    result->residual_limit_q24 = (uint64_t)result->valid_pair_count * UINT64_C(4194304);
    if (result->valid_pair_count < 3U) { result->direction_reason = DOA_INSUFFICIENT_PAIRS; return DOA_OK; }
    if (det <= 0) { result->direction_reason = DOA_SINGULAR; return DOA_OK; }
    ux = rne_div((syy * bx - sxy * by) * INT64_C(87808), det * INT64_C(1920));
    uy = rne_div((sxx * by - sxy * bx) * INT64_C(87808), det * INT64_C(1920));
    if (ux < -INT64_C(4194304) || ux > INT64_C(4194303) ||
        uy < -INT64_C(4194304) || uy > INT64_C(4194303)) {
        result->first_error_code = 10U;
        return DOA_NUMERIC_RANGE;
    }
    result->ux_q20 = (int32_t)ux; result->uy_q20 = (int32_t)uy;
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        if (result->pair[i].qualified != 0U) {
            int64_t direction = (int64_t)pair_dx[i] * ux + (int64_t)pair_dy[i] * uy;
            int64_t predicted = rne_div(direction * INT64_C(7864320), INT64_C(343) * INT64_C(1048576));
            int64_t residue = predicted - result->pair[i].tau_q12;
            result->residual_square_q24 += (uint64_t)(residue * residue);
        }
    }
    result->norm_square_q40 = (uint64_t)(ux * ux + uy * uy);
    if (result->residual_square_q24 > result->residual_limit_q24) {
        result->direction_reason = DOA_RESIDUAL_REJECT; return DOA_OK;
    }
    if (result->norm_square_q40 < UINT64_C(10995200164) ||
        result->norm_square_q40 > UINT64_C(1858175196201)) {
        result->direction_reason = DOA_NORM_REJECT; return DOA_OK;
    }
    status = doa_angles_from_vector(result->ux_q20, result->uy_q20, &angles);
    if (status != DOA_OK) { result->first_error_code = 10U; return status; }
    result->angle_q8 = angles.angle_q8;
    result->atan2_angle_q8 = angles.atan2_q8;
    result->atan2_deg = angles.atan2_deg;
    result->angle_difference_deg = angles.cordic_minus_atan2_deg;
    result->direction_valid = 1U;
    result->direction_reason = DOA_DIRECTION_OK;
    (void)doa_map_angle_q8(result->angle_q8, servo, &horizontal);
    result->horizontal_servo_deg = horizontal.angle_deg;
    result->horizontal_map_valid = horizontal.valid;
    result->servo_config_legal = horizontal.config_legal;
    result->servo_map_status = horizontal.status;
    result->servo_cmd_valid = (uint8_t)(bist == 0U && horizontal.valid != 0U);
    return DOA_OK;
}
