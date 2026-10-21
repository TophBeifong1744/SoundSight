"""Package current PYNQ software with a user's matching bit/HWH and XSA.

Only reads the external hardware project. Does not start Vivado or board actions.
Tool locations and workspaces are arguments, not public machine-specific defaults.
"""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def one(paths, label):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError("Expected one %s, found %s" % (label, paths))
    return paths[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hardware-project", type=Path, required=True)
    p.add_argument("--xsa", type=Path, required=True)
    p.add_argument("--volume", action="store_true", help="Volume ABI, separate board directory and matching instructions")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.output is None:
        args.output = ROOT / 'release/output' / ('soundsight_pynq_volume.zip' if args.volume else 'soundsight_pynq.zip')
    board_dir = 'SoundSight_PYNQ_Volume' if args.volume else 'SoundSight_PYNQ'
    hw = args.hardware_project.resolve()
    bit = one(hw.glob("*.runs/impl_1/*.bit"), "implemented bit")
    hwh = one(hw.glob("*.gen/sources_1/bd/*/hw_handoff/*.hwh"), "BD HWH")
    with zipfile.ZipFile(args.xsa) as xsa:
        embedded_bit = one((n for n in xsa.namelist() if n.endswith(".bit")), "XSA bit")
        embedded_hwh = one((n for n in xsa.namelist() if n.endswith(".hwh")), "XSA HWH")
        if xsa.read(embedded_bit) != bit.read_bytes() or xsa.read(embedded_hwh) != hwh.read_bytes():
            raise ValueError("External bit/HWH do not match the supplied XSA; do not mix builds.")
    tree = ET.parse(hwh)
    module = one((m for m in tree.iter("MODULE") if m.get("INSTANCE") == "ps_link"
                  and m.get("MODTYPE") == "bd_ps_link"), "ps_link")
    params = {x.get("NAME"): x.get("VALUE") for x in module.iter("PARAMETER")}
    if params.get("ACTUATOR_BOUND") != "0":
        raise ValueError("This first-run package is for the no-motion hardware candidate.")
    if args.volume:
        compute = one((m for m in tree.iter('MODULE') if m.get('INSTANCE') == 'compute'
                       and m.get('MODTYPE') == 'bd_clean_compute'), 'compute')
        compute_params = {x.get('NAME'): x.get('VALUE') for x in compute.iter('PARAMETER')}
        if params.get('LEVEL_ENABLE') != '1' or compute_params.get('LEVEL_ENABLE') != '1':
            raise ValueError('Volume package requires LEVEL_ENABLE=1 in both modules.')
    software = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source = dict(software_git=software, pr15="61e7303331641ec2353f89088b060aa81ffd6110",
                  pr16="0d388586af1dcd0355a2ab9d51360d4a9fb249cf",
                  hardware_project_name=hw.name, original_bit=bit.name,
                  original_hwh=hwh.name, xsa_byte_match=True,
                  bit_bytes=bit.stat().st_size, hwh_bytes=hwh.stat().st_size,
                  actuator_bound=0, target_arm="NOT_RUN", board="NOT_RUN")
    source['software_source'] = 'current working tree; git value is the base commit'
    source['software_worktree_status'] = subprocess.check_output(
        ['git', 'status', '--porcelain', '--', 'software', 'tools/package_pynq.py'],
        cwd=ROOT, text=True).splitlines()
    source['board_directory'] = board_dir
    if args.volume:
        source.update(level_enable=1, expected_abi='0x00010001',
                      threshold='explicit PS argument; 1000 is an uncalibrated trial value',
                      online_angle_filter=False, servo_motion=False)
    entries = {}
    # An allowlist excludes compiler outputs, user logs and Windows executables.
    for folder, extensions in [
        ("software/common", {".c", ".h", ".md", ".txt"}),
        ("software/ps", {".c", ".py", ".sh", ".txt"}),
    ]:
        for f in (ROOT / folder).rglob("*"):
            if f.is_file() and f.suffix in extensions and "build" not in f.relative_to(ROOT).parts:
                entries[f.relative_to(ROOT).as_posix()] = f
    for name in [
        "software/tests/test_solver_migration.py",
        "software/tests/solver_migration_reference.c",
        "software/tests/test_smp.py",
        "software/tests/test_buffered.py",
        "software/tests/test_application.py",
        "document/evidence/ps-solver-migration-20261020/PC-RESULT.json",
        "document/evidence/inherited/ps/bd_preparation/interface.hwh",
        "tools/pynq_preflight.py",
        "tools/tool_config.py",
        "document/pynq-ram-queue.md",
        "LICENSE",
    ]:
        entries[name] = ROOT / name
    entries["README.md"] = ROOT / "document/pynq-first-run.md"
    if args.volume:
        entries['README.md'] = ROOT / 'document/pynq-volume-sd.md'
        entries['document/ps-volume-gate.md'] = ROOT / 'document/ps-volume-gate.md'
        entries['software/tests/test_volume_gate.py'] = ROOT / 'software/tests/test_volume_gate.py'
    entries["soundsight.bit"] = bit
    entries["soundsight.hwh"] = hwh
    for suffix in ("_timing_summary_routed.rpt", "_drc_routed.rpt"):
        report = bit.with_name(bit.stem + suffix)
        entries["reports/" + report.name] = report
    for name, path in entries.items():
        if not path.is_file():
            raise FileNotFoundError(str(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwriting an older delivery without the caller first retaining it.
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as package:
        for name, path in sorted(entries.items()):
            package.write(path, board_dir + '/' + name)
        package.writestr(board_dir + '/SOURCE.json',
                        json.dumps(source, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(args.output) as package:
        if package.testzip() or any(package.read(board_dir+'/'+name) != path.read_bytes()
                                   for name, path in entries.items()):
            raise ValueError('Package integrity or source copy mismatch.')
    print("PYNQ_PACKAGE_CREATED", args.output, "files=", len(entries) + 1)
    print("No ARM compilation, MMIO, download, reset or motion executed.")


if __name__ == "__main__":
    main()
