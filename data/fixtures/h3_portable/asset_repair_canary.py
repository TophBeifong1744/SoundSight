"""Replay frozen outputs and isolate V2-01/02 checker mutations.

All result mutations are made on copies. One saved-result copy is sent through
the actual checker CLI, so a swallowed exception cannot look like a pass.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

import checker


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--saved", type=Path, required=True,
                    help="Frozen previous final02 directory; read only")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    saved = a.saved.resolve(strict=True)
    fixture = saved / "fixture"
    reference = saved / "reference"
    observed = saved / "causal"
    input_paths = (fixture / "schedule.json", fixture / "pcm.npy",
                   reference / "expected-stages.npz", reference / "reference-summary.json",
                   observed / "result.json", observed / "stages-and-audio.npz")
    before = {str(path): digest(path) for path in input_paths}
    schedule = checker.strict_json(fixture / "schedule.json")
    result = checker.strict_json(observed / "result.json")
    summary = checker.strict_json(reference / "reference-summary.json")
    with np.load(observed / "stages-and-audio.npz", allow_pickle=False) as source:
        arrays = {key: source[key].copy() for key in source.files}
    with np.load(reference / "expected-stages.npz", allow_pickle=False) as source:
        expected = {key: source[key].copy() for key in source.files}
    manifest = checker.strict_json(a.repo / "models/python/soundsight_h3_portable/tables/source-manifest.json")
    rom = manifest["entries"]["delay_rom"]
    context = {"root": a.repo, "pcm_path": fixture / "pcm.npy",
               "delay_path": rom["path"], "delay_sha": rom["sha256"]}

    class ArrayView:
        files = list(expected)
        def __getitem__(self, key):
            return expected[key]

    def evaluate(candidate):
        numeric = checker.compare(candidate, arrays, ArrayView(), schedule, context, 0)
        numeric["independent_direction_frames"] = checker.compare_directions(candidate, summary)
        return numeric

    baseline = evaluate(result)
    cases = {}

    def negative(name, target, mutate):
        changed = copy.deepcopy(result)
        mutate(changed)
        try:
            evaluate(changed)
        except checker.CheckFailure as exc:
            message = str(exc)
            if not message.startswith(target):
                raise AssertionError(f"WRONG_FIRST_FAILURE:{name}:wanted={target}:got={message}") from exc
            cases[name] = {"caught": True, "first_error": message}
        else:
            raise AssertionError("CANARY_ACCEPTED:" + name)

    def remove_mean_everywhere(value):
        for stage in value["stage_details"]:
            stage["expected"].remove("mean_0")
            del stage["units"]["mean_0"]
    negative("v2_01_mean0_removed_from_expected_and_units", "EXPECTED_UNIT_SET:0:", remove_mean_everywhere)
    negative("v2_01_missing_unit_only", "UNIT_STATUS_SET:0:",
             lambda value: value["stage_details"][0]["units"].pop("mean_0"))
    negative("v2_01_extra_unit_only", "UNIT_STATUS_SET:0:",
             lambda value: value["stage_details"][0]["units"].update(invented_unit="OK"))
    negative("v2_01_extra_expected", "EXPECTED_UNIT_SET:0:",
             lambda value: value["stage_details"][0]["expected"].append("invented_unit"))
    negative("v2_01_duplicate_expected", "DUPLICATE_EXPECTED:0",
             lambda value: value["stage_details"][0]["expected"].append("mean_0"))
    negative("v2_01_pending_status", "PENDING_UNIT:0:mean_0",
             lambda value: value["stage_details"][0]["units"].update(mean_0="PENDING"))
    negative("v2_01_wrong_frontend_state", "UNIT_STATE:0:mean_0:",
             lambda value: value["stage_details"][0]["units"].update(mean_0="SKIPPED_GATE_CLOSED"))
    negative("v2_01_wrong_closed_pair_state", "UNIT_STATE:0:phat_01:",
             lambda value: value["stage_details"][0]["units"].update(phat_01="OK"))
    negative("v2_01_wrong_active_lag_state", "UNIT_STATE:3:lag_01:",
             lambda value: value["stage_details"][3]["units"].update(lag_01="OK"))

    def one_event(value, frame, unit):
        matches = [e for e in value["events"] if e["frame"] == frame and e["unit"] == unit]
        assert len(matches) == 1
        return matches[0]

    def replace_completion(value):
        source = one_event(value, 3, "binding")
        destination = one_event(value, 3, "doa_fft_0")
        destination.update(copy.deepcopy(source))
    negative("v2_02_equal_count_missing_and_duplicate", "EVENT_DUPLICATE:3:binding:", replace_completion)
    negative("v2_02_missing_completion", "EVENT_KEY_MISSING:3:doa_fft_0",
             lambda value: value["events"].remove(one_event(value, 3, "doa_fft_0")))
    negative("v2_02_duplicate_completion", "EVENT_DUPLICATE:3:binding:",
             lambda value: value["events"].append(copy.deepcopy(one_event(value, 3, "binding"))))
    negative("v2_02_extra_unknown", "EVENT_EXTRA:3:invented_status",
             lambda value: value["events"].append({"frame": 3, "unit": "invented_status",
                 "visible_at": schedule["frames"][3]["available"], "result": "OK"}))
    negative("v2_02_wrong_frame", "EVENT_EXTRA:7:doa_fft_0",
             lambda value: one_event(value, 3, "doa_fft_0").update(frame=7))
    negative("v2_02_wrong_visible_time", "EVENT_TIME:3:doa_fft_0:",
             lambda value: one_event(value, 3, "doa_fft_0").update(visible_at=999))
    negative("v2_02_wrong_completion_result", "EVENT_RESULT:3:doa_fft_0:",
             lambda value: one_event(value, 3, "doa_fft_0").update(result="EXTERNAL_ERROR"))
    negative("v2_02_wrong_result_binding_time", "EVENT_TIME:3:result_binding:",
             lambda value: one_event(value, 3, "result_binding").update(visible_at=999))
    negative("v2_02_wrong_take_result", "EVENT_RESULT:3:take:",
             lambda value: one_event(value, 3, "take").update(result="TAKEN_NO_FRESH"))

    duplicate_json = a.out / "duplicate-key.json"
    duplicate_json.write_bytes(b'{"mean_0":"OK","mean_0":"PENDING"}')
    try:
        checker.strict_json(duplicate_json)
    except checker.CheckFailure as exc:
        assert str(exc) == "DUPLICATE_JSON_KEY:mean_0"
        cases["v2_01_duplicate_json_unit_key"] = {"caught": True, "first_error": str(exc)}
    else:
        raise AssertionError("DUPLICATE_JSON_UNIT_KEY_ACCEPTED")

    # Real CLI against a separate saved-output copy: equal-count substitution.
    cli_result = a.out / "mutated-result"
    cli_result.mkdir()
    tampered = copy.deepcopy(result)
    replace_completion(tampered)
    (cli_result / "result.json").write_text(json.dumps(tampered, indent=2), encoding="utf-8")
    shutil.copyfile(observed / "stages-and-audio.npz", cli_result / "stages-and-audio.npz")
    argv = [sys.executable, "-B", str(Path(checker.__file__).resolve()),
            "--repo", str(a.repo), "--fixture", str(fixture),
            "--reference", str(reference), "--result", str(cli_result),
            "--manual-angle-q8", "0", "--out", str(a.out / "unexpected-success")]
    process = subprocess.run(argv, capture_output=True, cwd=Path(__file__).resolve().parent)
    (a.out / "subprocess.stdout.log").write_bytes(process.stdout)
    (a.out / "subprocess.stderr.log").write_bytes(process.stderr)
    assert process.returncode != 0 and b"EVENT_DUPLICATE:3:binding:" in process.stderr
    assert not (a.out / "unexpected-success").exists()
    after = {str(path): digest(path) for path in input_paths}
    assert before == after
    packet = {"status": "ASSET_FIX_PENDING_INDEPENDENT_REVIEW",
              "baseline": baseline, "mutations": cases,
              "subprocess": {"argv": argv, "cwd": str(Path(__file__).resolve().parent),
                             "exit_code": process.returncode,
                             "expected_first_error": "EVENT_DUPLICATE:3:binding:",
                             "stdout_sha256": digest(a.out / "subprocess.stdout.log"),
                             "stderr_sha256": digest(a.out / "subprocess.stderr.log"),
                             "mutated_result_sha256": digest(cli_result / "result.json")},
              "saved_inputs_before_after_sha256": before,
              "saved_inputs_unchanged": before == after,
              "scope": "saved final02 replay, no new DUT or reference generation"}
    (a.out / "result.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "baseline_arrays": baseline["compared_arrays"],
                      "mutations_caught": len(cases), "subprocess_exit": process.returncode}))


if __name__ == "__main__":
    main()
