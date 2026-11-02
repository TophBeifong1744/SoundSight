"""One authoritative portable research chain for the B r2 dual-domain profile."""
import copy
import numpy as np

from .contracts import PAIRS
from .fft_table import fixed_fft_table
from .fixed4 import adapt_half_s29


def expected_units():
    names = ["transport", "frame_domain", "binding"]
    for ch in range(4):
        names.extend((f"mean_{ch}", f"gate_window_{ch}", f"doa_window_{ch}"))
    for domain in ("gate", "doa"):
        for ch in range(4):
            names.extend((f"{domain}_fft_{ch}", f"{domain}_fixed4_{ch}"))
    names.append("gate_state")
    for pair in PAIRS:
        names.extend((f"phat_{pair}", f"ifft_{pair}", f"lag_{pair}"))
    names.extend(("doa", "tracker", "result_binding"))
    return tuple(names)


class ActivityState:
    """Explicitly configured copy of the old limited 4/2, 3/3, 3-channel state rule."""
    def __init__(self, config):
        self.config = copy.deepcopy(config)
        floor = int(config["band_rms_floor_codes"]) ** 2
        self.noise = [max(int(v), floor) for v in config["noise_power_u64"]]
        if any(v >= (1 << 64) for v in self.noise):
            raise ValueError("ACTIVITY_FLOOR_U64_OVERFLOW")
        self.reset()

    def reset(self):
        self.active = False
        self.attack = 0
        self.release = 0

    def update(self, powers):
        p = [int(v) for v in powers]
        if len(p) != 4 or any(v < 0 or v >= (1 << 64) for v in p):
            raise ValueError("ACTIVITY_POWER_U64")
        on = sum(v >= 4 * n for v, n in zip(p, self.noise)) >= 3
        off = sum(v >= 2 * n for v, n in zip(p, self.noise)) < 3
        self.attack = min(3, self.attack + 1) if on else 0
        self.release = min(3, self.release + 1) if off else 0
        if not self.active and self.attack >= 3:
            self.active, self.release = True, 0
        elif self.active and self.release >= 3:
            self.active, self.attack = False, 0
        return {"active": self.active, "attack": self.attack, "release": self.release,
                "on_channels": int(sum(v >= 4 * n for v, n in zip(p, self.noise))),
                "below_off_channels": int(sum(v < 2 * n for v, n in zip(p, self.noise)))}


def solve_doa_vector_q20(pair_lags, leaf):
    """FG doa_q20 lines 204-230, excluding its embedded old atan2 call."""
    deltas = leaf.PAIR_DELTAS
    if len(pair_lags) != len(deltas):
        raise ValueError("ONE_LAG_PER_PAIR_REQUIRED")
    valid = [(deltas[k], int(row["tau_q12"])) for k, row in enumerate(pair_lags) if row.get("valid")]
    if len(valid) < 3:
        return {"valid": False, "reason": "INSUFFICIENT_PAIRS", "valid_pairs": len(valid)}
    sxx = sum(dx * dx for (dx, _), _tau in valid)
    syy = sum(dy * dy for (_, dy), _tau in valid)
    sxy = sum(dx * dy for (dx, dy), _tau in valid)
    bx = sum(dx * tau for (dx, _), tau in valid)
    by = sum(dy * tau for (_, dy), tau in valid)
    determinant = sxx * syy - sxy * sxy
    if determinant == 0:
        return {"valid": False, "reason": "RANK_DEFICIENT", "valid_pairs": len(valid)}
    ux = leaf.rne_div((syy * bx - sxy * by) * 343 * (1 << 8), determinant * 1920)
    uy = leaf.rne_div((sxx * by - sxy * bx) * 343 * (1 << 8), determinant * 1920)
    residual_sq = 0
    for (dx, dy), tau in valid:
        predicted = leaf.rne_div((dx * ux + dy * uy) * 1920 * (1 << 12), 343 * (1 << 20))
        residual_sq += (predicted - tau) ** 2
    norm_sq = ux * ux + uy * uy
    residual_ok = residual_sq <= len(valid) * (1 << 11) ** 2
    norm_ok = round(0.1 * (1 << 20)) ** 2 <= norm_sq <= round(1.3 * (1 << 20)) ** 2
    return {"valid": bool(residual_ok and norm_ok),
            "reason": "VALID" if residual_ok and norm_ok else "GEOMETRY_REJECT",
            "valid_pairs": len(valid), "ux_q20": ux, "uy_q20": uy,
            "residual_sum_square_q24": residual_sq, "norm_square_q40": norm_sq}


def _set(status, name, value):
    if name not in status:
        raise RuntimeError("UNEXPECTED_UNIT: " + name)
    if status[name] != "PENDING":
        raise RuntimeError("DUPLICATE_UNIT_STATUS: " + name)
    status[name] = value


def run_numeric_frame(pcm, frame_identity, activity, bindings):
    """Compute local integer stages; no fresh, commit, take, or audio control."""
    x = np.asarray(pcm)
    if x.shape != (1024, 4) or not np.issubdtype(x.dtype, np.integer) or np.any(x < -(1 << 23)) or np.any(x >= (1 << 23)):
        raise ValueError("PCM_REQUIRES_1024x4_SIGNED24")
    if type(frame_identity) is not dict or any(k not in frame_identity for k in ("boot", "session", "interval", "frame", "generation", "last_id")):
        raise ValueError("FRAME_IDENTITY_INCOMPLETE")
    x = x.astype(np.int64)
    leaf = bindings.fg
    status = {name: "PENDING" for name in expected_units()}
    for key in ("transport", "frame_domain", "binding"):
        _set(status, key, "WAIT_EXTERNAL_STATUS")
    arrays = {"pcm": x, "hann_u18f17": bindings.hann.copy()}
    detail = {"frame_identity": dict(frame_identity), "numeric_invalid": False,
              "invalid_reasons": [], "pair_rows": [], "fft_flags": {"gate": [], "doa": []},
              "fixed4": {}, "ifft_flags": [], "cordic": "NOT_RUN",
              "claim": "NUMERIC_ONLY_TIME_UNBOUND"}
    means = np.array([leaf.rne_div(sum(map(int, x[:, ch])), 1024) for ch in range(4)], dtype=np.int64)
    centered = x - means
    if np.any(centered < -(1 << 24)) or np.any(centered >= (1 << 24)):
        raise RuntimeError("GATE_CENTER_S25_OVERFLOW")
    gate_window = np.array([[leaf.rne_shift(int(v) * int(w), 17)
                             for v, w in zip(centered[:, ch], bindings.hann)] for ch in range(4)], dtype=np.int64)
    if np.any(gate_window < -(1 << 24)) or np.any(gate_window >= (1 << 24)):
        raise RuntimeError("GATE_WINDOW_S25_OVERFLOW")
    doa_window, window_overflow = leaf.window_pcm(x.T, bindings.hann)
    for ch in range(4):
        _set(status, f"mean_{ch}", "OK")
        _set(status, f"gate_window_{ch}", "OK")
        _set(status, f"doa_window_{ch}",
             "NUMERIC_INVALID_OVERFLOW_GROUP" if window_overflow else "OK")
    arrays.update(mean_s24=means, gate_centered_s25=centered.T.copy(),
                  gate_window_s25=gate_window, doa_window_s24=doa_window)
    full = {}
    half = {}
    for domain, window in (("gate", gate_window), ("doa", doa_window)):
        spectra = np.empty((4, 1024, 2), dtype=np.int64)
        for ch in range(4):
            spectra[ch], flags = fixed_fft_table([(int(v) << 4, 0) for v in window[ch]],
                                                  inverse=False, width=29, bindings=bindings)
            detail["fft_flags"][domain].append(flags)
            _set(status, f"{domain}_fft_{ch}", "NUMERIC_OK_WAIT_EXTERNAL" if not flags["overflow_count"] else "NUMERIC_INVALID_OVERFLOW")
            if flags["overflow_count"]:
                detail["invalid_reasons"].append(f"{domain}_fft_{ch}_OVERFLOW")
        adapted = adapt_half_s29(spectra[:, :513], frame_identity=frame_identity,
                                 domain=domain, bindings=bindings)
        spectra_half = adapted["payload_s25"]
        detail["fixed4"][domain] = adapted["summary"]
        for ch in range(4):
            channel_bad = adapted["summary"]["invalid_complex_by_channel"][ch] > 0
            _set(status, f"{domain}_fixed4_{ch}",
                 "NUMERIC_INVALID_OVERFLOW" if channel_bad else "NUMERIC_OK_WAIT_EXTERNAL")
            if channel_bad:
                detail["invalid_reasons"].append(f"{domain}_FIXED4_CH{ch}_OVERFLOW")
        full[domain], half[domain] = spectra, spectra_half
        arrays[domain + "_fft29"] = spectra
        arrays[domain + "_half25"] = spectra_half
        arrays[domain + "_fixed4_numeric_valid"] = adapted["numeric_valid"]
        arrays[domain + "_fixed4_overflow_components"] = adapted["overflow_components"]
    detail["fixed4_totals"] = {
        "overflow_components": sum(detail["fixed4"][domain]["overflow_components_total"]
                                   for domain in ("gate", "doa")),
        "invalid_complex": sum(detail["fixed4"][domain]["invalid_complex_total"]
                               for domain in ("gate", "doa")),
    }
    if window_overflow:
        detail["invalid_reasons"].append("DOA_WINDOW_OVERFLOW")
    detail["numeric_invalid"] = bool(detail["invalid_reasons"])
    denominator = sum(int(w) ** 2 for w in bindings.hann)
    sums = [sum(int(a) ** 2 + int(b) ** 2 for a, b in half["gate"][ch, 7:73]) for ch in range(4)]
    numerator = [2 * n * 1024 * (1 << 34) for n in sums]
    power = [leaf.rne_div(n, denominator) for n in numerator]
    if any(n >= (1 << 104) for n in numerator) or any(n < 0 or n >= (1 << 64) for n in power):
        detail["invalid_reasons"].append("GATE_POWER_WIDTH")
        detail["numeric_invalid"] = True
    else:
        arrays["gate_band_power_u64"] = np.asarray(power, dtype=np.uint64)
    if detail["numeric_invalid"]:
        activity.reset()
        gate_state = {"active": False, "attack": 0, "release": 0, "reason": "NUMERIC_INVALID_RESET"}
        _set(status, "gate_state", "NUMERIC_INVALID")
    else:
        gate_state = activity.update(power)
        gate_state["reason"] = "VALID_POWER"
        _set(status, "gate_state", "OK")
    detail["gate_state"] = gate_state
    pair_rows = [{"valid": False, "reason": "NOT_RUN"} for _ in PAIRS]
    crosses = np.zeros((6, 513, 2), dtype=np.int64)
    phat_codes = np.zeros((6, 513, 2), dtype=np.int64)
    masks = np.zeros((6, 513), dtype=np.uint8)
    correlations = np.zeros((6, 1024), dtype=np.int64)
    if not gate_state["active"] or detail["numeric_invalid"]:
        reason = "SKIPPED_NUMERIC_INVALID" if detail["numeric_invalid"] else "SKIPPED_GATE_CLOSED"
        for pair in PAIRS:
            for kind in ("phat", "ifft", "lag"):
                _set(status, kind + "_" + pair, reason)
        _set(status, "doa", reason)
        doa = {"valid": False, "reason": reason}
    else:
        for k, ((i, j), pair) in enumerate(zip(leaf.PAIRS, PAIRS)):
            crosses[k] = np.asarray([bindings.phat.cross(a, b) for a, b in zip(
                half["doa"][i], half["doa"][j])], dtype=np.int64)
            try:
                phat = bindings.phat.phat_pair(
                    half["doa"][i].tolist(), half["doa"][j].tolist(),
                    [7 <= n <= 85 for n in range(513)])
            except (ValueError, OverflowError) as exc:
                reason = type(exc).__name__ + ":" + str(exc)
                detail["invalid_reasons"].append("PHAT_" + pair + ":" + reason)
                pair_rows[k] = {"valid": False, "reason": "NUMERIC_INVALID_PHAT"}
                _set(status, "phat_" + pair, "NUMERIC_INVALID_PHAT")
                _set(status, "ifft_" + pair, "SKIPPED_NUMERIC_INVALID")
                _set(status, "lag_" + pair, "SKIPPED_NUMERIC_INVALID")
                detail["ifft_flags"].append({"not_run": True, "reason": reason})
                continue
            masks[k] = np.asarray(phat["mask"], dtype=np.uint8)
            if not phat["valid"]:
                pair_rows[k] = {"valid": False, "reason": phat["reason"]}
                _set(status, "phat_" + pair, "ALGORITHM_REJECTED:" + phat["reason"])
                _set(status, "ifft_" + pair, "SKIPPED_PAIR_UNUSABLE")
                _set(status, "lag_" + pair, "SKIPPED_PAIR_UNUSABLE")
                detail["ifft_flags"].append({"not_run": True, "reason": phat["reason"]})
                continue
            _set(status, "phat_" + pair, "OK")
            phat_codes[k] = np.asarray(phat["output"], dtype=np.int64)
            try:
                complete = bindings.guards.checked_conjugate(phat_codes[k], leaf.conjugate_complete)
            except ValueError as exc:
                detail["invalid_reasons"].append("CONJUGATE_" + pair + ":" + str(exc))
                _set(status, "ifft_" + pair, "NUMERIC_INVALID_CONJUGATE")
                _set(status, "lag_" + pair, "SKIPPED_NUMERIC_INVALID")
                detail["ifft_flags"].append({"not_run": True, "reason": "CONJUGATE_INVALID"})
                continue
            corr_complex, flags = fixed_fft_table(complete, inverse=True, width=25, bindings=bindings)
            detail["ifft_flags"].append(flags)
            if flags["overflow_count"]:
                detail["invalid_reasons"].append("IFFT_" + pair + "_OVERFLOW")
                _set(status, "ifft_" + pair, "NUMERIC_INVALID_OVERFLOW")
                _set(status, "lag_" + pair, "SKIPPED_NUMERIC_INVALID")
                continue
            _set(status, "ifft_" + pair, "NUMERIC_OK_WAIT_EXTERNAL")
            correlations[k] = corr_complex[:, 0]
            lag = leaf.lag_q12(correlations[k], leaf.PAIR_LENGTH_SQ[k])
            pair_rows[k] = lag
            _set(status, "lag_" + pair, "OK" if lag["valid"] else "ALGORITHM_REJECTED:" + lag["reason"])
        detail["numeric_invalid"] = bool(detail["invalid_reasons"])
        if detail["numeric_invalid"]:
            activity.reset()
            _set(status, "doa", "SKIPPED_NUMERIC_INVALID")
            doa = {"valid": False, "reason": "NUMERIC_INVALID"}
        else:
            doa = solve_doa_vector_q20(pair_rows, leaf)
            if doa["valid"]:
                x_q20, y_q20 = doa["ux_q20"], doa["uy_q20"]
                if x_q20 == y_q20 == 0:
                    detail["invalid_reasons"].append("CORDIC_ZERO_VECTOR")
                    detail["numeric_invalid"] = True
                    activity.reset()
                    _set(status, "doa", "NUMERIC_INVALID_CORDIC")
                    doa = {**doa, "valid": False, "reason": "CORDIC_ZERO_VECTOR"}
                else:
                    doa["azimuth_q8_deg"] = bindings.cordic.normalized_atan2_q8(y_q20, x_q20, leaf.atan2_q8)
                    detail["cordic"] = "OK_NORMALIZED_S23"
                    _set(status, "doa", "OK")
            else:
                _set(status, "doa", "ALGORITHM_REJECTED:" + doa["reason"])
    detail["pair_rows"] = pair_rows
    detail["doa"] = doa
    arrays["phat_cross_s51"] = crosses
    arrays["phat_s25"] = phat_codes
    arrays["phat_mask"] = masks
    arrays["ifft_real"] = correlations
    for key in ("tracker", "result_binding"):
        _set(status, key, "PENDING_TIME_BINDING")
    return {"arrays": arrays, "detail": detail, "units": status,
            "expected": expected_units(), "candidate_angle_q8": doa.get("azimuth_q8_deg") if doa.get("valid") else None}
