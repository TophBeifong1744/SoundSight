"""B r2 software fixed4 boundary: atomic complex zero on component overflow.

The historic leaf's RNE rule is reused. Its saturating payload is deliberately
not used by this new composition. This function models numeric semantics, not
ready/valid beats, backpressure, or hardware cancellation.
"""
import numpy as np


def adapt_half_s29(values, *, frame_identity, domain, bindings):
    """Map [4,513,2] signed29 codes to signed25 and component validity.

    Result arrays are indexed [channel, bin, component] (component 0=real,
    1=imag). Each invalid complex has the payload (0,0), while neighboring
    legal complexes retain their exact rounded values.
    """
    if domain not in ("gate", "doa"):
        raise ValueError("FIXED4_DOMAIN_REQUIRED")
    identity_fields = ("boot", "session", "interval", "frame", "generation", "last_id")
    if type(frame_identity) is not dict or any(k not in frame_identity for k in identity_fields):
        raise ValueError("FIXED4_FRAME_IDENTITY_INCOMPLETE")
    x = np.asarray(values)
    if (x.shape != (4, 513, 2) or not np.issubdtype(x.dtype, np.integer)
            or np.any(x < -(1 << 28)) or np.any(x >= (1 << 28))):
        raise ValueError("FIXED4_REQUIRES_FOUR_S29_HALF_SPECTRA")
    payload = np.empty((4, 513, 2), dtype=np.int64)
    overflow = np.zeros((4, 513, 2), dtype=np.bool_)
    numeric_valid = np.ones((4, 513), dtype=np.bool_)
    low, high = -(1 << 24), (1 << 24) - 1
    round_shift = bindings.fg.rne_shift
    for channel in range(4):
        for bin_index in range(513):
            re = round_shift(int(x[channel, bin_index, 0]), 4)
            im = round_shift(int(x[channel, bin_index, 1]), 4)
            bad_re = not low <= re <= high
            bad_im = not low <= im <= high
            overflow[channel, bin_index] = (bad_re, bad_im)
            numeric_valid[channel, bin_index] = not (bad_re or bad_im)
            payload[channel, bin_index] = (0, 0) if bad_re or bad_im else (re, im)
    counts = np.count_nonzero(overflow, axis=1).astype(np.int64)
    bad_complex = np.count_nonzero(~numeric_valid, axis=1).astype(np.int64)
    locations = [{"channel": int(channel), "bin": int(bin_index),
                  "real_overflow": bool(overflow[channel, bin_index, 0]),
                  "imag_overflow": bool(overflow[channel, bin_index, 1])}
                 for channel, bin_index in np.argwhere(~numeric_valid)]
    return {
        "payload_s25": payload,
        "numeric_valid": numeric_valid,
        "overflow_components": overflow,
        "summary": {
            "frame_identity": dict(frame_identity), "domain": domain,
            "array_axes": {"payload_s25": ["channel", "bin", "real_imag"],
                           "numeric_valid": ["channel", "bin"],
                           "overflow_components": ["channel", "bin", "real_imag"]},
            "overflow_components_by_channel": counts.tolist(),
            "invalid_complex_by_channel": bad_complex.tolist(),
            "overflow_components_total": int(counts.sum()),
            "invalid_complex_total": int(bad_complex.sum()),
            "invalid_locations": locations,
        },
    }
