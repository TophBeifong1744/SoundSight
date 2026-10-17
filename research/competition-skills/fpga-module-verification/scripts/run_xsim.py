"""Run one standalone Verilog/SV self-checking case; never overwrite evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


class CaseError(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(path):
    path = Path(path).resolve(strict=True)
    case = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {"schema_version", "name", "top", "tool_version", "contract", "sources", "minimum_checks"}
    if (not isinstance(case, dict) or set(case) != required or
            type(case["schema_version"]) is not int or case["schema_version"] != 1):
        raise CaseError("Unsupported case schema or fields")
    for key in ("name", "top"):
        if not isinstance(case[key], str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", case[key]):
            raise CaseError("Invalid name/top")
    if not isinstance(case["tool_version"], str) or not re.fullmatch(r"20[0-9]{2}\.[0-9]+", case["tool_version"]):
        raise CaseError("Specify actual expected tool_version")
    if type(case["minimum_checks"]) is not int or case["minimum_checks"] < 1:
        raise CaseError("minimum_checks must be positive integer")
    if not isinstance(case["sources"], list) or not case["sources"]:
        raise CaseError("No sources")
    files = []
    for source in case["sources"]:
        if not isinstance(source, str):
            raise CaseError("Source path must be a string")
        src = (path.parent / source).resolve(strict=True)
        if not src.is_file() or not re.fullmatch(r"[a-zA-Z0-9_]+\.(v|sv)", src.name):
            raise CaseError("Use standalone .v/.sv source basenames")
        files.append(src)
    if len({p.name.lower() for p in files}) != len(files):
        raise CaseError("Duplicate source basenames")
    if not isinstance(case["contract"], str):
        raise CaseError("Contract path must be a string")
    contract = (path.parent / case["contract"]).resolve(strict=True)
    if not contract.is_file():
        raise CaseError("Missing contract file")
    return case, files, contract


def assess(log, minimum_checks):
    bad = re.search(r"(?im)^\s*(?:fatal:|error:|\$fatal|skill_fail\b|fail\b)", log)
    if bad:
        return {"status": "FAIL_SIMULATION", "first_failure": log[bad.start():].splitlines()[0].strip()}
    markers = re.findall(r"(?m)^SKILL_PASS cases=(\d+) checks=(\d+)\s*$", log)
    if len(markers) != 1:
        return {"status": "FAIL_SIMULATION", "first_failure": "Missing or duplicate final self-check marker"}
    cases, checks = map(int, markers[0])
    if cases < 1 or checks < minimum_checks:
        return {"status": "FAIL_SIMULATION", "first_failure": "Insufficient executed checks"}
    return {"status": "PASS_SIMULATION", "cases": cases, "checks": checks}


def execute(command, cwd, env, timeout):
    options = {"start_new_session": True} if os.name != "nt" else {}
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, **options)
    try:
        raw, _ = process.communicate(timeout=timeout)
        return {"returncode": process.returncode, "text": raw.decode("utf-8", errors="replace"), "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        cleanup = False
        if os.name == "nt":
            try:
                killed = subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                        capture_output=True, timeout=10, check=False)
                cleanup = killed.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                cleanup = True
            except ProcessLookupError:
                cleanup = True
        try:
            raw, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            raw = exc.output or b""
        return {"returncode": process.returncode, "text": raw.decode("utf-8", errors="replace"),
                "timed_out": True, "cleanup_confirmed": cleanup, "pid": process.pid}


def run(case_path, vivado_bin, output, timeout=90):
    output = Path(output).resolve()
    if output.exists():
        raise CaseError("Use a NEW output directory; nothing was overwritten")
    output.mkdir(parents=True)
    result = {"status": "BLOCKED_INPUT", "stage": "preflight", "evidence_class": "rtl_simulation",
              "not_run": ["synthesis", "timing", "cdc", "board", "system"],
              "runner_sha256": digest(__file__), "commands": [], "sources": [],
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "python_version": sys.version, "platform": sys.platform}
    exit_code = 2
    started = time.monotonic()
    try:
        if not (0 < timeout <= 3600):
            raise CaseError("Timeout must be positive and <= 3600 seconds")
        case, sources, contract = load_case(case_path)
        tool_root = Path(vivado_bin).resolve(strict=True)
        if os.name == "nt" and any(re.search(r'[&|<>^%!"()\r\n]', str(p)) for p in (tool_root, output)):
            raise CaseError("Windows batch-tool paths contain unsupported shell metacharacters")
        suffix = ".bat" if os.name == "nt" else ""
        tools = {name: str(tool_root / (name + suffix)) for name in ("xvlog", "xelab", "xsim")}
        if not all(Path(p).is_file() for p in tools.values()):
            raise CaseError("Missing XSim tools in explicit directory")
        result.update(name=case["name"], top=case["top"], expected_tool_version=case["tool_version"],
                      manifest_sha256=digest(case_path), vivado_bin=str(tool_root))
        work = output / "work"
        work.mkdir()
        snapshot = output / "inputs"
        snapshot.mkdir()
        shutil.copyfile(case_path, snapshot / "case.json")
        shutil.copyfile(contract, snapshot / "contract.md")
        result["contract_sha256"] = digest(snapshot / "contract.md")
        for src in sources:
            dest = snapshot / src.name
            shutil.copyfile(src, dest)
            shutil.copyfile(dest, work / src.name)
            result["sources"].append({"path": str(src), "snapshot": "inputs/" + src.name, "sha256": digest(dest)})
        env = os.environ.copy()
        if os.name == "nt" and not env.get("PROCESSOR_ARCHITECTURE"):
            env["PROCESSOR_ARCHITECTURE"] = "AMD64"

        def step(stage, command):
            result["stage"] = stage
            result["commands"].append({"stage": stage, "argv": command, "cwd": str(work)})
            observation = execute(command, work, env, timeout)
            log = output / (stage + ".log")
            log.write_text(observation["text"], encoding="utf-8")
            result["commands"][-1].update({k: v for k, v in observation.items() if k != "text"})
            result["commands"][-1]["log_sha256"] = digest(log)
            if observation["timed_out"]:
                result["status"] = "TIMEOUT"
                raise TimeoutError(stage)
            if observation["returncode"] != 0:
                result["status"] = "FAIL_TOOL"
                raise RuntimeError(stage + " failed; inspect " + log.name)
            return observation["text"]

        version = step("version", [tools["xvlog"], "--version"])
        if not re.search(r"(?<![\d.])" + re.escape(case["tool_version"]) + r"(?![\d.])", version):
            result["status"] = "BLOCKED_ENV"
            raise CaseError("Actual xvlog version does not match manifest")
        for ext, flag in ((".v", []), (".sv", ["--sv"])):
            names = [p.name for p in sources if p.suffix == ext]
            if names:
                step("compile_" + ext[1:], [tools["xvlog"]] + flag + names)
        step("elaborate", [tools["xelab"], "work." + case["top"], "-s", "module_test", "-timescale", "1ns/1ps"])
        log = step("simulate", [tools["xsim"], "module_test", "-runall", "-log", "xsim.log"])
        result.update(assess(log, case["minimum_checks"]))
        exit_code = 0 if result["status"] == "PASS_SIMULATION" else 1
    except (CaseError, FileNotFoundError, json.JSONDecodeError, TypeError, KeyError) as exc:
        result["error"] = str(exc)
    except TimeoutError as exc:
        result["error"] = str(exc)
        exit_code = 3
    except RuntimeError as exc:
        result["error"] = str(exc)
        exit_code = 1
    except OSError as exc:
        result.update(status="BLOCKED_ENV", error=str(exc))
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return exit_code, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--vivado-bin", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    try:
        code, result = run(args.case, args.vivado_bin, args.output, args.timeout)
    except (CaseError, OSError) as exc:
        print("BLOCKED_INPUT:", exc)
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
