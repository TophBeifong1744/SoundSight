"""Check a saved portable cancellation result against a schedule-derived oracle."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from cancel_contract import expected
from independent_contract import ALL_UNITS


class CheckFailure(Exception):
    pass


def need(ok, label):
    if not ok:
        raise CheckFailure(label)


def compare_rows(actual, wanted, label, *, time_key):
    need(type(actual) is list, label + ":TYPE")
    expected_map = {(row["frame"], row["unit"]): row for row in wanted}
    observed_map = {}
    previous_order = None
    for index, row in enumerate(actual):
        need(type(row) is dict, label + f":ROW_FORMAT:{index}")
        if wanted:
            need(set(row) == set(wanted[0]), label + f":ROW_KEYS:{index}")
        key = (row.get("frame"), row.get("unit"))
        need(key in expected_map, label + f":EXTRA:{key}")
        need(key not in observed_map, label + f":DUPLICATE:{key}")
        need(row == expected_map[key], label + f":ROW:{key}:expected={expected_map[key]}:observed={row}")
        observed_map[key] = row
        if label == "EVENT_HISTORY":
            priority = 2 if row["unit"] == "tracker" else 3 if row["unit"] == "result_binding" else 4 if row["unit"] == "take" else 0
            order = (row[time_key], priority)
            need(previous_order is None or previous_order <= order,
                 label + f":CAUSAL_ORDER:{index}")
            previous_order = order
    need(set(observed_map) == set(expected_map),
         label + f":KEY_MISSING:{sorted(set(expected_map)-set(observed_map))}")


def check(result, schedule, arrays):
    oracle = expected(schedule, arrays)
    need(result.get("time_basis") == "SYNTHETIC_TIME", "TIME_BASIS")
    need(result.get("planned_frames") == len(schedule["frames"]), "FRAME_COUNT")
    need(len(result.get("frames", [])) == len(schedule["frames"]), "FRAME_ROWS")
    need(result.get("status") == ("ABORTED" if schedule.get("fatal_emit") is not None else "COMPLETED"),
         "INTERVAL_STATUS")
    compare_rows(result.get("events"), oracle["events"], "EVENT_HISTORY", time_key="visible_at")
    compare_rows(result.get("observations"), oracle["observations"],
                 "SAME_EDGE_OBSERVATIONS", time_key="observed_at")
    actual_terms = result.get("terminations")
    need(type(actual_terms) is list and len(actual_terms) == len(oracle["terminations"]),
         "TERMINATION_COUNT")
    need(len(result.get("stage_details", [])) == len(actual_terms), "STAGE_COUNT")
    for frame, (got, want) in enumerate(zip(actual_terms, oracle["terminations"])):
        need(type(got) is dict, f"TERMINATION_FORMAT:{frame}")
        for key in ("identity", "time_basis", "at", "reason"):
            need(got.get(key) == want[key], f"TERMINATION_{key.upper()}:{frame}")
        units = got.get("expected_units")
        need(type(units) is list and len(units) == 53 and len(set(units)) == 53
             and set(units) == set(ALL_UNITS), f"TERMINATION_EXPECTED_SET:{frame}")
        final, cancelled = got.get("final_before"), got.get("cancelled_units")
        need(type(final) is dict and type(cancelled) is list, f"TERMINATION_PARTITION_TYPE:{frame}")
        need(len(cancelled) == len(set(cancelled)) and not (set(final) & set(cancelled))
             and set(final) | set(cancelled) == set(ALL_UNITS),
             f"TERMINATION_PARTITION:{frame}")
        need(final == want["final_before"], f"TERMINATION_FINAL_BEFORE:{frame}")
        need(cancelled == want["cancelled_units"], f"TERMINATION_CANCELLED:{frame}")
        for key in ("ever_committed", "ever_taken", "successful_commit_at",
                    "successful_take_at", "later_interval_end_at",
                    "later_interval_end_reason", "prior_binding_retracted"):
            need(got.get(key) == want[key], f"TERMINATION_{key.upper()}:{frame}")
        stage = result["stage_details"][frame]
        declared = stage.get("expected")
        need(type(declared) is list and len(declared) == 53 and len(set(declared)) == 53
             and set(declared) == set(ALL_UNITS), f"STAGE_EXPECTED:{frame}")
        need(stage.get("units") == oracle["stages"][frame], f"STAGE_UNITS:{frame}")
        row = result["frames"][frame]
        need(row.get("frame") == frame and row.get("last_id") == want["identity"]["last_id"],
             f"FRAME_IDENTITY:{frame}")
        need((row.get("available"), row.get("commit"), row.get("take")) ==
             tuple(schedule["frames"][frame][k] for k in ("available", "commit_now", "take_now")),
             f"FRAME_TIMING:{frame}")
        if oracle["edge"] is not None and oracle["edge"] <= row["take"]:
            need(row.get("state") == ("CANCELLED" if oracle["reason"] == "FATAL" else "STOPPED")
                 and not row.get("fresh"), f"FRAME_CANCELLED:{frame}")
        need(not any(e["frame"] == frame and e["unit"] in ("result_binding", "take")
                     and e["visible_at"] >= oracle["edge"] for e in result["events"])
             if oracle["edge"] is not None else True, f"POST_EDGE_SUCCESS:{frame}")
    return {"frames": len(actual_terms), "normal_events": len(oracle["events"]),
            "observations": len(oracle["observations"]), "edge": oracle["edge"],
            "frame3_events": sum(e["frame"] == 3 for e in oracle["events"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--schedule", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    a = ap.parse_args()
    result = json.loads(a.result.read_text(encoding="utf-8"))
    schedule = json.loads(a.schedule.read_text(encoding="utf-8"))
    with np.load(a.reference, allow_pickle=False) as source:
        arrays = {key: source[key] for key in source.files}
    print(json.dumps({"status": "CHECKER_PASS_SCOPE_ONLY", "checked": check(result, schedule, arrays)}))


if __name__ == "__main__":
    try:
        main()
    except (CheckFailure, ValueError, KeyError, TypeError) as exc:
        print("CHECK_FAIL:" + str(exc), file=sys.stderr)
        sys.exit(1)
