"""Independent Q12 mix for spaced synthetic turn and return controls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from independent_reference import rne
from checker import manual_reference


def first_difference(actual, expected, name):
    if actual.shape != expected.shape:
        raise AssertionError(f"{name}:SHAPE:{actual.shape}:{expected.shape}")
    mismatch = np.flatnonzero(actual != expected)
    if len(mismatch):
        i = int(mismatch[0])
        raise AssertionError(f"{name}:FIRST_DIFFERENCE:{i}:expected={expected[i]}:observed={actual[i]}")


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
    from soundsight_h3_portable.audio import render_three_lanes

    source = np.load(a.fixture / "pcm.npy", allow_pickle=False)
    pcm = np.concatenate((source, source[:, :1904]), axis=1)  # 6000 source samples
    manifest = json.loads((a.repo / "models/python/soundsight_h3_portable/tables/source-manifest.json").read_text())
    row = manifest["entries"]["delay_rom"]
    rom_path = a.repo / row["path"]
    assert hashlib.sha256(rom_path.read_bytes()).hexdigest() == row["sha256"]
    rom = np.load(rom_path, allow_pickle=False)
    angle_a, angle_b = 0, 19 * 256
    delays_a = [0] + list(map(int, rom[angle_a + 46080]))
    delays_b = [0] + list(map(int, rom[angle_b + 46080]))
    controls = [
        {"emit": 2000, "state": "LOCKED", "delays": delays_a, "valid_through": 3500},
        {"emit": 3000, "state": "LOCKED", "delays": delays_b, "valid_through": 5000},
        {"emit": 4000, "state": "SEARCH"},
    ]
    result = render_three_lanes(pcm, angle_a, controls, Bindings(a.repo))
    mono = pcm[0]
    beam_a = manual_reference(pcm, rom, angle_a)
    beam_b = manual_reference(pcm, rom, angle_b)
    expected = np.empty(pcm.shape[1] + 8, dtype=np.int64)
    for emit in range(len(expected)):
        n = emit - 8
        m = int(mono[n]) if n >= 0 else 0
        b0 = int(beam_a[n]) if n >= 0 else 0
        b1 = int(beam_b[n]) if n >= 0 else 0
        if emit < 2000:
            value = m
        elif emit < 2480:
            alpha = min(4096, rne((emit - 2000) * 4096, 480))
            value = rne(m * (4096 - alpha) + b0 * alpha, 4096)
        elif emit < 3000:
            value = b0
        elif emit < 3480:
            alpha = min(4096, rne((emit - 3000) * 4096, 480))
            value = rne(b0 * (4096 - alpha) + b1 * alpha, 4096)
        elif emit < 4000:
            value = b1
        elif emit < 4480:
            alpha = min(4096, rne((emit - 4000) * 4096, 480))
            value = rne(b1 * (4096 - alpha) + m * alpha, 4096)
        else:
            value = m
        expected[emit] = value
    first_difference(result["automatic_raw"], expected, "AUTOMATIC_Q12_TURN_RETURN")
    first_difference(result["automatic"], expected[8:6008], "AUTO_SOURCE_PLUS_8")
    first_difference(result["single"], mono, "MONO")
    first_difference(result["manual"], beam_a, "MANUAL_INDEPENDENT_OF_AUTO")
    assert [e["emit"] for e in result["events"] if e["kind"] == "FADE_START"] == [2000, 3000, 4000]
    assert result["stats"]["max_beams"] <= 2 and result["stats"]["max_history"] <= 17
    assert result["aborted_at_emit"] is None and result["source_count"] == 6000
    # No public portable streaming API is claimed. This compositor reads one
    # physical source sample at a time, so its 4096 join cannot insert zeros.
    assert result["automatic_raw"][4104] == expected[4104]
    # A return requested during the A->B fade is queued until the 480-sample
    # fade completes. The second 480-sample fade must finish within 960 total.
    overlap_controls = controls[:2] + [{"emit": 3200, "state": "SEARCH"}]
    overlap = render_three_lanes(pcm, angle_a, overlap_controls, Bindings(a.repo))
    overlap_expected = np.empty_like(expected)
    for emit in range(len(overlap_expected)):
        n = emit - 8
        m = int(mono[n]) if n >= 0 else 0
        b0 = int(beam_a[n]) if n >= 0 else 0
        b1 = int(beam_b[n]) if n >= 0 else 0
        if emit < 2000:
            value = m
        elif emit < 2480:
            alpha = min(4096, rne((emit - 2000) * 4096, 480))
            value = rne(m * (4096 - alpha) + b0 * alpha, 4096)
        elif emit < 3000:
            value = b0
        elif emit < 3480:
            alpha = min(4096, rne((emit - 3000) * 4096, 480))
            value = rne(b0 * (4096 - alpha) + b1 * alpha, 4096)
        elif emit < 3960:
            alpha = min(4096, rne((emit - 3480) * 4096, 480))
            value = rne(b1 * (4096 - alpha) + m * alpha, 4096)
        else:
            value = m
        overlap_expected[emit] = value
    first_difference(overlap["automatic_raw"], overlap_expected, "SERIALIZED_RETURN_Q12")
    assert [e["emit"] for e in overlap["events"] if e["kind"] == "FADE_START"] == [2000, 3000, 3480]
    assert overlap["stats"]["max_beams"] <= 2 and overlap["stats"]["max_history"] <= 17
    packet = {"status": "PASS_SPACED_Q12_TURN_RETURN", "controls": controls,
              "source_samples": 6000, "raw_emits": 6008, "fade_samples": 480,
              "return_to_mono_by": 4480, "return_after_request_samples": 480,
              "manual_angle_q8": angle_a, "auto_turn_angle_q8": angle_b,
              "source_join": 4096, "max_history": result["stats"]["max_history"],
              "max_beams": result["stats"]["max_beams"],
              "overlap_fallback_request": 3200, "overlap_return_to_mono_by": 3960,
              "overlap_fallback_samples": 760,
              "pcm_sha256": hashlib.sha256(pcm.astype("<i8").tobytes()).hexdigest(),
              "scope": "test-side declared controls; not a second legal PCM DOA scenario or public streaming API"}
    (a.out / "result.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "emits": packet["raw_emits"]}))


if __name__ == "__main__":
    main()
