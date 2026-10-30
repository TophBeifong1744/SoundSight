"""Predeclare an independent synthetic H3 input; never import the DUT.

The broad-band source is a deterministic xorshift32 sequence. Four microphone
channels are delayed copies on the candidate 40 mm square. This is synthetic
geometry for software testing, not a measured array or production reference.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_codes(length):
    word = 0xA57C91E3
    values = []
    for _ in range(length):
        word ^= (word << 13) & 0xffffffff
        word ^= word >> 17
        word ^= (word << 5) & 0xffffffff
        values.append((((word >> 8) & 0xffff) - 32768) * 32)
    return np.asarray(values, dtype=np.int64)


def external_names(active):
    base = ["transport", "frame_domain", "binding"]
    base.extend(f"{domain}_{node}_{ch}" for domain in ("gate", "doa")
                for node in ("fft", "fixed4") for ch in range(4))
    if active:
        base.extend(f"ifft_{pair}" for pair in ("01", "02", "03", "12", "13", "23"))
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    package = a.repo / "models/python/soundsight_h3_portable"
    src = source_codes(4096 + 20)
    # 6-sample inter-column offset, two equal rows. The sequence is distinct
    # from the product author's LCG/tiled scene and was fixed before the run.
    pcm = np.stack((src[8:4104], src[14:4110],
                    src[14:4110], src[8:4104])).astype(np.int64)
    np.save(a.out / "pcm.npy", pcm)
    config = {
        "scope": "RESEARCH_ONLY",
        "profile_id": "soundsight-fixed4-dual-domain-research-v1",
        "source_manifest_sha256": sha(package / "tables/source-manifest.json"),
        "table_manifest_sha256": sha(package / "tables/table-manifest.json"),
        "sample_rate_hz": 48000, "frame_length": 1024, "hop": 512,
        "backend": "portable_q30_frozen",
        "geometry": {"positions_mm": [[0, 0], [40, 0], [40, 40], [0, 40]],
                     "sound_speed_m_s": 343,
                     "correction_policy": "UNAPPLIED_CANDIDATE",
                     "basis": "CANDIDATE_NOT_MEASURED"},
        "activity": {"on_power_ratio": 4, "off_power_ratio": 2,
                     "attack_frames": 3, "release_frames": 3,
                     "minimum_active_channels": 3,
                     "noise_power_u64": [1, 1, 1, 1],
                     "band_rms_floor_codes": 1,
                     "reference_sha256": hashlib.sha256(
                         b"h3-independent-synthetic-unit-noise-v1").hexdigest(),
                     "initial_state": "INACTIVE",
                     "invalid_policy": "RESET_ACTIVITY_AND_TRACKER"},
        "tracker": {"half_angle_q8": 30 << 8, "acquire_frames": 2,
                    "acquire_spread_q8": 8 << 8, "track_step_q8": 20 << 8,
                    "hold_samples": 9600, "max_gap_samples": 1440,
                    "time_domain": "SESSION_SAMPLE"},
        "audio_fade_samples": 480,
    }
    schedule = {"time_basis": "SYNTHETIC_TIME",
                "boot_id": "b-review-synthetic-boot",
                "session_id": "b-review-synthetic-session",
                "interval_id": "b-review-synthetic-interval",
                "generation": 11, "first_sample_id": 0,
                "result_ttl_samples": 1000, "frames": []}
    for i in range(7):
        last = 1023 + 512 * i
        available = last + 1
        schedule["frames"].append({
            "frame_index": i,
            "external_visible_at": {name: available for name in external_names(i >= 2)},
            "external_error_units": [], "available": available,
            "commit_now": available + 1, "take_now": available + 2,
            "audio_valid_through_emit": available + 1024,
        })
    (a.out / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (a.out / "schedule.json").write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
    identity = {"scene": "xorshift32 broadband, 6-sample inter-column offset, synthetic",
                "expected_first_active_frame": 2, "planned_frames": 7,
                "expected_forward_instances": 56,
                "expected_conditional_ifft_instances": 30,
                "research_only": True,
                "inputs_sha256": {name: sha(a.out / name) for name in
                                  ("pcm.npy", "config.json", "schedule.json")}}
    (a.out / "fixture-identity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(identity, sort_keys=True))


if __name__ == "__main__":
    main()
