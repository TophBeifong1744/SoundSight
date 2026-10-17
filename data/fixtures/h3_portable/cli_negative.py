"""Run short CLI input-rejection probes without touching product inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir()
    original = json.loads((a.fixture / "config.json").read_text())
    variants = {}
    wrong = json.loads(json.dumps(original))
    wrong["source_manifest_sha256"] = "0" * 64
    variants["wrong_identity"] = (wrong, "SOURCE_MANIFEST_CONFIG_MISMATCH")
    missing = json.loads(json.dumps(original))
    del missing["tracker"]["acquire_frames"]
    variants["missing_config"] = (missing, "CONFIG_INCOMPLETE")
    invalid = json.loads(json.dumps(original))
    invalid["activity"]["attack_frames"] = True
    variants["bool_integer"] = (invalid, "CONFIG_INCOMPLETE_OR_INVALID")
    records = []
    for name, (config, reason) in variants.items():
        path = a.out / (name + ".json")
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        command = [a.python, "-B", "-m", "soundsight_h3_portable",
                   "--repo", str(a.repo), "--config", str(path),
                   "--pcm", str(a.fixture / "pcm.npy"),
                   "--out", str(a.out / (name + "-should-not-exist"))]
        process = subprocess.run(command, cwd=a.repo / "models/python",
                                 capture_output=True)
        (a.out / (name + ".stdout.log")).write_bytes(process.stdout)
        (a.out / (name + ".stderr.log")).write_bytes(process.stderr)
        ok = process.returncode != 0 and reason.encode() in process.stderr and not (a.out / (name + "-should-not-exist")).exists()
        records.append({"name": name, "command": command, "exit_code": process.returncode,
                        "expected_reason": reason, "target_rejection": ok,
                        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
                        "config_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (a.out / "result.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(records))
    return 0 if all(item["target_rejection"] for item in records) else 1


if __name__ == "__main__":
    sys.exit(main())
