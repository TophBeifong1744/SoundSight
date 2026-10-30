#ifndef SOUNDSIGHT_DOA_SOLVER_H
#define SOUNDSIGHT_DOA_SOLVER_H
/* STATUS: FROZEN -- S1/S2 API 1.0, 2026-10-17.
 * API fields are assigned individually, never serialized as raw struct bytes.
 * All hardware transport constants come from the single frozen ABI header.
 */
#include <stdint.h>
#include "fpga_stm32_abi_frozen.h"
#define DOA_SOLVER_API_VERSION UINT32_C(0x00010000)
#define DOA_PAIR_COUNT FPGA_ABI_PAIR_COUNT
#define DOA_NO_BAD_PAIR UINT8_C(255)
#define DOA_S25_MIN FPGA_ABI_S25_MIN
#define DOA_S25_MAX FPGA_ABI_S25_MAX
#define DOA_FRAME_FLAGS_MASK SNAP_STATUS_FRAME_FLAGS_MASK
#define DOA_PAIR_FLAGS_MASK FEATURE_0_FLAGS_MASK

typedef enum {
    DOA_STAGE_PENDING = FPGA_STAGE_PENDING, DOA_STAGE_OK = FPGA_STAGE_OK,
    DOA_STAGE_REJECTED = FPGA_STAGE_REJECTED, DOA_STAGE_NUMERIC = FPGA_STAGE_NUMERIC,
    DOA_STAGE_PROTOCOL = FPGA_STAGE_PROTOCOL, DOA_STAGE_CANCELLED = FPGA_STAGE_CANCELLED,
    DOA_STAGE_SKIPPED = FPGA_STAGE_SKIPPED
} doa_stage_t;
typedef enum {
    DOA_OK = 0, DOA_BAD_ARGUMENT = 1, DOA_INPUT_RANGE = 2,
    DOA_INPUT_FLAGS = 3, DOA_INCOMPLETE_FRAME = 4, DOA_NUMERIC_RANGE = 5
} doa_status_t;
typedef enum {
    DOA_DIRECTION_OK = 0, DOA_INSUFFICIENT_PAIRS = 1, DOA_SINGULAR = 2,
    DOA_RESIDUAL_REJECT = 3, DOA_NORM_REJECT = 4,
    DOA_CANCELLED = 6, DOA_SOURCE_ERROR = 7
} doa_direction_reason_t;
typedef enum {
    DOA_PAIR_OK = 0, DOA_PAIR_MASK = 1, DOA_PAIR_STAGE = 2,
    DOA_PAIR_TAU = 3, DOA_PAIR_NOT_EVALUATED = 4
} doa_pair_reason_t;

/* pair[i] order is 01,02,03,12,13,23. S2 verifies the wire pair echo.
 * flags = FEATURE_0_GET_FLAGS(word); lag = FEATURE_0_GET_LAG(word).
 * peak/neighbor words use fpga_abi_word_to_s32; S1 checks S25/S6 bounds.
 */
typedef struct {
    int32_t lag, peak, r_minus, r_plus, second_peak;
    uint8_t mask_count;
    uint32_t flags;
} doa_pair_input_t;
typedef struct {
    uint32_t frame_id;
    uint32_t flags; /* SNAP_STATUS_GET_FRAME_FLAGS(locked_status). */
    doa_pair_input_t pair[DOA_PAIR_COUNT];
} doa_frame_input_t;

typedef struct {
    int32_t delta_q12, tau_q12;
    int64_t margin_q15;
    uint8_t qualified;
    doa_pair_reason_t reason;
} doa_pair_result_t;
typedef struct {
    uint8_t config_valid;
    int32_t offset_q8, direction, domain_min_q8, domain_max_q8;
    uint16_t mechanical_min, mechanical_max, servo_max;
} doa_servo_config_t;
typedef enum {
    DOA_MAP_OK = 0, DOA_MAP_DISABLED = 1, DOA_MAP_CONFIG = 2,
    DOA_MAP_CANONICAL = 3, DOA_MAP_DOMAIN = 4,
    DOA_MAP_MECHANICAL = 5, DOA_MAP_ARGUMENT = 6
} doa_map_status_t;
typedef struct {
    uint8_t config_legal, valid;
    uint16_t angle_deg;
    doa_map_status_t status;
} doa_servo_result_t;
typedef struct {
    int32_t angle_q8, atan2_q8;
    float atan2_deg, cordic_minus_atan2_deg;
} doa_angles_t;

typedef struct {
    uint32_t frame_id;
    uint8_t direction_valid, valid_pair_count, valid_pair_mask;
    uint8_t bad_pair_index, first_error_code;
    doa_direction_reason_t direction_reason;
    doa_pair_result_t pair[DOA_PAIR_COUNT];
    int32_t ux_q20, uy_q20, determinant;
    uint64_t residual_square_q24, residual_limit_q24, norm_square_q40;
    int32_t angle_q8;               /* Authoritative original integer CORDIC. */
    int32_t atan2_angle_q8;
    float atan2_deg, angle_difference_deg;
    uint16_t horizontal_servo_deg;
    uint8_t horizontal_map_valid, servo_config_legal;
    doa_map_status_t servo_map_status;
    uint8_t servo_cmd_valid;        /* direction && map && !BIST. S2 must also
                                    * check motion permit/watchdog/freshness. */
    uint8_t vertical_valid;         /* Always 0; no elevation solution. */
} doa_solve_output_t;

/* Return is API status; algorithm rejection returns DOA_OK with valid=0/reason.
 * flags contain only the defined flags masks; terminal stages cannot be PENDING.
 * Cancellation precedes source errors; all outputs clear on each call.
 * servo=NULL disables only mapping. The functions perform no hardware I/O.
 */
doa_status_t doa_solve(const doa_frame_input_t *frame,
                       const doa_servo_config_t *servo,
                       doa_solve_output_t *result);
doa_map_status_t doa_map_angle_q8(int32_t angle_q8,
                                const doa_servo_config_t *config,
                                doa_servo_result_t *result);
doa_status_t doa_angles_from_vector(int32_t ux_q20, int32_t uy_q20,
                                   doa_angles_t *result);
#endif
