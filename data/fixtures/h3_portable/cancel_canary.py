"""Subprocess negative canaries for the independent cancellation checker."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    here = Path(__file__).resolve().parent
    cases = {
        "drop_pre_event": ("fatal2561", "EVENT_HISTORY", lambda x: x["events"].pop(
            next(i for i, e in enumerate(x["events"]) if e["frame"] == 3 and e["unit"] == "transport"))),
        "rewrite_prior_binding": ("fatal2562", "EVENT_HISTORY", lambda x: next(
            e for e in x["events"] if e["frame"] == 3 and e["unit"] == "result_binding")
            .update(result="CANCELLED_BY_TRANSACTION")),
        "success_take_at_edge": ("fatal2562", "EVENT_HISTORY", lambda x: x["events"].append(
            {"frame": 3, "unit": "take", "visible_at": 2562, "result": "TAKEN_FRESH"})),
        "success_take_after_edge": ("fatal2561", "EVENT_HISTORY", lambda x: x["events"].append(
            {"frame": 3, "unit": "take", "visible_at": 2562, "result": "TAKEN_FRESH"})),
        "duplicate_termination": ("fatal2561", "TERMINATION_COUNT", lambda x: x["terminations"].append(
            copy.deepcopy(x["terminations"][3]))),
        "missing_termination": ("fatal2561", "TERMINATION_COUNT", lambda x: x["terminations"].pop()),
        "wrong_boot": ("fatal2561", "TERMINATION_IDENTITY", lambda x: x["terminations"][3]
            ["identity"].update(boot="WRONG_BOOT")),
        "missing_unit": ("fatal2561", "TERMINATION_EXPECTED_SET", lambda x: x["terminations"][3]
            ["expected_units"].remove("mean_0")),
        "partition_overlap": ("fatal2561", "TERMINATION_PARTITION", lambda x: x["terminations"][3]
            ["cancelled_units"].append("transport")),
        "wrong_visible_time": ("fatal2561", "EVENT_HISTORY", lambda x: next(
            e for e in x["events"] if e["frame"] == 3 and e["unit"] == "transport")
            .update(visible_at=2559)),
        "wrong_event_frame": ("fatal2561", "EVENT_HISTORY", lambda x: next(
            e for e in x["events"] if e["frame"] == 3 and e["unit"] == "transport")
            .update(frame=2)),
        "drop_same_edge_observation": ("fatal2560", "SAME_EDGE_OBSERVATIONS", lambda x:
            x["observations"].pop()),
        "erase_pre_error": ("pre_error", "EVENT_HISTORY", lambda x: next(
            e for e in x["events"] if e["frame"] == 3 and e["unit"] == "transport")
            .update(result="OK")),
    }
    records = []
    for label, (source, expected, mutation) in cases.items():
        original = a.run / source / "dut/result.json"
        mutated = json.loads(original.read_text(encoding="utf-8"))
        mutation(mutated)
        path = a.out / (label + ".json")
        path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        argv = [str(a.python), "-B", str(here / "cancel_checker.py"), "--result", str(path),
                "--schedule", str(a.run / source / "schedule.json"),
                "--reference", str(a.reference)]
        p = subprocess.run(argv, cwd=here, capture_output=True)
        (a.out / (label + ".stdout.log")).write_bytes(p.stdout)
        (a.out / (label + ".stderr.log")).write_bytes(p.stderr)
        stderr = p.stderr.decode("utf-8", errors="replace")
        records.append({"name": label, "source": source, "argv": argv, "cwd": str(here),
                        "exit_code": p.returncode, "expected_label": expected,
                        "first_error": stderr.splitlines()[0] if stderr else None,
                        "pass": p.returncode != 0 and expected in stderr})
    (a.out / "result.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if not all(row["pass"] for row in records):
        print("CANARY_FAIL", file=sys.stderr)
        return 1
    print(json.dumps({"status": "CANARY_PASS", "cases": len(records)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
