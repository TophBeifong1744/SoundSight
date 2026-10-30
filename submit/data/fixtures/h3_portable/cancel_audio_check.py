"""Check saved CLI audio at STOP/fatal edges without importing product code."""

import argparse
import json
from pathlib import Path

import numpy as np


def load(root, case):
    path = root / case / "dut"
    result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    with np.load(path / "stages-and-audio.npz", allow_pickle=False) as source:
        arrays = {key: source[key] for key in source.files if key.startswith("audio_")}
    return result, arrays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    baseline, base = load(a.run, "normal")
    raw = base["audio_automatic_raw"]
    assert len(raw) == 2568 and baseline["audio"]["aborted_at_emit"] is None
    assert np.array_equal(raw[8:2568], base["audio_automatic"])
    checks = {}
    for case, edge in (("fatal2559",2559),("fatal2560",2560),
                       ("fatal2561",2561),("fatal2562",2562),("fatal2563",2563),
                       ("tie2561",2561)):
        result, arrays = load(a.run, case)
        observed = arrays["audio_automatic_raw"]
        assert result["status"] == "ABORTED" and result["audio"]["aborted_at_emit"] == edge
        assert len(observed) == edge and np.array_equal(observed, raw[:edge])
        assert len(arrays["audio_automatic"]) == edge - 8
        assert np.array_equal(observed[8:], arrays["audio_automatic"])
        assert np.array_equal(arrays["audio_single"], base["audio_single"][:edge-8])
        assert np.array_equal(arrays["audio_manual"], base["audio_manual"][:edge-8])
        assert not any(e["kind"] == "STOP" for e in result["audio"]["events"])
        checks[case] = {"edge": edge, "raw_emits": len(observed), "prefix_equal": True}
    for case, edge in (("stop2561",2561),("stop2563",2563)):
        result, arrays = load(a.run, case)
        observed = arrays["audio_automatic_raw"]
        assert result["status"] == "COMPLETED" and result["audio"]["aborted_at_emit"] is None
        assert len(observed) == 2568 and np.array_equal(observed[:edge], raw[:edge])
        assert np.array_equal(observed[8:2568], arrays["audio_automatic"])
        assert any(e["kind"] == "STOP" and e["emit"] == edge for e in result["audio"]["events"])
        assert result["audio"]["stats"]["max_beams"] <= 2
        assert result["audio"]["stats"]["max_history"] <= 17
        checks[case] = {"edge": edge, "raw_emits": len(observed),
                        "changed_samples_after_edge": int(np.count_nonzero(observed[edge:] != raw[edge:]))}
    a.out.mkdir()
    (a.out / "result.json").write_text(json.dumps({"status": "PASS_CANCEL_AUDIO_PREFIX",
        "checks": checks, "scope": "saved CLI audio, synthetic sample coordinates"}, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": "PASS_CANCEL_AUDIO_PREFIX", "cases": len(checks)}))


if __name__ == "__main__":
    main()
