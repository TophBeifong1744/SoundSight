"""验证仓库或解压后的两个 Skill；只运行离线测试及显式选定的 XSim。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="尚不存在的结果目录")
    parser.add_argument("--vivado-bin", type=Path, help="提供时执行六次隔离 XSim；不打开工程")
    args = parser.parse_args()
    root, output = args.skills_root.resolve(), args.output.resolve()
    if output.exists():
        parser.error("输出目录已存在，不覆盖证据")
    module = root / "fpga-module-verification"
    pynq = root / "pynq-overlay-dma-validation"
    if not module.is_dir() or not pynq.is_dir():
        parser.error("两个 Skill 目录必须齐全")
    output.mkdir(parents=True)
    summary = {"status": "RUNNING", "scope": "offline and optional isolated XSim only",
               "started_utc": datetime.now(timezone.utc).isoformat(), "checks": [],
               "board": "NOT_RUN", "synthesis_implementation": "NOT_RUN"}

    def save():
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def command(name, cwd, argv, expected=0):
        argv = [sys.executable, "-E", "-s", "-B", "-X", "utf8", *map(str, argv)]
        # XSim 的单阶段超时由原 runner 管理；这里不杀其他用户工程。
        result = subprocess.run(argv, cwd=cwd, capture_output=True)
        (output / (name + ".stdout.log")).write_bytes(result.stdout)
        (output / (name + ".stderr.log")).write_bytes(result.stderr)
        summary["checks"].append({"name": name, "argv": argv, "cwd": str(cwd),
                                  "exit_code": result.returncode, "expected_exit": expected})
        save()
        if result.returncode != expected:
            raise RuntimeError(name + ": unexpected exit; see retained logs")
        print(name + ": expected exit " + str(expected), flush=True)
        return result.stdout + result.stderr

    try:
        # 链接验证只看当前说明；历史原件允许保留旧地址但不成为运行依赖。
        for skill in (module, pynq):
            entry = skill / "SKILL.md"
            if not entry.exists():
                entry = skill / "skill.md"
            text = entry.read_text(encoding="utf-8-sig")
            if not text.startswith("---\n") or "\nname: " not in text or "\ndescription: " not in text:
                raise ValueError("Invalid Skill frontmatter: " + str(entry))
            for doc in skill.rglob("*.md"):
                if {"history", "evidence"} & set(doc.relative_to(skill).parts):
                    continue
                for ref in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8-sig")):
                    if "://" not in ref and not (doc.parent / ref.split("#")[0]).exists():
                        raise FileNotFoundError(str(doc) + " -> " + ref)

        log = command("module-units", module, ["-m", "unittest", "discover", "-s", "tests", "-v"])
        if not re.search(rb"Ran 7 tests", log) or b"\nOK" not in log.replace(b"\r", b""):
            raise RuntimeError("Module test count/final status not confirmed")
        command("pynq-units", pynq, ["scripts/run_offline_tests.py", "--output", output / "pynq-tests.json"])
        units = json.loads((output / "pynq-tests.json").read_text(encoding="utf-8"))
        if units["status"] != "PASS" or units["tests_run"] < 55 or any(units[k] for k in ("failures", "errors", "skipped")):
            raise RuntimeError("PYNQ regression incomplete")
        for name, faults, expected in [("receive", [], 0), ("timeout", ["timeout", "abort-timeout"], 1)]:
            argv = ["scripts/simulate_dma.py", "--contract", "references/example-session.json", "--output", output / (name + ".json")]
            for fault in faults:
                argv += ["--fault", fault]
            command(name, pynq, argv, expected)
            report = json.loads((output / (name + ".json")).read_text(encoding="utf-8"))
            if report["status"] != ("PASS" if expected == 0 else "FAIL"):
                raise RuntimeError("Unexpected mock report: " + name)
            if expected == 0:
                if report["actual_bytes"] != 96 or report["mismatch_count"] != 0 or report["buffer_disposition"] != "released":
                    raise RuntimeError("Receive did not compare and release the complete payload")
            elif report["buffer_disposition"] != "retained" or not report["session_blocked"] or any(
                    op in {"rx.read", "rx.release"} for op in report["adapter_trace"]):
                raise RuntimeError("Double timeout did not preserve ownership and block retry")
        # 此入口无硬件实现，验证其继续拒绝执行；不传下载参数。
        log = command("board-guard", pynq, ["scripts/pynq_probe.py", "--profile", "references/example-profile.json", "--output", output / "forbidden-board.json"], 1)
        if b"BOARD_RUNNER_NOT_QUALIFIED" not in log or (output / "forbidden-board.json").exists():
            raise RuntimeError("Board guard did not reject before output")
        if args.vivado_bin:
            command("xsim-examples", module, ["scripts/run_examples.py", "--vivado-bin", args.vivado_bin.resolve(), "--output", output / "xsim"])
            xsim = json.loads((output / "xsim/summary.json").read_text())
            if xsim["status"] != "PASS_DEMONSTRATION" or len(xsim["runs"]) != 6 or not all(r["matched"] for r in xsim["runs"]):
                raise RuntimeError("Incomplete XSim positive/negative demonstrations")
            summary["xsim"] = xsim["runs"]
        else:
            summary["xsim"] = "NOT_RUN"
        summary.update(status="PASS", module_unit_tests=7, pynq_tests=units["tests_run"], pynq_subtests=units["subtests_run"])
    except Exception as exc:
        summary.update(status="FAIL", error=str(exc))
    finally:
        summary["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        save()
    print(json.dumps({"status": summary["status"], "output": str(output), "error": summary.get("error")}, ensure_ascii=False))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
