"""Independent integer/causal checker with in-memory negative canaries.

Does not import the DUT or its leaves. It compares the independent arithmetic
reference, predeclared event schedule and audio coordinates to CLI artifacts.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ASSET_DIR = Path(__file__).resolve().parent
if str(ASSET_DIR) not in sys.path:
    sys.path.insert(0, str(ASSET_DIR))
from independent_contract import ALL_UNITS, active, event_map, state_map


class CheckFailure(Exception):
    pass


def require(condition, label):
    if not condition:
        raise CheckFailure(label)


def strict_json(path):
    """Preserve duplicate-key detection before dict construction hides it."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def first_array_difference(observed, expected, name):
    require(observed.shape == expected.shape, name + ":SHAPE")
    require(observed.dtype == expected.dtype, name + ":DTYPE")
    mismatches = np.argwhere(observed != expected)
    if len(mismatches):
        index = tuple(map(int, mismatches[0]))
        raise CheckFailure("NUMERIC_FIRST_DIFFERENCE:" + name + ":" + str(index)
                           + ":expected=" + str(expected[index])
                           + ":observed=" + str(observed[index]))


def manual_reference(pcm, rom, angle_q8):
    delays = (0,) + tuple(map(int, rom[angle_q8 + 46080]))
    count = pcm.shape[1]
    output = np.zeros(count, dtype=np.int64)
    q = 4096
    for n in range(count):
        weighted = 0
        for ch, delay in enumerate(delays):
            position, fraction = divmod(n * q - delay, q)
            left = int(pcm[ch, position]) if 0 <= position < count else 0
            right = int(pcm[ch, position + 1]) if fraction and 0 <= position + 1 < count else 0
            weighted += (q - fraction) * left + fraction * right
        # nearest even with explicit sign handling
        magnitude, remainder = divmod(abs(weighted), 4 * q)
        if 2 * remainder > 4 * q or (2 * remainder == 4 * q and magnitude % 2):
            magnitude += 1
        output[n] = -magnitude if weighted < 0 else magnitude
    return output


def compare(result, arrays, expected, fixture, repo, manual_angle_q8):
    checked = []
    for name in expected.files:
        require(name in arrays, "MISSING_ARRAY:" + name)
        first_array_difference(arrays[name], expected[name], name)
        checked.append(name)
    require(result["claim"] == "PORTABLE_RESEARCH_CONFIG_ONLY", "CLAIM")
    require(result["time_basis"] == "SYNTHETIC_TIME", "TIME_BASIS")
    require(result["status"] == "COMPLETED", "NORMAL_RUN_STATUS")
    require(result["planned_frames"] == 7 and len(result["frames"]) == 7,
            "FRAME_COUNT")
    require(len(result["stage_details"]) == 7, "STAGE_COUNT")
    fresh = 0
    ifft_success = 0
    for i, row in enumerate(result["frames"]):
        detail = result["stage_details"][i]
        units = detail["units"]
        declared = detail["expected"]
        require(isinstance(declared, list) and all(isinstance(name, str) for name in declared),
                "EXPECTED_UNIT_FORMAT:" + str(i))
        require(len(declared) == len(set(declared)), "DUPLICATE_EXPECTED:" + str(i))
        missing_expected = sorted(set(ALL_UNITS) - set(declared))
        extra_expected = sorted(set(declared) - set(ALL_UNITS))
        require(not missing_expected and not extra_expected,
                f"EXPECTED_UNIT_SET:{i}:missing={missing_expected}:extra={extra_expected}")
        require(isinstance(units, dict), "UNIT_STATUS_FORMAT:" + str(i))
        missing_units = sorted(set(ALL_UNITS) - set(units))
        extra_units = sorted(set(units) - set(ALL_UNITS))
        require(not missing_units and not extra_units,
                f"UNIT_STATUS_SET:{i}:missing={missing_units}:extra={extra_units}")
        wanted_states = state_map(i, expected)
        for name in ALL_UNITS:
            require(units[name] != "PENDING", f"PENDING_UNIT:{i}:{name}")
            require(units[name] == wanted_states[name],
                    f"UNIT_STATE:{i}:{name}:expected={wanted_states[name]}:observed={units[name]}")
        require(row["frame"] == i and row["last_id"] == 1023 + i * 512,
                "FRAME_IDENTITY:" + str(i))
        schedule = fixture["frames"][i]
        require((row["available"], row["commit"], row["take"], row["expiry"]) ==
                (schedule["available"], schedule["commit_now"], schedule["take_now"],
                 row["last_id"] + fixture["result_ttl_samples"]), "EVENT_TIMING:" + str(i))
        require(row["last_id"] < row["available"] <= row["commit"] <= row["take"] <= row["expiry"],
                "CAUSAL_ORDER:" + str(i))
        require(row["external_visible"] == schedule["external_visible_at"],
                "EXTERNAL_STATUS_IDENTITY:" + str(i))
        require(row["external_errors"] == [], "UNEXPECTED_EXTERNAL_ERROR:" + str(i))
        for domain in ("gate", "doa"):
            for ch in range(4):
                require(units[f"{domain}_fft_{ch}"] == "OK" and
                        units[f"{domain}_fixed4_{ch}"] == "OK",
                        "FORWARD_UNIT:" + str(i))
        opened = active(i)
        require(bool(detail["detail"]["gate_state"]["active"]) == opened,
                "GATE_ATTACK:" + str(i))
        require(not row["invalid"] and not detail["detail"]["numeric_invalid"],
                "NUMERIC_INVALID:" + str(i))
        require(detail["detail"]["fixed4_totals"] ==
                {"overflow_components": 0, "invalid_complex": 0},
                "FIXED4_FRAME_TOTALS:" + str(i))
        for domain in ("gate", "doa"):
            fixed = detail["detail"]["fixed4"][domain]
            require(fixed["domain"] == domain and fixed["frame_identity"]["frame"] == i
                    and fixed["overflow_components_by_channel"] == [[0, 0]] * 4
                    and fixed["invalid_complex_by_channel"] == [0] * 4
                    and fixed["invalid_locations"] == [],
                    "FIXED4_NORMAL_SUMMARY:" + str(i) + ":" + domain)
        for pair in ("01", "02", "03", "12", "13", "23"):
            if not opened:
                require(all(units[f"{kind}_{pair}"] == "SKIPPED_GATE_CLOSED"
                            for kind in ("phat", "ifft", "lag")), "GATE_CLOSED_SKIP:" + str(i))
            else:
                require(units[f"phat_{pair}"] == "OK" and units[f"ifft_{pair}"] == "OK",
                        "ACTIVE_PAIR:" + str(i) + ":" + pair)
                ifft_success += 1
        doa = detail["detail"]["doa"]
        if opened:
            require(doa["valid"] and doa["reason"] == "VALID", "DOA_QUALIFICATION:" + str(i))
            require(abs(doa["azimuth_q8_deg"]) <= 8 * 256,
                    "SYNTHETIC_X_AXIS_ANGLE:" + str(i))
            require(detail["detail"]["cordic"] == "OK_NORMALIZED_S23", "CORDIC:" + str(i))
        else:
            require(not doa["valid"] and row["state"] == "SEARCH" and not row["fresh"],
                    "CLOSED_GATE_FRESH:" + str(i))
        if i == 2:
            require(row["state"] == "ACQUIRE" and not row["fresh"] and
                    row["control"]["state"] == "SEARCH", "ACQUIRE_MUST_NOT_FRESH")
        if i >= 3:
            require(row["state"] == "LOCKED" and row["fresh"] and
                    row["control"]["state"] == "LOCKED", "LOCKED_FRESH:" + str(i))
            fresh += 1
        require(row["control"]["emit"] == row["take"], "CONTROL_EMIT_TIME:" + str(i))
    require(ifft_success == 30 and fresh == 4, "POSITIVE_COVERAGE")
    events = result["events"]
    wanted_events = event_map(fixture, expected)
    require(isinstance(events, list), "EVENT_LOG_FORMAT")
    observed_events = {}
    for index, event in enumerate(events):
        require(isinstance(event, dict) and set(event) ==
                {"frame", "unit", "visible_at", "result"},
                "EVENT_ROW_FORMAT:" + str(index))
        frame, unit = event["frame"], event["unit"]
        require(type(frame) is int and isinstance(unit, str),
                "EVENT_IDENTITY_FORMAT:" + str(index))
        key = (frame, unit)
        require(key in wanted_events, f"EVENT_EXTRA:{frame}:{unit}")
        observed_events.setdefault(key, []).append(event)
    for (frame, unit), (visible_at, status) in wanted_events.items():
        matches = observed_events.get((frame, unit), [])
        require(matches, f"EVENT_KEY_MISSING:{frame}:{unit}")
        require(len(matches) == 1, f"EVENT_DUPLICATE:{frame}:{unit}:count={len(matches)}")
        event = matches[0]
        require(type(event["visible_at"]) is int and event["visible_at"] == visible_at,
                f"EVENT_TIME:{frame}:{unit}:expected={visible_at}:observed={event['visible_at']}")
        require(event["result"] == status,
                f"EVENT_RESULT:{frame}:{unit}:expected={status}:observed={event['result']}")
    pcm = np.load(repo["pcm_path"], allow_pickle=False)
    count = pcm.shape[1]
    audio = result["audio"]
    require(audio["source_count"] == count and audio["aborted_at_emit"] is None,
            "AUDIO_SOURCE_COUNT")
    for lane in ("single", "manual", "automatic"):
        require(arrays["audio_" + lane].shape == (count,), "AUDIO_LENGTH:" + lane)
    require(arrays["audio_automatic_raw"].shape == (count + 8,), "RAW_EMIT_LENGTH")
    first_fresh_emit = result["frames"][3]["take"]
    first_affected_source = first_fresh_emit - 8
    first_array_difference(arrays["audio_single"], pcm[0], "audio_single_source_coordinate")
    first_array_difference(arrays["audio_automatic_raw"][8:8 + count],
                           arrays["audio_automatic"], "audio_emit_plus_8")
    first_array_difference(arrays["audio_automatic"][:first_affected_source],
                           pcm[0, :first_affected_source], "audio_before_first_fresh")
    rom_path = repo["root"] / repo["delay_path"]
    require(hashlib.sha256(rom_path.read_bytes()).hexdigest() == repo["delay_sha"],
            "DELAY_ROM_IDENTITY")
    rom = np.load(rom_path, allow_pickle=False)
    first_array_difference(arrays["audio_manual"], manual_reference(pcm, rom, manual_angle_q8),
                           "manual_fixed_angle_q12")
    require(audio["stats"]["max_beams"] <= 2 and audio["stats"]["max_history"] <= 17,
            "DYNAMIC_RESOURCE_BOUND")
    return {"compared_arrays": len(checked), "frames": 7, "fresh": fresh,
            "conditional_ifft": ifft_success, "first_fresh_emit": first_fresh_emit,
            "audio_sources": count}


def compare_directions(result, reference_summary):
    rows = reference_summary["active_direction_checks"]
    require(len(rows) == 5, "DIRECTION_REFERENCE_COVERAGE")
    for frame_text, expected in rows.items():
        frame = int(frame_text)
        observed = result["stage_details"][frame]["detail"]
        for pair, wanted in enumerate(expected["lags"]):
            require(observed["pair_rows"][pair] == wanted,
                    f"LAG_FIRST_DIFFERENCE:{frame}:{pair}")
        for key, wanted in expected["direction"].items():
            require(observed["doa"].get(key) == wanted,
                    f"DIRECTION_FIRST_DIFFERENCE:{frame}:{key}:expected={wanted}:observed={observed['doa'].get(key)}")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--manual-angle-q8", type=int, required=True)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    require(not a.out.exists(), "OUTPUT_EXISTS")
    schedule = strict_json(a.fixture / "schedule.json")
    manifest = json.loads((a.repo / "models/python/soundsight_h3_portable/tables/source-manifest.json").read_text())
    drom = manifest["entries"]["delay_rom"]
    context = {"root": a.repo, "pcm_path": a.fixture / "pcm.npy",
               "delay_path": drom["path"], "delay_sha": drom["sha256"]}
    result = strict_json(a.result / "result.json")
    with np.load(a.result / "stages-and-audio.npz", allow_pickle=False) as source:
        arrays = {name: source[name].copy() for name in source.files}
    with np.load(a.reference / "expected-stages.npz", allow_pickle=False) as source:
        expected = {name: source[name].copy() for name in source.files}
    reference_summary = json.loads((a.reference / "reference-summary.json").read_text())
    class ArrayView:
        files = list(expected)
        def __getitem__(self, key):
            return expected[key]
    summary = compare(result, arrays, ArrayView(), schedule, context, a.manual_angle_q8)
    summary["independent_direction_frames"] = compare_directions(result, reference_summary)
    negatives = {}
    if a.self_test:
        experiments = ("NUMERIC", "FRESH", "EVENT", "AUDIO", "PHAT", "IFFT", "DIRECTION")
        for kind in experiments:
            result_copy = copy.deepcopy(result)
            array_copy = dict(arrays)
            if kind == "NUMERIC":
                array_copy["frame0000_doa_fft29"] = arrays["frame0000_doa_fft29"].copy()
                array_copy["frame0000_doa_fft29"][0, 7, 0] += 1
            elif kind == "FRESH":
                result_copy["frames"][2]["fresh"] = True
            elif kind == "EVENT":
                result_copy["events"] = [row for row in result_copy["events"]
                                         if not (row["frame"] == 3 and row["unit"] == "take")]
            elif kind == "PHAT":
                array_copy["frame0002_phat_s25"] = arrays["frame0002_phat_s25"].copy()
                array_copy["frame0002_phat_s25"][0, 7, 0] += 1
            elif kind == "IFFT":
                array_copy["frame0002_ifft_real"] = arrays["frame0002_ifft_real"].copy()
                array_copy["frame0002_ifft_real"][0, 0] += 1
            elif kind == "DIRECTION":
                result_copy["stage_details"][2]["detail"]["doa"]["azimuth_q8_deg"] += 1
            else:
                array_copy["audio_automatic"] = arrays["audio_automatic"].copy()
                array_copy["audio_automatic"][0] += 1
            try:
                compare(result_copy, array_copy, ArrayView(), schedule, context,
                        a.manual_angle_q8)
                compare_directions(result_copy, reference_summary)
            except CheckFailure as error:
                negatives[kind] = str(error)
            else:
                raise CheckFailure("NEGATIVE_CANARY_NOT_DETECTED:" + kind)
    a.out.mkdir()
    output = {"status": "CHECKER_PASS_SCOPE_ONLY", "positive": summary,
              "negative_canaries": negatives,
              "reference_is_independent_of_dut_import": True,
              "not_claimed": ["SNR", "real activity truth", "RTL timing", "production profile"]}
    (a.out / "checker-result.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except (CheckFailure, AssertionError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
