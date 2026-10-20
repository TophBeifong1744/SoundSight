/* Test-only direct S1 adapter. No wire decoding, MMIO, or board dependency. */
#include <stdint.h>
#include <string.h>
#include "doa_solver.h"

int migration_reference(uint32_t sequence, uint32_t frame_flags,
                        const int32_t pairs[42], const int32_t config[7],
                        int32_t out[12])
{
    doa_frame_input_t frame;
    doa_servo_config_t servo;
    doa_solve_output_t result;
    doa_status_t rc;
    unsigned int p;
    memset(&frame, 0, sizeof frame);
    memset(&servo, 0, sizeof servo);
    frame.frame_id = sequence;
    frame.flags = frame_flags;
    for (p = 0; p < 6U; ++p) {
        const int32_t *v = pairs + p * 7U;
        frame.pair[p].lag = v[0];
        frame.pair[p].peak = v[1];
        frame.pair[p].r_minus = v[2];
        frame.pair[p].r_plus = v[3];
        frame.pair[p].second_peak = v[4];
        frame.pair[p].mask_count = (uint8_t)v[5];
        frame.pair[p].flags = (uint32_t)v[6];
    }
    if (config != NULL) {
        servo.config_valid = 1U;
        servo.offset_q8 = config[0];
        servo.direction = config[1];
        servo.domain_min_q8 = config[2];
        servo.domain_max_q8 = config[3];
        servo.mechanical_min = (uint16_t)config[4];
        servo.mechanical_max = (uint16_t)config[5];
        servo.servo_max = (uint16_t)config[6];
    }
    rc = doa_solve(&frame, config != NULL ? &servo : NULL, &result);
    out[0] = (int32_t)rc;
    out[1] = result.direction_valid;
    out[2] = (int32_t)result.direction_reason;
    out[3] = result.angle_q8;
    out[4] = result.ux_q20;
    out[5] = result.uy_q20;
    out[6] = result.valid_pair_count;
    out[7] = result.horizontal_servo_deg;
    out[8] = result.servo_cmd_valid;
    out[9] = (int32_t)result.servo_map_status;
    out[10] = result.first_error_code;
    out[11] = result.bad_pair_index;
    return (int)rc;
}
