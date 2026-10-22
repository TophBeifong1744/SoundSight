"""Regression vectors recorded by software/common/s1/test_doa_solver.c."""

import math
import unittest
from dataclasses import replace

from stm32_angle_math import PairFeature, cordic_angle_q8, evaluate_pair, solve_from_pairs


def six_pairs(lags, *, left=800, right=800, mask_count=79, qualified=True):
    return [PairFeature(lag, 1000, left, right, 100, mask_count, qualified)
            for lag in lags]


class Stm32AngleMathTest(unittest.TestCase):
    def test_recorded_c_direction_vectors(self):
        # Values are independent expected outputs from the original C tests.
        cases = (
            ((3, 6, 3, 3, 0, -3), 561971, 561971, 11520),
            ((3, 0, -3, -3, -6, -3), 561971, -561971, -11520),
            ((0, 4, 4, 4, 4, 0), 0, 749295, 23040),
            ((0, -4, -4, -4, -4, 0), 0, -749295, -23040),
            ((-3, 0, 3, 3, 6, 3), -561971, 561971, 34560),
            ((-3, -6, -3, -3, 0, 3), -561971, -561971, -34560),
            ((-4, -4, 0, 0, 4, 4), -749295, 0, -46080),
            ((4, 5, 1, 1, -3, -4), 749295, 187324, 3593),
            ((2, 5, 3, 3, 1, -2), 374647, 561971, 14415),
        )
        for lags, ux, uy, angle in cases:
            with self.subTest(lags=lags):
                actual = solve_from_pairs(six_pairs(lags))
                self.assertTrue(actual.valid)
                self.assertEqual(actual.reason, "ok")
                self.assertEqual((actual.ux_q20, actual.uy_q20), (ux, uy))
                self.assertEqual(actual.angle_q8, angle)
                self.assertEqual(actual.residual_square_q24, 0)
                self.assertEqual(actual.angle_deg, angle / 256)

    def test_recorded_c_bist_arithmetic_without_hardware_flags(self):
        positive = solve_from_pairs(six_pairs((4, 4, 0, 0, -4, -4)))
        self.assertEqual((positive.ux_q20, positive.uy_q20, positive.angle_q8),
                         (749295, 0, 0))
        self.assertEqual(positive.norm_square_q40, 561442997025)
        self.assertEqual(positive.residual_square_q24, 0)

        rejected = solve_from_pairs(six_pairs((5, -3, 0, 1, -1, 2),
                                               left=800, right=600))
        self.assertFalse(rejected.valid)
        self.assertEqual(rejected.reason, "residual_reject")
        self.assertIsNone(rejected.angle_q8)
        self.assertEqual((rejected.ux_q20, rejected.uy_q20), (46831, -171729))
        self.assertEqual(rejected.residual_square_q24, 590912626)
        self.assertEqual(rejected.residual_limit_q24, 25165824)
        self.assertEqual(rejected.pairs[0].delta_q12, -683)

    def test_rne_zero_denominator_and_tau_endpoints(self):
        delta_cases = (
            (8192, 4097, 4095, 0), (8192, 4099, 4093, -2),
            (0, 4099, 4093, 2), (1000, 1100, 900, 0),
            (100, 200, 1, 2048), (100, 1, 200, -2048),
        )
        for peak, left, right, expected in delta_cases:
            with self.subTest(peak=peak, left=left, right=right):
                pair = PairFeature(0, peak, left, right, 100, 79, True)
                self.assertEqual(evaluate_pair(pair, 0).delta_q12, expected)
        endpoints = (
            (0, 6, 9600, 6304, 22928, True),
            (0, 6, 9198, 2610, 22929, False),
            (0, -6, 6304, 9600, -22928, True),
            (1, 8, 8295, 7609, 32425, True),
            (1, 8, 8294, 7610, 32426, False),
        )
        for index, lag, left, right, tau, accepted in endpoints:
            with self.subTest(index=index, lag=lag, left=left, right=right):
                pair = PairFeature(lag, 10000, left, right, 100, 79, True)
                actual = evaluate_pair(pair, index)
                self.assertEqual(actual.tau_q12, tau)
                self.assertEqual(actual.qualified, accepted)

    def test_source_qualification_and_numeric_rejections(self):
        lags = (4, 4, 0, 0, -4, -4)
        masked = solve_from_pairs(six_pairs(lags, mask_count=11))
        self.assertEqual(masked.reason, "insufficient_pairs")
        self.assertEqual(masked.valid_pair_count, 0)
        self.assertEqual(masked.pairs[0].reason, "mask")
        blocked = solve_from_pairs(six_pairs(lags, qualified=False))
        self.assertEqual(blocked.pairs[0].reason, "source")
        self.assertIsNone(blocked.angle_q8)
        zero = solve_from_pairs(six_pairs((0,) * 6))
        self.assertEqual(zero.reason, "norm_reject")
        with self.assertRaises(ValueError):
            solve_from_pairs(six_pairs(lags)[:5])
        with self.assertRaises(ValueError):
            evaluate_pair(PairFeature(32, 1000, 800, 800, 100, 79, True), 0)

    def test_recorded_c_high_norm_and_wide_margin(self):
        features = six_pairs((5, 11, 5, 5, 0, -5))
        for index in (0, 2, 3):
            features[index] = replace(features[index], r_plus=1000)
        features[5] = replace(features[5], r_minus=1000)
        high = solve_from_pairs(features)
        self.assertFalse(high.valid)
        self.assertEqual(high.reason, "norm_reject")
        self.assertEqual(high.norm_square_q40, 2122957877922)
        self.assertIsNone(high.angle_q8)

        wide = PairFeature(0, 0, 1, -1, -(1 << 24), 79, True)
        self.assertEqual(evaluate_pair(wide, 0).margin_q15, 549755813888)
        self.assertEqual(evaluate_pair(replace(wide, second_valid=False), 0).margin_q15, 0)
        minimum = replace(wide, peak=-(1 << 24), r_minus=-(1 << 24),
                          r_plus=-(1 << 24), second_valid=False)
        self.assertEqual(evaluate_pair(minimum, 0).margin_q15, -32768)

    def test_cordic_axes_endpoints_and_quadrants(self):
        self.assertEqual(cordic_angle_q8(-4194304, 0), -46080)
        self.assertEqual(cordic_angle_q8(-4194304, -4194304), -34560)
        with self.assertRaises(ValueError):
            cordic_angle_q8(0, 0)
        with self.assertRaises(ValueError):
            cordic_angle_q8(4194304, 0)
        # Same deterministic 1440-point sweep as the C test; this is a sample
        # check against independent atan2, not a global accuracy guarantee.
        largest_error = 0.0
        for index in range(1440):
            degrees_in = (index % 720) * 0.5 - 180 + (0.1234 if index >= 720 else 0)
            radians = math.radians(degrees_in)
            x_float = 1000000 * math.cos(radians)
            y_float = 1000000 * math.sin(radians)
            x = int(math.copysign(math.floor(abs(x_float) + 0.5), x_float))
            y = int(math.copysign(math.floor(abs(y_float) + 0.5), y_float))
            estimated = cordic_angle_q8(x, y) / 256
            reference = math.degrees(math.atan2(y, x))
            difference = (estimated - reference + 180) % 360 - 180
            largest_error = max(largest_error, abs(difference))
        self.assertLessEqual(largest_error, 0.004)


if __name__ == "__main__":
    unittest.main()
