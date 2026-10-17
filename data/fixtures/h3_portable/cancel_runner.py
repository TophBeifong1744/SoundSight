"""Run bounded cancellation scenarios and the independent checker.

All outputs are new. The original A fixture and the product tree are read only.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


SOURCE_HASHES = {
    "config.json": "30364604da6c94c1f90f79ef74eeb1a4d2f2348875e6ea7ee1853b497043e692",
    "schedule.json": "f8e463dea12f5de3ddac2e5f6dc9b01e07b641ab0b04ac4925906f516726668a",
    "pcm.npy": "9df457fcc932b465f0708764cdb0a2369d2bb1a1f1cc45dd90b09010024590a0",
}
PRODUCT = "7e5506c411ee739881dc36ae4e315361180c1764"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_bytes(repo, path):
    return subprocess.run(["git", "-C", str(repo), "show", PRODUCT + ":" + path],
                          check=True, capture_output=True).stdout


def product_identity(repo):
    files = subprocess.run(["git", "-C", str(repo), "ls-files",
                            "models/python/soundsight_h3_portable"], check=True,
                           capture_output=True, text=True).stdout.splitlines()
    result = {}
    for name in files:
        raw = (repo / name).read_bytes()
        frozen = git_bytes(repo, name)
        if raw != frozen and not (name.endswith(".json") and raw.replace(b"\r\n", b"\n") == frozen):
            raise RuntimeError("PRODUCT_BYTES_CHANGED:" + name)
        result[name] = {"git_sha256": hashlib.sha256(frozen).hexdigest(),
                        "worktree_sha256": hashlib.sha256(raw).hexdigest(),
                        "same_raw_bytes": raw == frozen}
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(name, command, cwd, out, records):
    p = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True)
    (out / (name + ".stdout.log")).write_bytes(p.stdout)
    (out / (name + ".stderr.log")).write_bytes(p.stderr)
    records.append({"name": name, "argv": list(map(str, command)), "cwd": str(cwd),
                    "exit_code": p.returncode,
                    "stdout_sha256": sha(out / (name + ".stdout.log")),
                    "stderr_sha256": sha(out / (name + ".stderr.log"))})
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--source-fixture", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only-case", help="Run one declared case for an isolated runner canary")
    ap.add_argument("--inject-checker-failure", action="store_true",
                    help="Isolated canary: corrupt a saved result before the checker")
    a = ap.parse_args()
    repo, source, out = a.repo.resolve(strict=True), a.source_fixture.resolve(strict=True), a.out
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    here = Path(__file__).resolve().parent
    python = a.python.resolve(strict=True)
    before = product_identity(repo)
    for name, digest in SOURCE_HASHES.items():
        if sha(source / name) != digest:
            raise RuntimeError("R_SAVED_FIXTURE_HASH:" + name)
    config = json.loads((source / "config.json").read_text(encoding="utf-8"))
    rebound = {}
    for key, file in (("source_manifest_sha256", "source-manifest.json"),
                      ("table_manifest_sha256", "table-manifest.json")):
        path = repo / "models/python/soundsight_h3_portable/tables" / file
        rebound[key] = {"from": config[key], "to": sha(path), "path": str(path)}
        config[key] = rebound[key]["to"]
    original_schedule = json.loads((source / "schedule.json").read_text(encoding="utf-8"))
    pcm = np.load(source / "pcm.npy", allow_pickle=False)
    cases = {}
    for label, edge in (("fatal2559",2559),("fatal2560",2560),("fatal2561",2561),
                        ("fatal2562",2562),("fatal2563",2563)):
        cases[label] = (4, {"fatal_emit": edge})
    cases.update({"normal": (4, {}), "stop2561": (4, {"stop_emit": 2561}),
                  "stop2563": (4, {"stop_emit": 2563}),
                  "tie2561": (4, {"fatal_emit": 2561, "stop_emit": 2561}),
                  "early_external": (4, {"fatal_emit": 2560, "early_external": True}),
                  "pre_error": (4, {"fatal_emit": 2560, "early_external": True,
                                     "external_error": True}),
                  "overlap": (5, {"fatal_emit": 3073, "overlap": True})})
    if a.only_case:
        if a.only_case not in cases:
            raise ValueError("UNKNOWN_CASE:" + a.only_case)
        cases = {a.only_case: cases[a.only_case]}
    if a.inject_checker_failure and len(cases) != 1:
        raise ValueError("INJECTION_REQUIRES_ONLY_CASE")
    records, cases_index = [], {}
    for label, (nframes, changes) in cases.items():
        directory = out / label
        directory.mkdir()
        schedule = copy.deepcopy(original_schedule)
        schedule["frames"] = schedule["frames"][:nframes]
        for key in ("fatal_emit", "stop_emit"):
            if key in changes:
                schedule[key] = changes[key]
        if changes.get("early_external"):
            schedule["frames"][3]["external_visible_at"]["transport"] = 2559
        if changes.get("external_error"):
            schedule["frames"][3]["external_error_units"] = ["transport"]
        if changes.get("overlap"):
            schedule["frames"][3]["take_now"] = 3073
            schedule["frames"][4]["available"] = 3073
            schedule["frames"][4]["commit_now"] = 3074
            schedule["frames"][4]["take_now"] = 3075
        write_json(directory / "config.json", config)
        write_json(directory / "schedule.json", schedule)
        np.save(directory / "pcm.npy", pcm[:, :2560 if nframes == 4 else 3072])
        cli = [python, "-B", "-m", "soundsight_h3_portable", "--repo", repo,
               "--config", directory / "config.json", "--pcm", directory / "pcm.npy",
               "--schedule", directory / "schedule.json", "--manual-angle-q8", "0",
               "--out", directory / "dut"]
        if run(label + ".cli", cli, repo / "models/python", out, records):
            break
        result_path = directory / "dut/result.json"
        if a.inject_checker_failure:
            corrupted = json.loads(result_path.read_text(encoding="utf-8"))
            corrupted["events"][0]["result"] = "INJECTED_WRONG_RESULT"
            result_path = directory / "mutated-result.json"
            write_json(result_path, corrupted)
        checker = [python, "-B", here / "cancel_checker.py", "--result", result_path,
                   "--schedule", directory / "schedule.json", "--reference", a.reference]
        if run(label + ".checker", checker, here, out, records):
            break
        cases_index[label] = {name: sha(directory / name) for name in
                              ("config.json", "schedule.json", "pcm.npy")}
    after = product_identity(repo)
    index = {"product_commit": PRODUCT, "product_before": before,
             "product_after_equal": before == after, "source_fixture": SOURCE_HASHES,
             "reference_sha256": sha(a.reference), "rebound": rebound,
             "cases": cases_index, "steps": records, "python": sys.version,
             "injected_checker_failure": a.inject_checker_failure,
             "numpy": np.__version__, "status": "PASS_CASES" if len(cases_index) == len(cases) else "FAIL_INCOMPLETE"}
    write_json(out / "run-index.json", index)
    print(json.dumps({"status": index["status"], "cases": list(cases_index)}))
    return 0 if index["status"] == "PASS_CASES" else 1


if __name__ == "__main__":
    sys.exit(main())
