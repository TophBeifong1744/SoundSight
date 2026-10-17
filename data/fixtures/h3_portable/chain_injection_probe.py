"""Test-side S29 overflow injection at one forward FFT output per scenario.

This proves chain error propagation. It does not claim that legal PCM naturally
reaches the injected S29 value, and it does not replace the normal CLI run.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    sys.path.insert(0, str(a.repo / "models/python"))
    from soundsight_h3_portable.bindings import Bindings
    from soundsight_h3_portable import chain

    pcm = np.load(a.fixture / "pcm.npy", allow_pickle=False)[:, :2560]
    config = json.loads((a.fixture / "config.json").read_text())
    source_schedule = json.loads((a.fixture / "schedule.json").read_text())
    output = {}
    for domain, bin_index in (("gate", 0), ("doa", 512)):
        schedule = copy.deepcopy(source_schedule)
        schedule["frames"] = schedule["frames"][:4]
        for key in list(schedule["frames"][3]["external_visible_at"]):
            if key.startswith("ifft_") or key == f"{domain}_fixed4_1":
                del schedule["frames"][3]["external_visible_at"][key]
        original = chain.fixed_fft_table
        forward_count = 0
        target = 3 * 8 + (0 if domain == "gate" else 4) + 1

        def injected(*args, **kwargs):
            nonlocal forward_count
            value, flags = original(*args, **kwargs)
            if not kwargs["inverse"]:
                if forward_count == target:
                    value = value.copy()
                    value[bin_index, 0] = (1 << 28) - 1
                forward_count += 1
            return value, flags

        chain.fixed_fft_table = injected
        try:
            result = chain.run_causal_interval(pcm, config, schedule, 0, Bindings(a.repo))
        finally:
            chain.fixed_fft_table = original
        assert forward_count == 32, (domain, forward_count)
        row = result["frames"][3]
        stage = result["stages"][3]
        fixed = stage["detail"]["fixed4"][domain]
        assert result["frames"][2]["state"] == "ACQUIRE"
        assert row["invalid"] and not row["fresh"] and row["state"] == "SEARCH"
        assert row["tracker"]["reason"] == "NUMERIC_OR_PROTOCOL_INVALID_RESET"
        assert row["commit_status"] == row["take_status"] == "REJECTED_NUMERIC_OR_PROTOCOL_INVALID"
        assert stage["units"][f"{domain}_fixed4_1"] == "NUMERIC_INVALID_OVERFLOW"
        assert all(stage["units"][f"{domain}_fixed4_{ch}"] == "OK"
                   for ch in (0, 2, 3))
        assert fixed["invalid_complex_by_channel"] == [0, 1, 0, 0]
        assert fixed["invalid_locations"] == [{"channel": 1, "bin": bin_index,
                                                 "real_overflow": True,
                                                 "imag_overflow": False}]
        assert not stage["arrays"][f"{domain}_fixed4_numeric_valid"][1, bin_index]
        assert tuple(stage["arrays"][f"{domain}_half25"][1, bin_index]) == (0, 0)
        assert stage["arrays"][f"{domain}_fixed4_numeric_valid"][1, bin_index + (-1 if bin_index else 1)]
        assert all(stage["units"][f"{kind}_{pair}"] == "SKIPPED_NUMERIC_INVALID"
                   for kind in ("phat", "ifft", "lag")
                   for pair in ("01", "02", "03", "12", "13", "23"))
        take_events = [e for e in result["events"] if e["frame"] == 3 and e["unit"] == "take"]
        assert len(take_events) == 1 and take_events[0]["result"] == "REJECTED_NUMERIC_OR_PROTOCOL_INVALID"
        assert all(not (e["frame"] == 3 and e["result"] in ("TAKEN_FRESH", "BOUND_FRESH"))
                   for e in result["events"])
        output[domain] = {"target_forward_ordinal": target, "target_channel": 1,
                          "target_bin": bin_index, "frame": row, "fixed4": fixed,
                          "gate_state": stage["detail"]["gate_state"],
                          "units": stage["units"], "take_event": take_events[0]}
    (a.out / "result.json").write_text(json.dumps({"status": "PASS_INJECTED_ERROR_PROPAGATION",
        "injection_scope": "test-side one S29 forward FFT output; no legal PCM reachability claim",
        "scenarios": output}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS_INJECTED_ERROR_PROPAGATION", "domains": list(output)}))


if __name__ == "__main__":
    main()
