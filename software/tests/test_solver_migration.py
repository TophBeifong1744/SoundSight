"""B -> C: offline S1/ctypes equivalence; no PYNQ import or hardware access.

Default: compile and test on the current host.
--library: test the existing target library built by software/ps/build_solver.sh.
--golden: also compare every result with a saved PC RESULT.json.
Python 3.8+, C99; generated executables stay in a temporary build directory.
"""
import argparse
import copy
import ctypes as C
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("api_status direction_valid reason angle_q8 ux_q20 uy_q20 valid_pairs "
        "servo_deg servo_cmd_valid map_status first_error bad_pair").split()
# Fixture values are the frozen 2D profile, not new public ABI definitions.
REAL_FLAGS = 0x11003800
BIST_FLAGS = 0x66001800
EXAMPLE_CONFIG = [23040, 1, -23040, 23040, 0, 180, 180]


def make_case(name, lags, bist=False, left=800, right=800, config=None):
    return dict(name=name, sequence=1, frame_flags=0x18 if bist else 0x10,
                config=config, pairs=[
                    [lag, 1000, left, right, 100, 79,
                     BIST_FLAGS if bist else REAL_FLAGS] for lag in lags])


def cases():
    result = [
        make_case("BIST_REJECT", [5, -3, 0, 1, -1, 2], True, right=600,
                  config=EXAMPLE_CONFIG),
        make_case("BIST_ZERO", [4, 4, 0, 0, -4, -4], True, config=EXAMPLE_CONFIG),
    ]
    for name, lags in [
        ("PLUS_45", [3, 6, 3, 3, 0, -3]),
        ("MINUS_45", [3, 0, -3, -3, -6, -3]),
        ("PLUS_90", [0, 4, 4, 4, 4, 0]),
        ("MINUS_90", [0, -4, -4, -4, -4, 0]),
        ("MINUS_180", [-4, -4, 0, 0, 4, 4]),
        ("OFF_AXIS", [4, 5, 1, 1, -3, -4]),
    ]:
        result.append(make_case(name, lags, config=EXAMPLE_CONFIG))
    base = make_case("BASE", [4, 4, 0, 0, -4, -4])
    for mask in (11, 12, 79, 80):
        f = copy.deepcopy(base)
        f["name"] = "MASK_" + str(mask)
        for pair in f["pairs"]:
            pair[5] = mask
        result.append(f)
    for lag in (-33, -32, 31, 32):
        f = copy.deepcopy(base)
        f["name"] = "LAG_" + str(lag)
        f["pairs"][0][0] = lag
        result.append(f)
    for value in (-16777217, -16777216, 16777215, 16777216):
        f = copy.deepcopy(base)
        f["name"] = "S25_" + str(value)
        f["pairs"][0][1] = value
        result.append(f)
    f = copy.deepcopy(base)
    f["name"] = "TWO_PAIRS"
    for pair in f["pairs"][2:]:
        pair[6] &= ~0x800
    result.append(f)
    f = copy.deepcopy(base)
    f["name"] = "FRAME_CANCEL"
    f["frame_flags"] |= 0x100000
    result.append(f)
    f = copy.deepcopy(base)
    f["name"] = "NO_MAPPING"
    result.append(f)
    # Denominator after normalization is 8192. Differences 2/6/10 produce
    # exact +/-0.5, +/-1.5, +/-2.5, including ties rounding both up and down.
    for difference in (2, 6, 10):
        for sign in (-1, 1):
            f = copy.deepcopy(base)
            f["name"] = "RNE_%+d_OVER_4" % (sign * difference)
            left, right = 4096 + difference, 4096
            if sign > 0:
                left, right = right, left
            for pair in f["pairs"]:
                pair[1:5] = [8192 + difference // 2, left, right, 100]
            result.append(f)
    # Fixed seed; baseline outputs can be replayed on ARM without target hardware.
    rng = random.Random(20261020)
    for i in range(128):
        f = make_case("SEEDED_%03d" % i, [rng.randrange(-8, 9) for _ in range(6)])
        for pair in f["pairs"]:
            pair[2] = rng.randrange(500, 1001)
            pair[3] = rng.randrange(500, 1001)
            pair[4] = rng.randrange(0, 1001)
            pair[5] = rng.randrange(10, 80)
        result.append(f)
    return result


def wire_frame(case):
    words = []
    for index, p in enumerate(case["pairs"]):
        lag, peak, left, right, second, mask, flags = p
        words.append((lag & 255) | (index << 8) | (mask << 16) | flags)
        words.extend(value & 0xffffffff for value in (peak, left, right, second))
    return dict(sequence=case["sequence"], status=case["frame_flags"] | 1,
                words=words)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--library", type=Path)
    ap.add_argument("--golden", type=Path)
    ap.add_argument("--output", type=Path,
                    default=ROOT / "software/build/solver-migration/RESULT.json")
    args = ap.parse_args()
    if os.name == "nt":
        sys.path.insert(0, str(ROOT / "tools"))
        from tool_config import gcc_executable
        gcc = str(gcc_executable())
    else:
        gcc = os.environ.get("CC", "gcc")
        if not shutil.which(gcc):
            raise RuntimeError("C compiler unavailable: " + gcc)
    spec = importlib.util.spec_from_file_location("ss_ps_client",
                                                ROOT / "software/ps/ps_client.py")
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logs = []

    def run(cmd):
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        logs.append(dict(command=cmd, returncode=proc.returncode,
                         stdout=proc.stdout, stderr=proc.stderr))
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        return proc.stdout

    # C's Solver is used unchanged; the oracle accepts semantic fields, not words.
    with tempfile.TemporaryDirectory(prefix="migration_", dir=args.output.parent) as tmp, ExitStack() as libraries:
        tmp = Path(tmp)
        common = [gcc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Wconversion",
                  "-Wshadow", "-Werror", "-pedantic",
                  "-I" + str(ROOT / "software/common"),
                  "-I" + str(ROOT / "software/common/s1")]
        if os.name == "nt":
            common.append("-D__USE_MINGW_ANSI_STDIO=1")
        core = str(ROOT / "software/common/s1/doa_solver.c")
        suffix = ".dll" if os.name == "nt" else ".so"
        shared = ["-shared"] + ([] if os.name == "nt" else ["-fPIC"])
        exe = tmp / ("s1.exe" if os.name == "nt" else "s1")
        run(common + [core, str(ROOT / "software/common/s1/test_doa_solver.c"),
                      "-lm", "-o", str(exe)])
        s1 = run([str(exe)])
        if "failures=0" not in s1 or "4705" not in s1:
            raise AssertionError("Original S1 test suite did not pass")
        library = args.library.resolve() if args.library else tmp / ("solver" + suffix)
        if not args.library:
            run(common + shared + [core, str(ROOT / "software/ps/ss_solver_bridge.c"),
                                   "-lm", "-o", str(library)])
        reference_path = tmp / ("reference" + suffix)
        run(common + shared + [core, str(ROOT / "software/tests/solver_migration_reference.c"),
                               "-lm", "-o", str(reference_path)])
        solver = client.Solver(library)
        if os.name == "nt":
            import _ctypes
            libraries.callback(_ctypes.FreeLibrary, solver.lib._handle)
        ref_lib = C.CDLL(str(reference_path))
        if os.name == "nt":
            libraries.callback(_ctypes.FreeLibrary, ref_lib._handle)
        ref = ref_lib.migration_reference
        ref.argtypes = [C.c_uint32, C.c_uint32, C.POINTER(C.c_int32),
                        C.POINTER(C.c_int32), C.POINTER(C.c_int32)]
        ref.restype = C.c_int
        records = []
        fixed = {
            "BIST_REJECT": dict(direction_valid=0, reason=3, ux_q20=46831,
                                uy_q20=-171729, servo_cmd_valid=0),
            "BIST_ZERO": dict(direction_valid=1, reason=0, ux_q20=749295,
                              uy_q20=0, angle_q8=0, servo_cmd_valid=0),
            "PLUS_45": dict(direction_valid=1, angle_q8=11520),
            "MINUS_45": dict(direction_valid=1, angle_q8=-11520),
            "PLUS_90": dict(direction_valid=1, angle_q8=23040),
            "MINUS_90": dict(direction_valid=1, angle_q8=-23040),
            "MASK_11": dict(direction_valid=0, reason=1),
            "MASK_12": dict(direction_valid=1),
            "TWO_PAIRS": dict(direction_valid=0, reason=1),
            "FRAME_CANCEL": dict(direction_valid=0, reason=6),
            "NO_MAPPING": dict(direction_valid=1, servo_cmd_valid=0),
        }
        for case in cases():
            config = case["config"]
            cfg = (C.c_int32 * 7)(*config) if config is not None else None
            data = (C.c_int32 * 42)(*(v for p in case["pairs"] for v in p))
            out = (C.c_int32 * 12)()
            rc = ref(case["sequence"], case["frame_flags"], data, cfg, out)
            expected = dict(zip(KEYS, out))
            expected["bridge_status"] = rc
            frame = wire_frame(case)
            actual = solver.solve(frame, config)
            if actual != expected:
                raise AssertionError((case["name"], expected, actual))
            for key, value in fixed.get(case["name"], {}).items():
                if actual[key] != value:
                    raise AssertionError((case["name"], key, value, actual[key]))
            records.append(dict(name=case["name"], frame=frame, config=config,
                                expected=expected, actual=actual))
        bad_results = []
        for name, change, code in [
            ("ZERO_SEQUENCE", lambda f: f.update(sequence=0), -1),
            ("STATUS_RESERVED", lambda f: f.update(status=f["status"] | 0x200000), -2),
            ("NOT_LOCKED", lambda f: f.update(status=f["status"] & ~1), -3),
            ("PAIR_ECHO", lambda f: f["words"].__setitem__(0, f["words"][0] ^ 0x100), -4),
            ("FEATURE_RESERVED", lambda f: f["words"].__setitem__(0, f["words"][0] | 0x800000), -4),
        ]:
            frame = wire_frame(cases()[1])
            change(frame)
            actual = solver.solve(frame)
            if actual["bridge_status"] != code:
                raise AssertionError((name, actual))
            bad_results.append(dict(name=name, expected=code, actual=actual["bridge_status"]))
        config = EXAMPLE_CONFIG[:]
        config[4] = -1
        actual = solver.solve(wire_frame(cases()[1]), config)
        if actual["bridge_status"] != -5:
            raise AssertionError(("NEGATIVE_MECHANICAL_LIMIT", actual))
        bad_results.append(dict(name="NEGATIVE_MECHANICAL_LIMIT", expected=-5, actual=-5))
        if args.golden:
            golden = json.loads(args.golden.read_text(encoding="utf-8"))
            compare = lambda items: [(x["name"], x["frame"], x["config"], x["expected"]) for x in items]
            if compare(golden["cases"]) != compare(records):
                raise AssertionError("Target differs from saved PC baseline")
        report = dict(result="PASS", machine=platform.machine(), system=platform.system(),
                      python=platform.python_version(), compiler=run([gcc, "--version"]).splitlines()[0],
                      original_s1_assertions=4705, equivalence_cases=len(records),
                      bridge_negative_cases=bad_results, cases=records,
                      golden_compared=bool(args.golden),
                      scope="OFFLINE_NO_MMIO_NO_MOTION", commands=logs)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        # ExitStack releases DLLs before TemporaryDirectory on success or failure.
    print("MIGRATION_PASS original_s1=4705 equivalence=%d bridge_negative=%d" %
          (len(records), len(bad_results)))
    for item in records[:8]:
        print(item["name"], json.dumps(item["actual"], sort_keys=True))
    print(args.output)


if __name__ == "__main__":
    main()
