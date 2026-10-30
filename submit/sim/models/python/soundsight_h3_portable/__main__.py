"""CLI for exact-byte bound, research-only numeric or synthetic-time intervals."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

import numpy as np

from .bindings import Bindings, HERE, digest
from .chain import ActivityState, run_causal_interval, run_numeric_frame
from .contracts import validate_config


def _json(value):
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _read_json(path):
    return json.loads(path.read_bytes())


def _local_code():
    names = ("__init__.py", "__main__.py", "bindings.py", "contracts.py",
             "fft_table.py", "fixed4.py", "chain.py", "audio.py")
    return {name: digest(HERE / name) for name in names}


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        "Bound portable H3 research candidate. Requires explicit research config; "
        "a schedule must declare SYNTHETIC_TIME. No H3 acceptance claim."))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pcm", type=Path, required=True,
                        help="NumPy .npy, shape [4,T], signed24 integer codes")
    parser.add_argument("--schedule", type=Path,
                        help="Explicit absolute SESSION_SAMPLE synthetic event schedule")
    parser.add_argument("--manual-angle-q8", type=int,
                        help="Required with --schedule; independent external manual angle")
    parser.add_argument("--out", type=Path, required=True, help="New directory; overwrite refused")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("OUTPUT_EXISTS")
    if (args.schedule is None) != (args.manual_angle_q8 is None):
        parser.error("SCHEDULE_AND_MANUAL_ANGLE_REQUIRED_TOGETHER")
    local_before = _local_code()
    inputs_before = {"config": digest(args.config), "pcm": digest(args.pcm)}
    if args.schedule:
        inputs_before["schedule"] = digest(args.schedule)
    bindings = Bindings(args.repo)
    config = validate_config(_read_json(args.config), bindings)
    pcm = np.load(args.pcm, allow_pickle=False)
    if (pcm.ndim != 2 or pcm.shape[0] != 4 or not np.issubdtype(pcm.dtype, np.integer)
            or np.any(pcm < -(1 << 23)) or np.any(pcm >= (1 << 23))):
        raise ValueError("FOUR_CHANNEL_SIGNED24_PCM_REQUIRED")
    if args.schedule:
        result = run_causal_interval(pcm, config, _read_json(args.schedule),
                                     args.manual_angle_q8, bindings)
        stages = result.pop("stages")
        audio = result.pop("audio")
        audio_arrays = {key: audio.pop(key) for key in
                        ("single", "manual", "automatic", "automatic_raw")}
        result["audio"] = audio
    else:
        activity = ActivityState(config["activity"])
        count = max(0, (pcm.shape[1] - 1024) // 512 + 1)
        stages = []
        for index in range(count):
            frame = pcm[:, index * 512:index * 512 + 1024].T
            identity = {"boot": "NUMERIC_ONLY_UNBOUND", "session": "numeric-only", "interval": "unbound",
                        "frame": index, "generation": 0, "last_id": None}
            stages.append(run_numeric_frame(frame, identity, activity, bindings))
        result = {"claim": "PORTABLE_RESEARCH_CONFIG_ONLY",
                  "time_basis": "NUMERIC_ONLY_TIME_UNBOUND", "planned_frames": count,
                  "fresh": "NOT_AVAILABLE", "automatic_control": "NOT_RUN"}
        audio_arrays = {}
    bindings.verify_post()
    if _local_code() != local_before:
        raise RuntimeError("COMPOSER_CODE_CHANGED_DURING_RUN")
    after = {"config": digest(args.config), "pcm": digest(args.pcm)}
    if args.schedule:
        after["schedule"] = digest(args.schedule)
    if after != inputs_before:
        raise RuntimeError("INPUT_CHANGED_DURING_RUN")
    output = args.out
    output.mkdir(parents=True, exist_ok=False)
    try:
        arrays = {}
        for index, stage in enumerate(stages):
            for name, array in stage["arrays"].items():
                arrays[f"frame{index:04d}_{name}"] = array
        arrays.update({"audio_" + key: value for key, value in audio_arrays.items()})
        np.savez_compressed(output / "stages-and-audio.npz", **arrays)
        result["stage_details"] = [{"detail": stage["detail"], "units": stage["units"],
                                     "expected": stage["expected"]} for stage in stages]
        (output / "result.json").write_text(json.dumps(_json(result), indent=2), encoding="utf-8")
        index = {"claim": "DIAGNOSTIC_SMOKE_NOT_ACCEPTANCE",
                 "argv": sys.argv if argv is None else argv,
                 "inputs_sha256": inputs_before, "source_identity": bindings.identity,
                 "composer_sha256": local_before,
                 "outputs_sha256": {name: digest(output / name) for name in
                                    ("result.json", "stages-and-audio.npz")}}
        (output / "run-index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    except BaseException:
        (output / "FAILED.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
