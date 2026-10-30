"""Table-fed FG radix2 FFT; same arithmetic, frozen twiddle source.

Extracted from fixed_golden.fixed_fft. The only intentional difference is
consuming the bound Q30 bytes instead of calling math.cos/sin per transform.
"""
import hashlib
import numpy as np


def fixed_fft_table(samples, *, inverse, width, bindings):
    if (inverse, width) not in ((False, 29), (True, 25)):
        raise ValueError("UNSUPPORTED_FFT_PROFILE")
    leaf = bindings.fg
    values = [(int(a), int(b)) for a, b in samples]
    if len(values) != 1024:
        raise ValueError("1024_COMPLEX_SAMPLES_REQUIRED")
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    if any(not (lo <= a <= hi and lo <= b <= hi) for a, b in values):
        raise ValueError("FFT_INPUT_OUTSIDE_WIDTH")
    values = leaf._bit_reverse(values)
    table = bindings.fft_twiddle[1 if inverse else 0]
    offset = 0
    overflow = 0
    stage_hashes = []
    size = 2
    while size <= 1024:
        half = size // 2
        twiddles = table[offset:offset + half]
        if len(twiddles) != half:
            raise RuntimeError("FROZEN_TWIDDLE_SHAPE")
        for base in range(0, 1024, size):
            for j, (wr, wi) in enumerate(twiddles):
                wr, wi = int(wr), int(wi)
                ar, ai = values[base + j]
                br, bi = values[base + j + half]
                tr = leaf.rne_shift(wr * br - wi * bi, 30)
                ti = leaf.rne_shift(wr * bi + wi * br, 30)
                for index, (re, im) in ((base + j, (ar + tr, ai + ti)),
                                        (base + j + half, (ar - tr, ai - ti))):
                    rr, ov0 = leaf.saturate(leaf.rne_shift(re, 1), width)
                    ii, ov1 = leaf.saturate(leaf.rne_shift(im, 1), width)
                    values[index] = (rr, ii)
                    overflow += int(ov0) + int(ov1)
        stage_hashes.append(hashlib.sha256(np.asarray(values, dtype="<i8").tobytes()).hexdigest())
        offset += half
        size *= 2
    if offset != 1023:
        raise RuntimeError("FROZEN_TWIDDLE_COUNT")
    return np.asarray(values, dtype=np.int64), {"overflow_count": overflow, "stage_sha256": stage_hashes}
