"""Reproduce bounded independent portable-H3 checks with real exit propagation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--fixed-input-index", type=Path, required=True,
                    help="The frozen 21-object ASSEMBLY-PLAN INPUTS.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--inject-failure-step", choices=("reference",),
                    help="Isolated runner canary: run a child that fails before DUT execution")
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    here = Path(__file__).resolve().parent
    python = str(a.python.resolve(strict=True))
    repo = a.repo.resolve(strict=True)
    steps = []

    def run(name, argv, *, cli=False):
        process = subprocess.run(argv, cwd=repo / "models/python" if cli else here,
                                 capture_output=True)
        (a.out / (name + ".stdout.log")).write_bytes(process.stdout)
        (a.out / (name + ".stderr.log")).write_bytes(process.stderr)
        record = {"name": name, "argv": list(map(str, argv)), "cwd": str(repo / "models/python" if cli else here),
                  "exit_code": process.returncode,
                  "stdout_sha256": digest(a.out / (name + ".stdout.log")),
                  "stderr_sha256": digest(a.out / (name + ".stderr.log"))}
        steps.append(record)
        return process.returncode

    base = [python, "-B"]
    fixture = a.out / "fixture"
    reference = a.out / "reference"
    numeric = a.out / "numeric"
    causal = a.out / "causal"
    checked = a.out / "checked"
    negatives = a.out / "cli-negatives"
    boundary = a.out / "boundary"
    injection = a.out / "injection"
    events = a.out / "events"
    audio = a.out / "audio"
    jobs = [
        ("fixture", base + [str(here / "make_fixture.py"), "--repo", str(repo), "--out", str(fixture)], False),
        ("reference", base + [str(here / "independent_reference.py"), "--repo", str(repo),
                              "--fixture", str(fixture), "--out", str(reference)], False),
        ("numeric", base + ["-m", "soundsight_h3_portable", "--repo", str(repo),
                            "--config", str(fixture / "config.json"), "--pcm", str(fixture / "pcm.npy"),
                            "--out", str(numeric)], True),
        ("causal", base + ["-m", "soundsight_h3_portable", "--repo", str(repo),
                           "--config", str(fixture / "config.json"), "--pcm", str(fixture / "pcm.npy"),
                           "--schedule", str(fixture / "schedule.json"), "--manual-angle-q8", "0",
                           "--out", str(causal)], True),
        ("checker", base + [str(here / "checker.py"), "--repo", str(repo),
                            "--fixture", str(fixture), "--reference", str(reference),
                            "--result", str(causal), "--manual-angle-q8", "0", "--self-test",
                            "--out", str(checked)], False),
        ("cli-negatives", base + [str(here / "cli_negative.py"), "--python", python,
                                  "--repo", str(repo), "--fixture", str(fixture),
                                  "--out", str(negatives)], False),
        ("boundary", base + [str(here / "boundary_probe.py"), "--repo", str(repo),
                              "--out", str(boundary)], False),
        ("injection", base + [str(here / "chain_injection_probe.py"), "--repo", str(repo),
                               "--fixture", str(fixture), "--out", str(injection)], False),
        ("events", base + [str(here / "event_probe.py"), "--repo", str(repo),
                            "--fixture", str(fixture), "--out", str(events)], False),
        ("audio", base + [str(here / "audio_probe.py"), "--repo", str(repo),
                           "--fixture", str(fixture), "--out", str(audio)], False),
    ]
    for name, argv, cli in jobs:
        if name == a.inject_failure_step:
            argv = base + ["-c", "raise RuntimeError('CONTROLLED_CHILD_FAILURE')"]
        code = run(name, argv, cli=cli)
        if code != 0:
            break
    completed = [row["name"] for row in steps]
    unexpected = [row for row in steps if row["exit_code"]]
    product_paths = subprocess.run(["git", "-C", str(repo), "ls-files", "models/python/soundsight_h3_portable"],
                                   capture_output=True, text=True, check=True).stdout.splitlines()
    product_commit = "7e5506c411ee739881dc36ae4e315361180c1764"
    product_files = {}
    for path in product_paths:
        worktree_bytes = (repo / path).read_bytes()
        git_bytes = subprocess.run(["git", "-C", str(repo), "show", product_commit + ":" + path],
                                   capture_output=True, check=True).stdout
        same = worktree_bytes == git_bytes
        crlf_only = not same and worktree_bytes.replace(b"\r\n", b"\n") == git_bytes
        if crlf_only and not path.endswith(".json"):
            raise RuntimeError("PRODUCT_CODE_WORKTREE_GIT_BYTES_MISMATCH: " + path)
        if not (same or crlf_only):
            raise RuntimeError("PRODUCT_WORKTREE_GIT_BYTES_MISMATCH: " + path)
        product_files[path] = {
            "worktree_sha256": hashlib.sha256(worktree_bytes).hexdigest(),
            "git_blob_sha256": hashlib.sha256(git_bytes).hexdigest(),
            "same_raw_bytes": same, "crlf_checkout_only": crlf_only,
        }
    require_index = a.fixed_input_index.resolve(strict=True)
    if digest(require_index) != "7ffc495f26a778a312e93dd2199d65ee4d2c050d6dc609393f6c4af83d862db0":
        raise RuntimeError("FIXED_21_OBJECT_INDEX_MISMATCH")
    source_manifest = json.loads((repo / "models/python/soundsight_h3_portable/tables/source-manifest.json").read_text())
    source_files = {}
    for role, row in source_manifest["entries"].items():
        observed = digest(repo / row["path"])
        if observed != row["sha256"]:
            raise RuntimeError("SOURCE_BINDING_MISMATCH: " + role)
        source_files[role] = observed
    cli_identity_checks = {}
    for name in ("numeric", "causal"):
        if name not in completed or next(row for row in steps if row["name"] == name)["exit_code"]:
            continue
        run_index = json.loads((a.out / name / "run-index.json").read_text())
        for local_name, observed_sha in run_index["composer_sha256"].items():
            product_path = "models/python/soundsight_h3_portable/" + local_name
            if product_files[product_path]["worktree_sha256"] != observed_sha:
                raise RuntimeError("CLI_EXECUTED_DIFFERENT_PRODUCT_BYTES:" + name + ":" + local_name)
        if run_index["source_identity"]["source_files"] != source_files:
            raise RuntimeError("CLI_SOURCE_BINDING_MISMATCH:" + name)
        cli_identity_checks[name] = {"composer_modules": len(run_index["composer_sha256"]),
                                     "fixed4_sha256": run_index["composer_sha256"]["fixed4.py"]}
    identity = {"product_commit": product_commit, "python": sys.version,
                "numpy": np.__version__, "product_files": product_files,
                "fixed_21_object_index_sha256": digest(require_index),
                "source_binding_sha256": source_files, "cli_execution_identity": cli_identity_checks,
                "asset_sha256": {path.name: digest(path) for path in here.iterdir() if path.is_file()}}
    packet = {"status": "PASS_SCOPED" if len(steps) == len(jobs) and not unexpected else "FAIL_INCOMPLETE",
              "steps": steps, "completed": completed, "identity": identity,
              "controlled_failure_step": a.inject_failure_step,
              "not_measured": ["real clock", "RTL", "AMD", "production", "recorded acoustics", "SNR"]}
    (a.out / "evidence-index.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "completed": completed,
                      "index_sha256": digest(a.out / "evidence-index.json")}))
    return 0 if packet["status"] == "PASS_SCOPED" else 1


if __name__ == "__main__":
    sys.exit(main())
