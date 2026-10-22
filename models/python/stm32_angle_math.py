"""Pure numeric port of ``software/common/s1/doa_solver.c`` (S1).

The six inputs are already decoded and assigned to pairs 01, 02, 03, 12,
13, 23. The caller supplies ``source_qualified`` after checking the source
stages. This module does not decode FPGA registers, handle frames, or produce
servo commands. Its authoritative output is the original integer CORDIC Q8
angle; Python's atan2 is diagnostic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees
from typing import Sequence


PAIR_DX_DY = ((1, 0), (1, 1), (0, 1), (0, 1), (-1, 1), (-1, 0))
TAU_LIMIT_Q12 = (22928, 32425, 22928, 22928, 32425, 22928)
ATAN_Q16 = (
    2949120, 1740967, 919879, 466945, 234379,
    117304, 58666, 29335, 14668, 7334, 3667, 1833,
    917, 458, 229, 115, 57, 29, 14, 7, 4, 2, 1, 0,
)
S25_MIN, S25_MAX = -(1 << 24), (1 << 24) - 1
VECTOR_MIN, VECTOR_MAX = -(1 << 22), (1 << 22) - 1
NORM_MIN_Q40, NORM_MAX_Q40 = 10995200164, 1858175196201


@dataclass(frozen=True)
class PairFeature:
    """Decoded numeric feature; ``source_qualified`` comes from the caller.

    The flag is true only when the upstream raw peak and processing stages
    satisfy the relevant real-frame or diagnostic-frame source contract.
    ``second_valid`` controls margin calculation, not pair qualification.
    """

    lag: int
    peak: int
    r_minus: int
    r_plus: int
    second_peak: int
    mask_count: int
    source_qualified: bool
    second_valid: bool = True


@dataclass(frozen=True)
class PairMath:
    delta_q12: int = 0
    tau_q12: int = 0
    margin_q15: int = 0
    qualified: bool = False
    reason: str = "not_evaluated"


@dataclass(frozen=True)
class DirectionMath:
    valid: bool
    reason: str
    pairs: tuple[PairMath, ...]
    valid_pair_count: int
    valid_pair_mask: int
    determinant: int
    ux_q20: int
    uy_q20: int
    residual_square_q24: int
    residual_limit_q24: int
    norm_square_q40: int
    angle_q8: int | None
    atan2_deg: float | None

    @property
    def angle_deg(self) -> float | None:
        return None if self.angle_q8 is None else self.angle_q8 / 256.0


def _rne_div(numerator: int, denominator: int) -> int:
    """Signed round-to-nearest-even; the C reference returns zero for d=0."""
    if denominator <= 0:
        return 0
    quotient, remainder = divmod(abs(numerator), denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient & 1):
        quotient += 1
    return -quotient if numerator < 0 else quotient


def _canonical_q8(angle_q8: int) -> int:
    if angle_q8 >= 46080:
        angle_q8 -= 92160
    if angle_q8 < -46080:
        angle_q8 += 92160
    return angle_q8


def cordic_angle_q8(ux_q20: int, uy_q20: int) -> int:
    """Return the C solver's authoritative 24-step signed angle in Q8 degrees."""
    if not VECTOR_MIN <= ux_q20 <= VECTOR_MAX or not VECTOR_MIN <= uy_q20 <= VECTOR_MAX:
        raise ValueError("vector component outside signed 23-bit range")
    if ux_q20 == 0 and uy_q20 == 0:
        raise ValueError("zero direction vector")

    maximum = max(abs(ux_q20), abs(uy_q20))
    scale = 1 << (24 - maximum.bit_length())
    cx = abs(ux_q20) * scale
    cy = (-uy_q20 if ux_q20 < 0 else uy_q20) * scale
    offset = (11796480 if uy_q20 >= 0 else -11796480) if ux_q20 < 0 else 0
    angle_q16 = 0
    for step, atan_step_q16 in enumerate(ATAN_Q16):
        old_cx, old_cy = cx, cy
        # Python's signed >> is floor division, matching the reference SV >>>.
        if old_cy > 0:
            cx = old_cx + (old_cy >> step)
            cy = old_cy - (old_cx >> step)
            angle_q16 += atan_step_q16
        elif old_cy < 0:
            cx = old_cx - (old_cy >> step)
            cy = old_cy + (old_cx >> step)
            angle_q16 -= atan_step_q16
    return _canonical_q8(_rne_div(angle_q16 + offset, 256))


def _validate_feature(feature: PairFeature) -> None:
    if not isinstance(feature, PairFeature):
        raise TypeError("each pair must be a PairFeature")
    for name in ("lag", "peak", "r_minus", "r_plus", "second_peak", "mask_count"):
        if type(getattr(feature, name)) is not int:
            raise TypeError(f"{name} must be an integer")
    if type(feature.source_qualified) is not bool or type(feature.second_valid) is not bool:
        raise TypeError("source_qualified and second_valid must be booleans")
    if not -32 <= feature.lag <= 31 or not 0 <= feature.mask_count <= 79:
        raise ValueError("lag or mask_count outside C input range")
    if any(not S25_MIN <= value <= S25_MAX for value in
           (feature.peak, feature.r_minus, feature.r_plus, feature.second_peak)):
        raise ValueError("peak or neighbor outside signed 25-bit range")


def evaluate_pair(feature: PairFeature, index: int) -> PairMath:
    """Apply the C parabolic interpolation, margin, and pair tau gate."""
    _validate_feature(feature)
    if type(index) is not int or not 0 <= index < 6:
        raise ValueError("pair index must be 0..5 in 01,02,03,12,13,23 order")
    if feature.mask_count < 12:
        return PairMath(reason="mask")
    if not feature.source_qualified:
        return PairMath(reason="source")

    denominator = feature.r_minus - 2 * feature.peak + feature.r_plus
    numerator = (feature.r_minus - feature.r_plus) * 2048
    if denominator < 0:
        denominator, numerator = -denominator, -numerator
    delta_q12 = max(-2048, min(2048, _rne_div(numerator, denominator)))
    tau_q12 = feature.lag * 4096 + delta_q12
    second = feature.second_peak if feature.second_valid else 0
    margin_q15 = _rne_div((feature.peak - second) * 32768,
                          max(abs(feature.peak), 1))
    if abs(tau_q12) > TAU_LIMIT_Q12[index]:
        return PairMath(delta_q12, tau_q12, margin_q15, False, "tau")
    return PairMath(delta_q12, tau_q12, margin_q15, True, "ok")


def solve_from_pairs(features: Sequence[PairFeature]) -> DirectionMath:
    """Estimate horizontal angle from six decoded features, without hardware I/O.

    Invalid source/protocol frames must be rejected by the caller before this
    pure math entry. ``valid=False`` means there is no usable angle; never send
    a motion command solely on the strength of this result.
    """
    if len(features) != 6:
        raise ValueError("exactly six features are required")
    # Like the C solver, validate all numeric fields before any pair arithmetic.
    for feature in features:
        _validate_feature(feature)
    pairs = tuple(evaluate_pair(feature, index) for index, feature in enumerate(features))
    valid_indices = [index for index, pair in enumerate(pairs) if pair.qualified]
    count = len(valid_indices)
    mask = sum(1 << index for index in valid_indices)
    sxx = syy = sxy = bx = by = 0
    for index in valid_indices:
        dx, dy = PAIR_DX_DY[index]
        tau_q12 = pairs[index].tau_q12
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
        bx += dx * tau_q12
        by += dy * tau_q12
    determinant = sxx * syy - sxy * sxy
    residual_limit = count * 4194304

    def result(reason: str, ux: int = 0, uy: int = 0, residual: int = 0,
               norm: int = 0, angle: int | None = None,
               reference: float | None = None) -> DirectionMath:
        return DirectionMath(angle is not None, reason, pairs, count, mask,
                             determinant, ux, uy, residual, residual_limit,
                             norm, angle, reference)

    if count < 3:
        return result("insufficient_pairs")
    if determinant <= 0:
        return result("singular")
    ux = _rne_div((syy * bx - sxy * by) * 87808, determinant * 1920)
    uy = _rne_div((sxx * by - sxy * bx) * 87808, determinant * 1920)
    if not VECTOR_MIN <= ux <= VECTOR_MAX or not VECTOR_MIN <= uy <= VECTOR_MAX:
        return result("numeric_range")

    residual = 0
    for index in valid_indices:
        dx, dy = PAIR_DX_DY[index]
        predicted = _rne_div((dx * ux + dy * uy) * 7864320, 343 * 1048576)
        residual += (predicted - pairs[index].tau_q12) ** 2
    norm = ux * ux + uy * uy
    if residual > residual_limit:
        return result("residual_reject", ux, uy, residual, norm)
    if not NORM_MIN_Q40 <= norm <= NORM_MAX_Q40:
        return result("norm_reject", ux, uy, residual, norm)
    angle_q8 = cordic_angle_q8(ux, uy)
    reference = degrees(atan2(uy, ux))
    if reference >= 180.0:
        reference -= 360.0
    return result("ok", ux, uy, residual, norm, angle_q8, reference)
