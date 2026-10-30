"""Read-only first check on PYNQ: no MMIO, bit download, reset, or motion.

Run from the extracted SoundSight_PYNQ directory. JSON output can be returned
to the coordinator before attempting the hardware-facing runtime.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET


def inspect(hwh, bit):
    errors = []
    cpus = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    gcc = shutil.which("gcc")
    pynq_present = importlib.util.find_spec("pynq") is not None
    result = dict(system=platform.system(), machine=platform.machine(),
                  python=platform.python_version(), python_executable=sys.executable,
                  process_bits=struct.calcsize("P") * 8, allowed_cpus=cpus,
                  pynq_installed=pynq_present, gcc=gcc,
                  hardware_access=False, bit_downloaded=False)
    cmdline = Path("/proc/cmdline")
    if cmdline.is_file():
        result["boot_arguments"] = cmdline.read_text().strip()
    if result["system"] != "Linux" or not result["machine"].lower().startswith("arm"):
        errors.append("Run this check on the Zynq PYNQ board (ARM Linux).")
    if result["process_bits"] != 32:
        errors.append("This Zynq-7000 delivery expects a 32-bit ARM userspace.")
    if sys.version_info < (3, 8):
        errors.append("Python 3.8 or later is required.")
    if not {0, 1}.issubset(cpus):
        errors.append("CPU 0 and CPU 1 must both be available; do not load a bare-metal CPU1 ELF.")
    if not pynq_present:
        errors.append("Use the Python environment containing PYNQ.")
    if not gcc:
        errors.append("gcc is needed to build and check the C solver on the board.")
    else:
        p = subprocess.run([gcc, "--version"], capture_output=True, text=True, timeout=10)
        if p.returncode:
            errors.append("gcc --version failed.")
        else:
            result["compiler"] = p.stdout.splitlines()[0]
    if not bit.is_file() or bit.stat().st_size == 0:
        errors.append("Missing nonempty soundsight.bit.")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software/ps"))
        from run_capture import address_from_hwh
        base, size = address_from_hwh(hwh)
        result["ps_link"] = dict(base=hex(base), bytes=size)
        tree = ET.parse(hwh)
        module = next(m for m in tree.iter("MODULE") if m.get("INSTANCE") == "ps_link")
        params = {p.get("NAME"): p.get("VALUE") for p in module.iter("PARAMETER")}
        result["actuator_bound"] = params.get("ACTUATOR_BOUND")
        if result["actuator_bound"] != "0":
            errors.append("This first-run package is for ACTUATOR_BOUND=0.")
    except (OSError, ValueError, ET.ParseError, StopIteration) as exc:
        errors.append("HWH check failed: " + str(exc))
    result["errors"] = errors
    result["result"] = "READY_FOR_ARM_OFFLINE_TEST" if not errors else "NEEDS_ATTENTION"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwh", type=Path, default=Path("soundsight.hwh"))
    parser.add_argument("--bit", type=Path, default=Path("soundsight.bit"))
    args = parser.parse_args()
    result = inspect(args.hwh, args.bit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
