#include "doa_solver.h"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static unsigned int checks = 0, failures = 0;
static const int32_t positive_lags[DOA_PAIR_COUNT] = ABI_BIST_PASS_LAGS_INITIALIZER;

static void expect_i(const char *label, int64_t actual, int64_t expected)
{
    ++checks;
    if (actual != expected) {
        ++failures;
        fprintf(stderr, "FAIL %s: expected=%" PRId64 " actual=%" PRId64 "\n", label, expected, actual);
    }
}
static void expect_true(const char *label, int condition) { expect_i(label, condition != 0, 1); }

/* Example only: actual mechanics are explicitly configured by the caller. */
static doa_servo_config_t example_servo(void)
{
    doa_servo_config_t c = {1U, 23040, 1, -23040, 23040, 0U, 180U, 180U};
    return c;
}

static doa_frame_input_t make_frame(const int32_t lags[DOA_PAIR_COUNT],
                              int32_t left, int32_t right, uint8_t bist)
{
    doa_frame_input_t f;
    unsigned int i;
    memset(&f, 0, sizeof(f));
    f.frame_id = 1U;
    f.flags = SNAP_STATUS_ALL_TERMINAL | (bist != 0U ? SNAP_STATUS_BIST : UINT32_C(0));
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        doa_pair_input_t *p = &f.pair[i];
        p->lag = lags[i]; p->peak = ABI_BIST_PEAK; p->r_minus = left; p->r_plus = right;
        p->second_peak = ABI_BIST_SECOND; p->mask_count = ABI_BIST_MASK_COUNT;
        p->flags = bist != 0U ? ABI_BIST_PAIR_FLAGS :
            FEATURE_0_RAW_PEAK_VALID | FEATURE_0_SECOND_VALID | FEATURE_0_IFFT_QUALIFIED |
            (UINT32_C(1) << FEATURE_0_PHAT_STAGE_SHIFT) | (UINT32_C(1) << FEATURE_0_IFFT_STAGE_SHIFT);
    }
    return f;
}

static void print_result(const char *name, const doa_frame_input_t *f, const doa_solve_output_t *r, int pairs)
{
    unsigned int i;
    if (pairs) for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        printf("PAIR,%s,%u,%" PRId32 ",%" PRId32 ",%" PRId32 ",%" PRId64 ",%u\n",
               name, i, f->pair[i].lag, r->pair[i].delta_q12, r->pair[i].tau_q12,
               r->pair[i].margin_q15, (unsigned int)r->pair[i].qualified);
    }
    printf("CASE,%s,%u,%d,%u,%" PRId32 ",%" PRId32 ",%" PRIu64 ",%" PRIu64
           ",%" PRId32 ",%.6f,%u,%u,%u\n", name,
           (unsigned int)r->direction_valid, (int)r->direction_reason,
           (unsigned int)r->valid_pair_count, r->ux_q20, r->uy_q20,
           r->residual_square_q24, r->norm_square_q40, r->angle_q8,
           (double)r->atan2_deg, (unsigned int)r->horizontal_map_valid,
           (unsigned int)r->horizontal_servo_deg, (unsigned int)r->servo_cmd_valid);
}

static void test_bist(void)
{
    const int32_t reject_lags[DOA_PAIR_COUNT] = ABI_BIST_REJECT_LAGS_INITIALIZER;
    const int32_t reject_tau[DOA_PAIR_COUNT] = ABI_BIST_REJECT_TAU_INITIALIZER;
    const int32_t accept_tau[DOA_PAIR_COUNT] = ABI_BIST_PASS_TAU_INITIALIZER;
    doa_frame_input_t f = make_frame(reject_lags, ABI_BIST_LEFT, ABI_BIST_REJECT_RIGHT, 1U);
    doa_servo_config_t servo = example_servo();
    doa_solve_output_t r;
    unsigned int i;
    expect_i("BIST reject API", doa_solve(&f, &servo, &r), DOA_OK);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        expect_i("BIST reject delta", r.pair[i].delta_q12, ABI_BIST_REJECT_DELTA_Q12);
        expect_i("BIST reject tau", r.pair[i].tau_q12, reject_tau[i]);
        expect_i("BIST reject margin", r.pair[i].margin_q15, ABI_BIST_MARGIN_Q15);
        expect_i("BIST reject pair qualification", r.pair[i].qualified, 1);
    }
    expect_i("BIST reject ux", r.ux_q20, ABI_BIST_REJECT_UX_Q20);
    expect_i("BIST reject uy", r.uy_q20, ABI_BIST_REJECT_UY_Q20);
    expect_i("BIST reject residual", (int64_t)r.residual_square_q24, (int64_t)ABI_BIST_REJECT_RESIDUAL_Q24);
    expect_i("BIST reject limit", (int64_t)r.residual_limit_q24, (int64_t)ABI_BIST_RESIDUAL_LIMIT_Q24);
    expect_i("BIST reject norm", (int64_t)r.norm_square_q40, INT64_C(31683992002));
    expect_i("BIST reject valid", r.direction_valid, 0);
    expect_i("BIST reject reason", r.direction_reason, 3);
    expect_i("BIST reject actuator", r.servo_cmd_valid, 0);
    print_result("BIST_REJECT", &f, &r, 1);

    f = make_frame(positive_lags, ABI_BIST_LEFT, ABI_BIST_PASS_RIGHT, 1U);
    expect_i("BIST pass API", doa_solve(&f, &servo, &r), DOA_OK);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        expect_i("BIST pass delta", r.pair[i].delta_q12, 0);
        expect_i("BIST pass tau", r.pair[i].tau_q12, accept_tau[i]);
        expect_i("BIST pass margin", r.pair[i].margin_q15, ABI_BIST_MARGIN_Q15);
    }
    expect_i("BIST pass ux", r.ux_q20, ABI_BIST_PASS_UX_Q20);
    expect_i("BIST pass uy", r.uy_q20, 0);
    expect_i("BIST pass residual", (int64_t)r.residual_square_q24, 0);
    expect_i("BIST pass norm", (int64_t)r.norm_square_q40, (int64_t)ABI_BIST_PASS_NORM_Q40);
    expect_i("BIST pass valid", r.direction_valid, 1);
    expect_i("BIST pass reason", r.direction_reason, 0);
    expect_i("BIST pass angle", r.angle_q8, 0);
    expect_i("BIST pass example servo", r.horizontal_servo_deg, 90);
    expect_i("BIST pass still blocks command", r.servo_cmd_valid, 0);
    expect_i("vertical disabled", r.vertical_valid, 0);
    print_result("BIST_ZERO", &f, &r, 1);
}

static void test_directions(void)
{
    static const struct {
        const char *name;
        int32_t lags[DOA_PAIR_COUNT], ux, uy, angle;
        uint64_t norm;
        uint16_t servo;
        uint8_t map_valid;
    } cases[] = {
        {"PLUS_45", {3,6,3,3,0,-3}, 561971,561971,11520, UINT64_C(631622809682),135U,1U},
        {"MINUS_45", {3,0,-3,-3,-6,-3}, 561971,-561971,-11520, UINT64_C(631622809682),45U,1U},
        {"PLUS_90", {0,4,4,4,4,0}, 0,749295,23040, UINT64_C(561442997025),180U,1U},
        {"MINUS_90", {0,-4,-4,-4,-4,0}, 0,-749295,-23040, UINT64_C(561442997025),0U,1U},
        {"PLUS_135_MAP_REJECT", {-3,0,3,3,6,3}, -561971,561971,34560, UINT64_C(631622809682),0U,0U},
        {"MINUS_135_MAP_REJECT", {-3,-6,-3,-3,0,3}, -561971,-561971,-34560, UINT64_C(631622809682),0U,0U},
        {"MINUS_180_MAP_REJECT", {-4,-4,0,0,4,4}, -749295,0,-46080, UINT64_C(561442997025),0U,0U},
        {"OFF_AXIS_14", {4,5,1,1,-3,-4}, 749295,187324,3593, UINT64_C(596533278001),104U,1U},
        {"OFF_AXIS_56", {2,5,3,3,1,-2}, 374647,561971,14415, UINT64_C(456171779450),146U,1U}
    };
    doa_servo_config_t servo = example_servo();
    unsigned int i;
    for (i = 0; i < (unsigned int)(sizeof(cases)/sizeof(cases[0])); ++i) {
        doa_frame_input_t f = make_frame(cases[i].lags, 800, 800, 0U);
        doa_solve_output_t r;
        expect_i(cases[i].name, doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("nonzero valid", r.direction_valid, 1);
        expect_i("nonzero reason", r.direction_reason, 0);
        expect_i("nonzero ux", r.ux_q20, cases[i].ux);
        expect_i("nonzero uy", r.uy_q20, cases[i].uy);
        expect_i("nonzero residual", (int64_t)r.residual_square_q24, 0);
        expect_i("nonzero norm", (int64_t)r.norm_square_q40, (int64_t)cases[i].norm);
        expect_i("nonzero integer angle", r.angle_q8, cases[i].angle);
        expect_i("nonzero float angle q8", r.atan2_angle_q8, cases[i].angle);
        expect_i("nonzero map valid", r.horizontal_map_valid, cases[i].map_valid);
        expect_i("nonzero servo", r.horizontal_servo_deg, cases[i].servo);
        expect_i("nonzero command candidate", r.servo_cmd_valid, cases[i].map_valid);
        expect_true("nonzero float agreement", fabsf(r.angle_difference_deg) < 0.004f);
        print_result(cases[i].name, &f, &r, 0);
    }
}

static void test_rejections(void)
{
    doa_servo_config_t servo = example_servo();
    doa_frame_input_t f = make_frame(positive_lags, 800, 800, 0U);
    doa_solve_output_t r;
    unsigned int i;
    for (i = 0; i < DOA_PAIR_COUNT; ++i) f.pair[i].mask_count = 11U;
    expect_i("mask11 API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("mask11 no pairs", r.valid_pair_count, 0);
    expect_i("mask11 reason", r.direction_reason, DOA_INSUFFICIENT_PAIRS);
    expect_i("mask11 command", r.servo_cmd_valid, 0);
    print_result("MASK_11_REJECT", &f, &r, 0);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) f.pair[i].mask_count = 12U;
    expect_i("mask12 API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("mask12 boundary pass", r.direction_valid, 1);
    for (i = 2; i < DOA_PAIR_COUNT; ++i) f.pair[i].flags &= ~FEATURE_0_RAW_PEAK_VALID;
    expect_i("two pairs API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("two pairs count", r.valid_pair_count, 2);
    expect_i("two pairs reject", r.direction_reason, DOA_INSUFFICIENT_PAIRS);
    print_result("TWO_PAIRS_REJECT", &f, &r, 0);

    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].peak = INT32_C(16777216);
    expect_i("S25 overflow API", doa_solve(&f, &servo, &r), DOA_INPUT_RANGE);
    expect_i("S25 bad pair", r.bad_pair_index, 0);
    expect_i("S25 invalid", r.direction_valid, 0);
    expect_i("S25 reason", r.direction_reason, DOA_SOURCE_ERROR);
    print_result("S25_RANGE_REJECT", &f, &r, 0);
    f.pair[0].peak = DOA_S25_MIN - 1;
    expect_i("S25 underflow", doa_solve(&f, &servo, &r), DOA_INPUT_RANGE);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].lag = 32;
    expect_i("S6 overflow", doa_solve(&f, &servo, &r), DOA_INPUT_RANGE);
    f.pair[0].lag = -33;
    expect_i("S6 underflow", doa_solve(&f, &servo, &r), DOA_INPUT_RANGE);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].mask_count = 80U;
    expect_i("mask exceeds band", doa_solve(&f, &servo, &r), DOA_INPUT_RANGE);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].flags |= UINT32_C(0x00800000);
    expect_i("malformed bool", doa_solve(&f, &servo, &r), DOA_INPUT_FLAGS);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].flags = (f.pair[0].flags & ~FEATURE_0_PHAT_STAGE_MASK) | (UINT32_C(7) << FEATURE_0_PHAT_STAGE_SHIFT);
    expect_i("unknown stage", doa_solve(&f, &servo, &r), DOA_INPUT_FLAGS);
    f.pair[0].flags &= ~FEATURE_0_PHAT_STAGE_MASK;
    expect_i("terminal frame cannot contain pending stage", doa_solve(&f, &servo, &r), DOA_INPUT_FLAGS);
    expect_i("pending stage reason", r.direction_reason, DOA_SOURCE_ERROR);
    expect_i("pending stage command rejected", r.servo_cmd_valid, 0);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.flags &= ~SNAP_STATUS_ALL_TERMINAL;
    expect_i("incomplete frame", doa_solve(&f, &servo, &r), DOA_INCOMPLETE_FRAME);

    f = make_frame(positive_lags, 800, 800, 0U);
    f.pair[0].flags |= FEATURE_0_NUMERIC_ERROR;
    expect_i("numeric source API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("numeric source reason", r.direction_reason, DOA_SOURCE_ERROR);
    f.pair[1].flags |= FEATURE_0_CANCELLED;
    expect_i("cancel precedence API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("cancel precedence", r.direction_reason, DOA_CANCELLED);
    f = make_frame(positive_lags, 800, 800, 0U);
    f.flags |= SNAP_STATUS_FRAME_CANCELLED; f.flags |= UINT32_C(8) << SNAP_STATUS_FIRST_ERROR_SHIFT;
    expect_i("frame cancel API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("frame cancel first", r.direction_reason, DOA_CANCELLED);
    expect_i("first error preserved", r.first_error_code, 8);

    f = make_frame(positive_lags, 800, 800, 0U);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) f.pair[i].lag = 0;
    expect_i("norm low API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("norm low reason", r.direction_reason, DOA_NORM_REJECT);
    print_result("ZERO_NORM_REJECT", &f, &r, 0);
    {
        const int32_t high_lags[DOA_PAIR_COUNT] = {5,11,5,5,0,-5};
        f = make_frame(high_lags, 800, 800, 0U);
        f.pair[0].r_plus = 1000; f.pair[2].r_plus = 1000; f.pair[3].r_plus = 1000;
        f.pair[5].r_minus = 1000;
        expect_i("norm high API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("norm high reason", r.direction_reason, DOA_NORM_REJECT);
        expect_true("norm high exceeds", r.norm_square_q40 > UINT64_C(1858175196201));
        print_result("HIGH_NORM_REJECT", &f, &r, 0);
    }
    f = make_frame(positive_lags, 800, 800, 0U);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) f.pair[i].flags &= ~FEATURE_0_IFFT_QUALIFIED;
    expect_i("IFFT required API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("IFFT required count", r.valid_pair_count, 0);
    expect_i("IFFT required reason", r.direction_reason, DOA_INSUFFICIENT_PAIRS);

    f = make_frame(positive_lags, 800, 800, 0U);
    expect_i("valid before stale clear", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("valid command before clear", r.servo_cmd_valid, 1);
    f.flags |= SNAP_STATUS_FRAME_CANCELLED;
    expect_i("cancel clears stale API", doa_solve(&f, &servo, &r), DOA_OK);
    expect_i("cancel clears stale servo", r.horizontal_servo_deg, 0);
    expect_i("cancel clears stale valid", r.horizontal_map_valid, 0);
    expect_i("cancel clears stale command", r.servo_cmd_valid, 0);
    expect_i("null frame", doa_solve(NULL, &servo, &r), DOA_BAD_ARGUMENT);
    expect_i("null result", doa_solve(&f, &servo, NULL), DOA_BAD_ARGUMENT);
    f = make_frame(positive_lags, 800, 800, 0U);
    expect_i("optional mapping API", doa_solve(&f, NULL, &r), DOA_OK);
    expect_i("optional mapping direction", r.direction_valid, 1);
    expect_i("optional mapping command", r.servo_cmd_valid, 0);
}

static void test_rounding_and_tau(void)
{
    static const struct { const char *name; int32_t peak, left, right, delta; } cases[] = {
        {"negative denominator half-even zero",8192,4097,4095,0},
        {"negative denominator half-even two",8192,4099,4093,-2},
        {"negative denominator two-and-half",8192,4101,4091,-2},
        {"positive denominator half-even zero",0,4097,4095,0},
        {"positive denominator half-even two",0,4099,4093,2},
        {"positive denominator two-and-half",0,4101,4091,2},
        {"positive half with negative denominator",8192,4093,4099,2},
        {"zero denominator",1000,1100,900,0},
        {"positive delta clamp",100,200,1,2048},
        {"negative delta clamp",100,1,200,-2048},
        {"S25 minimum exact",DOA_S25_MIN,DOA_S25_MIN,DOA_S25_MIN,0},
        {"S25 maximum exact",DOA_S25_MAX,DOA_S25_MAX,DOA_S25_MAX,0},
        {"S25 extreme neighbor difference",DOA_S25_MAX,DOA_S25_MIN,DOA_S25_MAX,2048}
    };
    doa_solve_output_t r;
    doa_servo_config_t servo = example_servo();
    unsigned int i;
    for (i = 0; i < (unsigned int)(sizeof(cases)/sizeof(cases[0])); ++i) {
        doa_frame_input_t f = make_frame(positive_lags, 800, 800, 0U);
        f.pair[0].lag = 0; f.pair[0].peak = cases[i].peak;
        f.pair[0].r_minus = cases[i].left; f.pair[0].r_plus = cases[i].right;
        expect_i(cases[i].name, doa_solve(&f, &servo, &r), DOA_OK);
        expect_i(cases[i].name, r.pair[0].delta_q12, cases[i].delta);
    }
    {
        doa_frame_input_t f = make_frame(positive_lags, 800, 800, 0U);
        f.pair[0].peak = 0; f.pair[0].r_minus = 1; f.pair[0].r_plus = -1;
        f.pair[0].second_peak = DOA_S25_MIN;
        expect_i("wide margin API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("wide margin not int32", r.pair[0].margin_q15, INT64_C(549755813888));
        f.pair[0].flags &= ~FEATURE_0_SECOND_VALID;
        expect_i("absent second API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("absent second ignored", r.pair[0].margin_q15, 0);
        f.pair[0].peak = DOA_S25_MIN;
        f.pair[0].r_minus = DOA_S25_MIN; f.pair[0].r_plus = DOA_S25_MIN;
        expect_i("minimum abs safe API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("minimum abs safe margin", r.pair[0].margin_q15, -32768);
    }
    {
        doa_frame_input_t f = make_frame(positive_lags, 800, 800, 0U);
        f.pair[0].lag = 6; f.pair[0].peak = 10000;
        f.pair[0].r_minus = 9600; f.pair[0].r_plus = 6304;
        expect_i("tau boundary API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("tau boundary exact", r.pair[0].tau_q12, 22928);
        expect_i("tau boundary accepted", r.pair[0].qualified, 1);
        f.pair[0].r_minus = 9198; f.pair[0].r_plus = 2610;
        expect_i("tau plus one API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("tau plus one exact", r.pair[0].tau_q12, 22929);
        expect_i("tau plus one rejected", r.pair[0].reason, DOA_PAIR_TAU);
        f.pair[0].lag = -6; f.pair[0].r_minus = 6304; f.pair[0].r_plus = 9600;
        expect_i("negative tau boundary API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("negative tau boundary exact", r.pair[0].tau_q12, -22928);
        expect_i("negative tau boundary accepted", r.pair[0].qualified, 1);
        f = make_frame(positive_lags, 800, 800, 0U);
        f.pair[1].lag = 8; f.pair[1].peak = 10000;
        f.pair[1].r_minus = 8295; f.pair[1].r_plus = 7609;
        expect_i("diagonal tau API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("diagonal tau exact", r.pair[1].tau_q12, 32425);
        expect_i("diagonal tau accepted", r.pair[1].qualified, 1);
        f.pair[1].r_minus = 8294; f.pair[1].r_plus = 7610;
        expect_i("diagonal tau plus one API", doa_solve(&f, &servo, &r), DOA_OK);
        expect_i("diagonal tau plus one exact", r.pair[1].tau_q12, 32426);
        expect_i("diagonal tau plus one rejected", r.pair[1].reason, DOA_PAIR_TAU);
    }
}

static void test_mapper(void)
{
    doa_servo_config_t c = example_servo();
    doa_servo_result_t r;
    expect_i("map positive endpoint", doa_map_angle_q8(23040, &c, &r), DOA_MAP_OK);
    expect_i("map positive endpoint degrees", r.angle_deg, 180);
    expect_i("map negative endpoint", doa_map_angle_q8(-23040, &c, &r), DOA_MAP_OK);
    expect_i("map negative endpoint degrees", r.angle_deg, 0);
    expect_i("map no clamping", doa_map_angle_q8(23041, &c, &r), DOA_MAP_DOMAIN);
    expect_i("map no clamping valid", r.valid, 0);
    expect_i("map +180 canonical reject", doa_map_angle_q8(46080, &c, &r), DOA_MAP_CANONICAL);
    c.direction = -1;
    expect_i("map reversed sign", doa_map_angle_q8(11520, &c, &r), DOA_MAP_OK);
    expect_i("map reversed degrees", r.angle_deg, 45);
    c.direction = 0;
    expect_i("map illegal direction", doa_map_angle_q8(0, &c, &r), DOA_MAP_CONFIG);
    c = example_servo(); c.offset_q8 = 0;
    expect_i("map half-even 0", doa_map_angle_q8(128, &c, &r), DOA_MAP_OK);
    expect_i("map half-even 0 value", r.angle_deg, 0);
    expect_i("map half-even 2", doa_map_angle_q8(384, &c, &r), DOA_MAP_OK);
    expect_i("map half-even 2 value", r.angle_deg, 2);
    expect_i("map half-even 2.5", doa_map_angle_q8(640, &c, &r), DOA_MAP_OK);
    expect_i("map half-even 2.5 value", r.angle_deg, 2);
    expect_i("map negative before rounding", doa_map_angle_q8(-1, &c, &r), DOA_MAP_MECHANICAL);
    c.mechanical_max = 1U;
    expect_i("map pre-round max", doa_map_angle_q8(257, &c, &r), DOA_MAP_MECHANICAL);
    c = example_servo(); c.servo_max = 0U;
    expect_i("map servo0 config", doa_map_angle_q8(0, &c, &r), DOA_MAP_CONFIG);
    c = example_servo(); c.servo_max = 512U;
    expect_i("map U9 range", doa_map_angle_q8(0, &c, &r), DOA_MAP_CONFIG);
    c = example_servo(); c.offset_q8 = 8388608;
    expect_i("map S24 offset range", doa_map_angle_q8(0, &c, &r), DOA_MAP_CONFIG);
    expect_i("map null result", doa_map_angle_q8(0, &c, NULL), DOA_MAP_ARGUMENT);
    expect_i("map null config", doa_map_angle_q8(0, NULL, &r), DOA_MAP_DISABLED);
    c = example_servo(); c.offset_q8 = 46080;
    c.domain_min_q8 = -46080; c.domain_max_q8 = 46079;
    c.mechanical_max = 360U; c.servo_max = 360U;
    expect_i("map -180 included", doa_map_angle_q8(-46080, &c, &r), DOA_MAP_OK);
    expect_i("map -180 zero", r.angle_deg, 0);
    expect_i("map near180 included", doa_map_angle_q8(46079, &c, &r), DOA_MAP_OK);
    expect_i("map near180 rne", r.angle_deg, 360);
}

static void test_angle_sweep(void)
{
    const double pi = 3.1415926535897932384626433832795;
    double max_error = 0.0;
    float max_float_error = 0.0f;
    unsigned int i;
    doa_angles_t a;
    /* First revolution hits exact Q8 angles; the offset revolution exercises
     * non-integral Q8 rounding. Both cover all four quadrants and the wrap. */
    for (i = 0; i < 1440U; ++i) {
        double degrees_in = (double)(i % 720U) * 0.5 - 180.0 + (i >= 720U ? 0.1234 : 0.0);
        double radians = degrees_in * pi / 180.0;
        int32_t x = (int32_t)lround(1000000.0 * cos(radians));
        int32_t y = (int32_t)lround(1000000.0 * sin(radians));
        double expected = atan2((double)y, (double)x) * 180.0 / pi;
        double difference;
        int32_t qdiff;
        expect_i("CORDIC sweep status", doa_angles_from_vector(x, y, &a), DOA_OK);
        difference = (double)a.angle_q8 / 256.0 - expected;
        if (difference >= 180.0) difference -= 360.0;
        if (difference < -180.0) difference += 360.0;
        if (fabs(difference) > max_error) max_error = fabs(difference);
        if (fabsf(a.cordic_minus_atan2_deg) > max_float_error)
            max_float_error = fabsf(a.cordic_minus_atan2_deg);
        qdiff = a.angle_q8 - a.atan2_q8;
        if (qdiff >= 46080) qdiff -= 92160;
        if (qdiff < -46080) qdiff += 92160;
        expect_true("CORDIC vs double atan2 <=0.004deg", fabs(difference) <= 0.004);
        expect_true("CORDIC vs atan2f <=1 Q8 code", qdiff >= -1 && qdiff <= 1);
    }
    expect_i("zero vector rejected", doa_angles_from_vector(0, 0, &a), DOA_NUMERIC_RANGE);
    expect_i("vector overflow rejected", doa_angles_from_vector(4194304, 0, &a), DOA_NUMERIC_RANGE);
    expect_i("vector negative endpoint", doa_angles_from_vector(-4194304, 0, &a), DOA_OK);
    expect_i("vector negative endpoint angle", a.angle_q8, -46080);
    expect_i("vector extreme diagonal", doa_angles_from_vector(-4194304, -4194304, &a), DOA_OK);
    expect_i("vector extreme diagonal angle", a.angle_q8, -34560);
    expect_i("angle null", doa_angles_from_vector(1, 0, NULL), DOA_BAD_ARGUMENT);
    printf("SWEEP,1440,max_cordic_vs_double_deg=%.9f,max_cordic_vs_atan2f_deg=%.9f\n",
           max_error, (double)max_float_error);
}


static uint32_t read_be32(const uint8_t bytes[4])
{
    return ((uint32_t)bytes[0] << 24U) | ((uint32_t)bytes[1] << 16U) |
           ((uint32_t)bytes[2] << 8U) | (uint32_t)bytes[3];
}
static void write_be32(uint32_t word, uint8_t bytes[4])
{
    bytes[0] = (uint8_t)(word >> 24U); bytes[1] = (uint8_t)(word >> 16U);
    bytes[2] = (uint8_t)(word >> 8U); bytes[3] = (uint8_t)word;
}
static void test_frozen_abi_handoff(void)
{
    const uint8_t magic_bytes[4] = {0x5AU, 0x5AU, 0x20U, 0x26U};
    const uint8_t consume_command[5] = {0xB8U, 0U, 0U, 0U, 4U};
    const int32_t reject_lags[DOA_PAIR_COUNT] = ABI_BIST_REJECT_LAGS_INITIALIZER;
    const int32_t reject_tau[DOA_PAIR_COUNT] = ABI_BIST_REJECT_TAU_INITIALIZER;
    const int32_t pass_tau[DOA_PAIR_COUNT] = ABI_BIST_PASS_TAU_INITIALIZER;
    doa_servo_config_t servo = example_servo();
    unsigned int v, i;
    expect_i("ABI magic byte order", read_be32(magic_bytes), FPGA_ABI_MAGIC_VALUE);
    expect_i("ABI read budget", 1 + 2 + 6 * 6 + 1, FPGA_ABI_READ_TRANSACTIONS);
    expect_i("ABI word count", FPGA_ABI_SPI_BYTES * 8U, FPGA_ABI_SPI_BITS);
    expect_i("ABI consume header", consume_command[0], REG_SNAP_CMD | FPGA_ABI_WRITE_BIT);
    expect_i("ABI consume data", read_be32(consume_command + 1), SNAP_CMD_CONSUME);
    expect_i("SYS_CTRL bit2 reserved", SYS_CTRL_WRITE_MASK & UINT32_C(4), 0);
    expect_i("SYS_CTRL bit4 reserved", SYS_CTRL_WRITE_MASK & UINT32_C(16), 0);
    expect_i("BIST selection separate", REG_BIST_SELECT, 0x2C);
    expect_i("word -1", fpga_abi_word_to_s32(UINT32_C(0xFFFFFFFF)), -1);
    expect_i("word INT32_MIN", fpga_abi_word_to_s32(UINT32_C(0x80000000)), -INT64_C(2147483648));
    expect_i("word S25_MIN", fpga_abi_word_to_s32(UINT32_C(0xFF000000)), DOA_S25_MIN);
    expect_i("word S25_MAX", fpga_abi_word_to_s32(UINT32_C(0x00FFFFFF)), DOA_S25_MAX);
    expect_i("literal negative lag", FEATURE_0_GET_LAG(UINT32_C(0x664F19FD)), -3);
    expect_i("literal pair", FEATURE_0_GET_PAIR(UINT32_C(0x664F19FD)), 1);
    expect_i("literal mask", FEATURE_0_GET_MASK_COUNT(UINT32_C(0x664F19FD)), 79);
    expect_i("literal flags", FEATURE_0_GET_FLAGS(UINT32_C(0x664F19FD)), ABI_BIST_PAIR_FLAGS);
    expect_i("literal frame flags", SNAP_STATUS_GET_FRAME_FLAGS(UINT32_C(0x00007F39)), ABI_BIST_FRAME_FLAGS);
    expect_i("status field mask", SNAP_STATUS_DEFINED_MASK,
        SNAP_STATUS_LOCKED | SNAP_STATUS_QUEUED | SNAP_STATUS_GAP | SNAP_STATUS_BIST |
        SNAP_STATUS_ALL_TERMINAL | SNAP_STATUS_ENERGY_VALID | SNAP_STATUS_MOTION_PERMIT |
        SNAP_STATUS_VALID_PAIRS_MASK | SNAP_STATUS_IRQ | SNAP_STATUS_DRAINING |
        SNAP_STATUS_PROFILE_SUPPORTED | SNAP_STATUS_REAL_ENERGY_CAP | SNAP_STATUS_ACTUATOR_BOUND |
        SNAP_STATUS_FRAME_CANCELLED | SNAP_STATUS_FIRST_ERROR_MASK);
    for (v = 0; v < 2U; ++v) {
        doa_frame_input_t src = make_frame(v == 0U ? reject_lags : positive_lags,
            ABI_BIST_LEFT, v == 0U ? ABI_BIST_REJECT_RIGHT : ABI_BIST_PASS_RIGHT, 1U);
        doa_frame_input_t decoded;
        doa_solve_output_t out;
        uint8_t bytes[4];
        memset(&decoded, 0, sizeof(decoded));
        decoded.frame_id = v + 1U;
        decoded.flags = SNAP_STATUS_GET_FRAME_FLAGS(UINT32_C(0x00007F39));
        for (i = 0; i < DOA_PAIR_COUNT; ++i) {
            uint32_t feature = src.pair[i].flags |
                ((uint32_t)src.pair[i].lag & FEATURE_0_LAG_MASK) |
                ((uint32_t)i << FEATURE_0_PAIR_SHIFT) |
                ((uint32_t)src.pair[i].mask_count << FEATURE_0_MASK_COUNT_SHIFT);
            uint32_t word;
            write_be32(feature, bytes); word = read_be32(bytes);
            expect_i("ABI pair echo", FEATURE_0_GET_PAIR(word), i);
            expect_i("ABI reserved bits", word & ~FEATURE_0_DEFINED_MASK, 0);
            decoded.pair[i].lag = FEATURE_0_GET_LAG(word);
            decoded.pair[i].mask_count = (uint8_t)FEATURE_0_GET_MASK_COUNT(word);
            decoded.pair[i].flags = FEATURE_0_GET_FLAGS(word);
            write_be32((uint32_t)src.pair[i].peak, bytes);
            decoded.pair[i].peak = fpga_abi_word_to_s32(read_be32(bytes));
            write_be32((uint32_t)src.pair[i].r_minus, bytes);
            decoded.pair[i].r_minus = fpga_abi_word_to_s32(read_be32(bytes));
            write_be32((uint32_t)src.pair[i].r_plus, bytes);
            decoded.pair[i].r_plus = fpga_abi_word_to_s32(read_be32(bytes));
            write_be32((uint32_t)src.pair[i].second_peak, bytes);
            decoded.pair[i].second_peak = fpga_abi_word_to_s32(read_be32(bytes));
        }
        expect_i("ABI decode -> solve", doa_solve(&decoded, &servo, &out), DOA_OK);
        expect_i("ABI output frame identity", out.frame_id, v + 1U);
        expect_i("ABI expected direction valid", out.direction_valid, v == 0U ? 0 : 1);
        expect_i("ABI expected direction reason", out.direction_reason, v == 0U ? 3 : 0);
        expect_i("ABI BIST never commands servo", out.servo_cmd_valid, 0);
        for (i = 0; i < DOA_PAIR_COUNT; ++i) {
            expect_i("ABI tau result", out.pair[i].tau_q12, v == 0U ? reject_tau[i] : pass_tau[i]);
            expect_i("ABI margin result", out.pair[i].margin_q15, ABI_BIST_MARGIN_Q15);
        }
    }
    puts("ABI_HANDOFF,PASS,2_BIST_vectors,big_endian,flags,sign_extension,S2_struct_to_S1");
}

int main(void)
{
    puts("PAIR_HEADER,case,pair,lag,delta_q12,tau_q12,margin_q15,qualified");
    puts("CASE_HEADER,case,direction_valid,reason,pair_count,ux_q20,uy_q20,residual_q24,norm_q40,angle_q8,atan2_deg,map_valid,servo_deg,servo_cmd_valid");
    test_frozen_abi_handoff();
    test_bist();
    test_directions();
    test_rejections();
    test_rounding_and_tau();
    test_mapper();
    test_angle_sweep();
    printf("RESULT,%s,checks=%u,failures=%u\n", failures == 0U ? "PASS" : "FAIL", checks, failures);
    return failures == 0U ? 0 : 1;
}
