"""Author replay of B D1/D2 inputs, required regressions and two data formats."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

REVIEW = "0ef0355642ea8719d5e4cdde0a38c531550218d4"
OLD = "55039cf8bfab2bd6112192c8bd646d427a52a642"
BROOT = "results/skill-review/b-20260914/skl002-independent/"
SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from dma_session import DmaSession, TransferSpec
from simulate_dma import MockDma, MockClock


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--validator-python", required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    summary = {"review_commit": REVIEW, "old_candidate": OLD,
               "scope": "AUTHOR_SELF_TEST_NOT_B_ACCEPTANCE", "checks": [], "inputs": [],
               "script_sha256": digest(__file__), "python": sys.version}

    def save():
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    def git(*argv):
        return subprocess.check_output(["git", "-c", f"safe.directory={REPO.as_posix()}", *argv], cwd=REPO)

    def copy_blob(commit, path, dest):
        raw = git("show", commit + ":" + path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        summary["inputs"].append({"commit": commit, "git_path": path,
                                  "copy": dest.relative_to(out).as_posix(), "sha256": digest(dest)})

    names = git("ls-tree", "-r", "--name-only", REVIEW, BROOT).decode().splitlines()
    for name in names:
        rel = name.removeprefix(BROOT)
        if rel.startswith(("thermal/", "pixel/")) or rel in ("thermal-session-input.json", "pixel-session-input.json"):
            copy_blob(REVIEW, name, out / "b-inputs" / rel)
    old_script = out / "old-input/validate_profile.py"
    copy_blob(OLD, "skill/pynq-overlay-dma-validation/scripts/validate_profile.py", old_script)

    def command(label, argv, expected, output_json=None, issue=None):
        dest = out / label
        dest.mkdir()
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run([str(x) for x in argv], cwd=SKILL, capture_output=True, timeout=180)
        (dest / "stdout.log").write_bytes(result.stdout)
        (dest / "stderr.log").write_bytes(result.stderr)
        info = {"argv": [str(x) for x in argv], "cwd": str(SKILL), "started_utc": started,
                "exit_code": result.returncode, "expected_exit": expected,
                "stdout_sha256": digest(dest / "stdout.log"), "stderr_sha256": digest(dest / "stderr.log")}
        ok = result.returncode == expected
        if output_json:
            report = json.loads(output_json.read_text(encoding="utf-8"))
            info.update(report_sha256=digest(output_json), status=report["status"])
            if issue:
                ok = ok and report["status"] == "FAIL" and issue in {i["code"] for i in report["issues"]}
        info["matched"] = ok
        (dest / "command.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        summary["checks"].append({"name": label, **info})
        save()
        print(label, "PASS_EXPECTATION" if ok else "FAIL", flush=True)
        if not ok:
            raise RuntimeError(label)

    thermal = out / "b-inputs/thermal"
    for label, profile, evidence, issue in (
        ("missing-dma", thermal / "missing-dma-ip.json", None, "HWH_CONTRACT_IP"),
        ("missing-control", thermal / "missing-control-ip.json", None, "HWH_CONTRACT_IP"),
        ("duplicate", thermal / "profile.json", thermal / "duplicate-evidence.json", "DMA_RUN_DUPLICATE"),
    ):
        for phase, script, expected in (("old", old_script, 0), ("fixed", SKILL / "scripts/validate_profile.py", 1)):
            report = out / f"{label}-{phase}.json"
            argv = [sys.executable, "-B", script, "--profile", profile, "--mode", "offline", "--output", report]
            if evidence:
                argv += ["--evidence", evidence]
            command(label + "-" + phase, argv, expected, report, issue if phase == "fixed" else None)

    for label, script_args, expected in (
        ("unit", ["scripts/run_offline_tests.py"], 0),
        ("receive", ["scripts/simulate_dma.py", "--contract", "references/example-session.json"], 0),
        ("timeout", ["scripts/simulate_dma.py", "--contract", "references/example-session.json", "--fault", "timeout", "--fault", "abort-timeout"], 1),
    ):
        report = out / (label + ".json")
        command(label, [sys.executable, "-B", *script_args, "--output", report], expected, report)
    timeout = json.loads((out / "timeout.json").read_text())
    assert timeout["buffer_disposition"] == "retained" and timeout["session_blocked"]
    assert not any(event in timeout["adapter_trace"] for event in ("rx.read", "rx.release"))

    for name in ("thermal", "pixel"):
        report = out / (name + "-static.json")
        command(name + "-static", [sys.executable, "-B", "scripts/validate_profile.py", "--profile",
                                  out / "b-inputs" / name / "profile.json", "--output", report], 0, report)
        data = json.loads((out / "b-inputs" / (name + "-session-input.json")).read_text())
        expected = b"".join(struct.pack(data["payload_format"], value) for value in data["values"])
        assert hashlib.sha256(expected).hexdigest() == data["golden_sha256"]
        assert expected == (out / "b-inputs" / name / "golden.bin").read_bytes()
        spec = TransferSpec(**data["transfer"])
        for fault_name, faults in (
            ("normal", set()), ("cache-stale", {"rx-invalidate-noop"}),
            ("partial-stop-fail", {"rx-arm-after", "abort-timeout"}),
            ("status-unreadable", {"status-read", "abort-timeout"}),
            ("timeout-stop-fail", {"timeout", "abort-timeout"}),
            ("short", {"short-output"}), ("release-fail", {"rx-release"}),
        ):
            dma = MockDma(mode="receive", capture=expected, alignment=spec.buffer_alignment_bytes, faults=faults)
            session = DmaSession(dma, clock=MockClock())
            observation = session.run(spec, expected=expected)
            assert observation["status"] == ("PASS" if not faults else "FAIL"), observation
            if fault_name in {"partial-stop-fail", "status-unreadable", "timeout-stop-fail"}:
                assert observation["buffer_disposition"] == "retained"
                assert "rx.read" not in dma.trace and "rx.release" not in dma.trace
            assert dma.trace.count("rx.release") <= 1
            if faults:
                before = list(dma.trace)
                blocked = session.run(spec, expected=expected)
                assert blocked["status"] == "FAIL" and dma.trace == before
                observation["next_run"] = blocked
            observation.update(adapter_trace=dma.trace, payload_format=data["payload_format"],
                               golden_sha256=data["golden_sha256"], timing_source="synthetic mock clock; not hardware throughput")
            target = out / f"{name}-{fault_name}.json"
            target.write_text(json.dumps(observation, indent=2) + "\n", encoding="utf-8")
            summary["checks"].append({"name": name + "-" + fault_name, "matched": True, "report_sha256": digest(target)})
            save()
    command("structure", [args.validator_python, "-X", "utf8", args.validator, SKILL], 0)
    command("board-guard", [sys.executable, "-B", "scripts/pynq_probe.py", "--download"], 2)
    summary["status"] = "PASS_AUTHOR_REGRESSION"
    save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
