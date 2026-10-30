"""Independent integer oracle for the new four-channel fixed4 boundary."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np


def rne16(value):
    magnitude, remainder = divmod(abs(int(value)), 16)
    if remainder > 8 or (remainder == 8 and magnitude % 2):
        magnitude += 1
    return -magnitude if value < 0 else magnitude


def oracle(values):
    rounded = np.empty(values.shape, dtype=np.int64)
    flags = np.empty(values.shape, dtype=np.bool_)
    for index in np.ndindex(values.shape):
        code = rne16(values[index])
        rounded[index] = code
        flags[index] = not (-(1 << 24) <= code < (1 << 24))
    valid = ~np.any(flags, axis=2)
    rounded[~valid] = 0
    return rounded, valid, flags


def check(actual, expected, label):
    for key, value in zip(("payload_s25", "numeric_valid", "overflow_components"), expected):
        got = actual[key]
        if not isinstance(got, np.ndarray) or got.dtype != value.dtype or got.shape != value.shape:
            raise AssertionError(f"{label}:{key}:SHAPE_OR_DTYPE")
        difference = np.argwhere(got != value)
        if len(difference):
            index = tuple(map(int, difference[0]))
            raise AssertionError(f"{label}:{key}:{index}:expected={value[index]}:observed={got[index]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    sys.path.insert(0, str(a.repo / "models/python"))
    from soundsight_h3_portable.bindings import Bindings
    from soundsight_h3_portable.fixed4 import adapt_half_s29

    bindings = Bindings(a.repo)
    identity = dict(boot="probe-boot", session="probe-session", interval="probe-interval",
                    frame=7, generation=3, last_id=4607)
    values = np.zeros((4, 513, 2), dtype=np.int64)
    cases = {
        (0, 0, 0): (1 << 28) - 9,
        (0, 1, 0): (1 << 28) - 8,
        (0, 2, 0): (1 << 28) - 1,
        (0, 3, 0): -(1 << 28),
        (0, 4, 0): 8, (0, 5, 0): -8,
        (0, 6, 0): 24, (0, 7, 0): -24,
        (1, 512, 1): (1 << 28) - 1,
        (2, 73, 0): (1 << 28) - 1,
        (2, 73, 1): (1 << 28) - 1,
        (2, 74, 0): 41,
        (3, 73, 0): -41,
    }
    for index, code in cases.items():
        values[index] = code
    expected = oracle(values)
    results = {}
    for domain in ("gate", "doa"):
        actual = adapt_half_s29(values, frame_identity=identity, domain=domain, bindings=bindings)
        check(actual, expected, domain)
        summary = actual["summary"]
        counts = np.count_nonzero(expected[2], axis=1).tolist()
        invalid = np.count_nonzero(~expected[1], axis=1).tolist()
        assert summary["domain"] == domain and summary["frame_identity"] == identity
        assert summary["overflow_components_by_channel"] == counts
        assert summary["invalid_complex_by_channel"] == invalid
        assert summary["overflow_components_total"] == sum(sum(row) for row in counts)
        assert summary["invalid_complex_total"] == sum(invalid)
        assert {(row["channel"], row["bin"]) for row in summary["invalid_locations"]} == \
               {(int(ch), int(bin_index)) for ch, bin_index in np.argwhere(~expected[1])}
        results[domain] = {"overflow_components_by_channel": counts,
                           "invalid_complex_by_channel": invalid,
                           "invalid_locations": summary["invalid_locations"]}

    # Isolated output mutations prove that each published axis is checked.
    baseline = adapt_half_s29(values, frame_identity=identity, domain="gate", bindings=bindings)
    canaries = {}
    for name, key, index in (
        ("payload", "payload_s25", (2, 74, 0)),
        ("numeric_valid", "numeric_valid", (0, 1)),
        ("real_overflow", "overflow_components", (0, 1, 0)),
        ("imag_overflow", "overflow_components", (1, 512, 1)),
        ("channel_attribution", "overflow_components", (3, 73, 0)),
    ):
        bad = dict(baseline)
        bad[key] = baseline[key].copy()
        if key == "payload_s25":
            bad[key][index] += 1
        else:
            bad[key][index] = ~bad[key][index]
        try:
            check(bad, expected, name)
        except AssertionError as exc:
            canaries[name] = str(exc)
        else:
            raise AssertionError("CANARY_NOT_CAUGHT:" + name)

    invalid_inputs = {
        "shape": np.zeros((4, 512, 2), dtype=np.int64),
        "float": np.zeros((4, 513, 2), dtype=np.float64),
        "positive_out_of_s29": np.full((4, 513, 2), 1 << 28, dtype=np.int64),
        "negative_out_of_s29": np.full((4, 513, 2), -(1 << 28) - 1, dtype=np.int64),
    }
    for name, bad in invalid_inputs.items():
        try:
            adapt_half_s29(bad, frame_identity=identity, domain="gate", bindings=bindings)
        except ValueError:
            pass
        else:
            raise AssertionError("INVALID_INPUT_ACCEPTED:" + name)
    for name, domain, ident in (("domain", "unknown", identity),
                                ("identity", "gate", {"frame": 7})):
        try:
            adapt_half_s29(values, frame_identity=ident, domain=domain, bindings=bindings)
        except ValueError:
            pass
        else:
            raise AssertionError("INVALID_INPUT_ACCEPTED:" + name)

    result = {"status": "PASS_BOUNDARY_SOFTWARE", "contract": "B14-02 RNE>>4 atomic complex",
              "cases": {str(k): v for k, v in cases.items()}, "domains": results,
              "isolated_negative_canaries": canaries,
              "invalid_inputs_rejected": list(invalid_inputs) + ["domain", "identity"],
              "scope": "direct new fixed4 entry; legal PCM reachability tested separately"}
    (a.out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "negative_canaries": len(canaries)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
