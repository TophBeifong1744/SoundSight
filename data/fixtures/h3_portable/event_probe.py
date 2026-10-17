"""Bounded synthetic-time causality tests; injected candidate is labelled."""
import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np


def expect_error(fn, label):
    try:
        fn()
    except ValueError as exc:
        if label not in str(exc):
            raise AssertionError(f"WRONG_ERROR:{label}:{exc}") from exc
        return str(exc)
    raise AssertionError("EXPECTED_REJECTION_MISSING:" + label)


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

    pcm = np.load(a.fixture / "pcm.npy", allow_pickle=False)
    config = json.loads((a.fixture / "config.json").read_text())
    schedule = json.loads((a.fixture / "schedule.json").read_text())

    def execute(cfg=config, sch=schedule, data=pcm):
        return chain.run_causal_interval(data, copy.deepcopy(cfg), copy.deepcopy(sch), 0, Bindings(a.repo))

    result = {"scope": "SYNTHETIC_TIME only; no hardware cycles or production TTL"}
    equal = copy.deepcopy(schedule)
    equal["result_ttl_samples"] = 3  # last_id+3 equals each declared take
    equality = execute(sch=equal)
    assert len(equality["frames"]) == 7 and all(r["take"] == r["expiry"] for r in equality["frames"])
    result["ttl_equal"] = {"frames": len(equality["frames"]), "boundary": "take == last_id+3"}
    short = copy.deepcopy(equal)
    short["result_ttl_samples"] = 2
    result["ttl_exceeded"] = expect_error(lambda: execute(sch=short), "T_RESULT_EXPIRED")
    zero = copy.deepcopy(equal)
    zero["result_ttl_samples"] = 0
    result["ttl_zero_legal_config_but_expired_take"] = expect_error(
        lambda: execute(sch=zero), "T_RESULT_EXPIRED")
    huge = copy.deepcopy(schedule)
    huge["result_ttl_samples"] = (1 << 63) - 1
    result["ttl_overflow"] = expect_error(lambda: execute(sch=huge), "T_RESULT_OVERFLOW")

    missing = copy.deepcopy(schedule)
    del missing["frames"][0]["external_visible_at"]["transport"]
    result["missing_status"] = expect_error(lambda: execute(sch=missing), "EXTERNAL_STATUS_SET_MISMATCH")
    late = copy.deepcopy(schedule)
    late["frames"][0]["external_visible_at"]["transport"] += 1
    result["late_status"] = expect_error(lambda: execute(sch=late), "STATUS_NOT_VISIBLE_BY_AVAILABLE")
    error = copy.deepcopy(schedule)
    error["frames"] = error["frames"][:4]
    error["frames"][3]["external_error_units"] = ["gate_fixed4_1"]
    with_error = execute(sch=error, data=pcm[:, :2560])
    failed = with_error["frames"][3]
    assert failed["invalid"] and not failed["fresh"] and failed["state"] == "SEARCH"
    assert failed["take_status"] == "REJECTED_NUMERIC_OR_PROTOCOL_INVALID"
    assert with_error["stages"][3]["units"]["gate_fixed4_1"] == "EXTERNAL_ERROR"
    result["external_error"] = {"frame": 3, "state": failed["state"],
                                "take_status": failed["take_status"]}

    # A declared candidate rejection tests Tracker HOLD/expiry propagation;
    # it is not a claim that the legal PCM scene naturally rejects direction.
    hold_cfg = copy.deepcopy(config)
    hold_cfg["tracker"]["hold_samples"] = 600
    original = chain.solve_doa_vector_q20
    calls = 0
    def reject_twice(rows, leaf):
        nonlocal calls
        index = calls
        calls += 1
        if index in (2, 3):  # active frame4/frame5 after frame3 first fresh
            return {"valid": False, "reason": "INJECTED_CANDIDATE_REJECTION"}
        return original(rows, leaf)
    chain.solve_doa_vector_q20 = reject_twice
    try:
        held = execute(cfg=hold_cfg)
    finally:
        chain.solve_doa_vector_q20 = original
    assert calls == 5
    fresh3, hold4, expired5 = held["frames"][3:6]
    assert fresh3["fresh"] and fresh3["state"] == "LOCKED"
    assert hold4["state"] == "HOLD" and not hold4["fresh"]
    assert hold4["tracker"]["last_fresh_sample"] == fresh3["available"]
    assert hold4["tracker"]["valid_through_sample"] == fresh3["available"] + 600
    assert hold4["control"]["state"] == "HOLD"
    assert expired5["state"] == "SEARCH" and not expired5["fresh"]
    assert expired5["tracker"]["last_fresh_sample"] is None
    # Audio has its separate declared frame3 deadline (3584), which HOLD may
    # not refresh; Tracker hold expiration above is independently 3160.
    audio_events = held["audio"]["events"]
    assert any(e["kind"] == "HOLD" and e["emit"] == hold4["take"] for e in audio_events)
    assert any(e["kind"] == "TTL_EXPIRED" and e["emit"] == 3585 for e in audio_events)
    result["hold_then_expire"] = {"last_fresh": fresh3["available"],
                                  "hold_at": hold4["available"], "expired_at": expired5["available"],
                                  "hold_valid_through": hold4["tracker"]["valid_through_sample"]}

    gap_cfg = copy.deepcopy(config)
    gap_cfg["tracker"]["max_gap_samples"] = 700
    gap = copy.deepcopy(schedule)
    gap["frames"][4]["available"] = 3400
    gap["frames"][4]["commit_now"] = 3401
    gap["frames"][4]["take_now"] = 3402
    after_gap = execute(cfg=gap_cfg, sch=gap)
    assert after_gap["frames"][3]["fresh"]
    assert after_gap["frames"][4]["state"] == "ACQUIRE"
    assert not after_gap["frames"][4]["fresh"]
    assert after_gap["frames"][4]["tracker"]["reason"] == "gap_reset_acquire"
    result["gap_reacquire"] = {"previous_available": after_gap["frames"][3]["available"],
                               "gap_available": after_gap["frames"][4]["available"],
                               "state": after_gap["frames"][4]["state"]}

    short_pcm = pcm[:, :2560]
    base4 = copy.deepcopy(schedule)
    base4["frames"] = base4["frames"][:4]
    fatal = copy.deepcopy(base4)
    fatal["fatal_emit"] = 2500
    fatal["stop_emit"] = 2500
    aborted = execute(sch=fatal, data=short_pcm)
    assert aborted["status"] == "ABORTED" and aborted["frames"][3]["state"] == "CANCELLED"
    assert aborted["frames"][3]["suppressed"] == ["FRAME_TAKE_CANCELLED_BY_FATAL"]
    assert aborted["terminations"][3]["reason"] == "FATAL_BEFORE_AVAILABLE"
    assert aborted["terminations"][3]["time_basis"] == "SYNTHETIC_TIME"
    assert len(aborted["audio"]["automatic_raw"]) == 2500
    assert aborted["audio"]["aborted_at_emit"] == 2500
    result["fatal_over_stop"] = {"emit": 2500, "raw_length": len(aborted["audio"]["automatic_raw"]),
                                 "previous_frame_state": aborted["frames"][2]["state"]}
    stop = copy.deepcopy(base4)
    stop["stop_emit"] = 2500
    stopped = execute(sch=stop, data=short_pcm)
    assert stopped["status"] == "COMPLETED" and stopped["frames"][3]["state"] == "STOPPED"
    assert stopped["frames"][3]["suppressed"] == ["FRAME_TAKE_CANCELLED_BY_STOP"]
    assert stopped["terminations"][3]["reason"] == "STOP_BEFORE_AVAILABLE"
    assert stopped["audio"]["aborted_at_emit"] is None
    assert len(stopped["audio"]["automatic_raw"]) == 2568
    result["smooth_stop"] = {"emit": 2500, "raw_length": len(stopped["audio"]["automatic_raw"])}

    (a.out / "result.json").write_text(json.dumps({"status": "PASS_BOUNDED_CAUSAL",
        "checks": result}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS_BOUNDED_CAUSAL", "checks": list(result)}))


if __name__ == "__main__":
    main()
