"""Static handoff comparison; never starts Vivado or validates RTL behavior.

Default: compare the archived export with the maintained recipes. Optional
--live-project and --export-dir also compare the user's current work copy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tkinter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "stm32-handoff-20261018/original"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(path):
    return [line.rstrip() for line in path.read_text("utf-8-sig").splitlines()]


def interpreter():
    tcl = tkinter.Tcl()
    events = []

    def record(command, *args):
        events.append((command, args))
        return args[-1] if args else ""

    for command in ("create_bd_cell", "create_bd_port", "create_bd_intf_port",
                    "connect_bd_net", "connect_bd_intf_net", "set_property",
                    "create_ip"):
        tcl.createcommand(command, lambda *args, cmd=command: record(cmd, *args))
    for command in ("get_bd_cells", "get_bd_pins", "get_bd_ports",
                    "get_bd_intf_ports", "get_bd_intf_pins", "get_ips",
                    "get_files", "get_runs"):
        tcl.createcommand(command, lambda *args: args[-1])
    tcl.createcommand("get_property", lambda *args: "hier")
    # GUI layout is not electrical connectivity. The latest export omits it.
    for command in ("current_bd_instance", "create_bd_design", "validate_bd_design",
                    "save_bd_design", "regenerate_bd_layout"):
        tcl.createcommand(command, lambda *args: "/")
    # Use Python to read source files; do not depend on Tcl's host path encoding.
    tcl.createcommand("source", lambda path: tcl.eval(Path(path).read_text("utf-8-sig")))
    return tcl, events


def check(export, live):
    bd = (export / "soundsight_stm32_bd.tcl").read_text("utf-8-sig")
    body = bd[bd.index("proc create_root_design {"):bd.index("# End of create_root_design()")]
    tcl, expected = interpreter()
    tcl.eval(body)
    tcl.eval('create_root_design ""')
    tcl, actual = interpreter()
    tcl.setvar("ss_root", ROOT.as_posix())
    tcl.eval((ROOT / "project/bd/stm32.tcl").read_text("utf-8-sig"))
    assert actual == expected, "BD cells/properties/connections differ"

    fft, fft_events = interpreter()
    fft.setvar("destination", ".")
    fft.eval("rename file real_file; proc file {sub args} {if {$sub eq {mkdir}} {return}; real_file $sub {*}$args}")
    fft.eval((ROOT / "project/ip/create_fft_ip.tcl").read_text("utf-8-sig"))
    fft_counts = {}
    ip_hashes = {}
    for command, args in fft_events:
        if command != "set_property":
            continue
        values = fft.splitlist(args[1])
        props = dict(zip(values[::2], values[1::2]))
        name = args[2]
        reference = PREVIOUS / (name + ".xci")
        candidate = export / (name + ".xci")
        if not candidate.exists():
            candidate = reference  # Unchanged XCI retained once in prior evidence.
        assert json.loads(candidate.read_text()) == json.loads(reference.read_text()), name
        exported = json.loads(candidate.read_text())["ip_inst"]["parameters"]["component_parameters"]
        for key, value in props.items():
            assert exported[key.removeprefix("CONFIG.")][0]["value"] == value, (name, key)
        assert exported["Component_Name"][0]["value"] == name
        assert exported["blocking_run_time_configuration"][0]["value"] == "false"
        assert len(exported) == len(props) + 2
        fft_counts[name] = len(props)
        ip_hashes[name] = digest(candidate)

    settings, setting_events = interpreter()
    settings.eval((ROOT / "project/script/stm32_settings.tcl").read_text("utf-8-sig"))
    project = (export / "project.tcl").read_text("utf-8-sig")
    count = 0
    for command, args in setting_events:
        if args[0] != "-name":
            continue
        _, prop, _, value, _, run = args
        start = project.rindex("set obj [get_runs " + run + "]")
        end = "# Create 'impl_1' run" if run == "synth_1" else "# set the current impl run"
        block = project[start:project.index(end, start)]
        lines = [s for s in block.splitlines() if s.startswith('set_property -name "' + prop + '"')]
        assert len(lines) == 1, (run, prop)
        parsed, events = interpreter()
        parsed.setvar("obj", run)
        parsed.eval(lines[0])
        assert events == [(command, args)], (run, prop, value)
        count += 1

    # The disabled debug XDC is evidence only, not a maintained dependency.
    pos = project.index('set file "spi_ila_debug/spi_ila_debug.xdc"')
    debug_block = project[pos:project.index("\n#", pos)]
    assert 'set_property -name "is_enabled" -value "0"' in debug_block
    assert 'set_property -name "used_in" -value "implementation"' in debug_block
    manifest = ROOT / "document/build/stm32-handoff-files.txt"
    files = [s for s in manifest.read_text().splitlines() if s and not s.startswith("#")]
    assert len(files) == len(set(files))
    for name in files:
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), name
        if path.suffix in (".tcl", ".py", ".bat", ".v", ".sv", ".xdc"):
            text = path.read_text("utf-8-sig")
            # OS fallback is not a sender workspace/tool dependency.
            path_text = text.replace("C:/Windows/System32/cmd.exe", "OS_COMMAND_SHELL")
            assert not re.search(r"[A-Za-z]:[/\\]", path_text), name
            assert not re.search(r"spi_ila_debug|create_debug_core|MARK_DEBUG", text, re.I), name
        if path.suffix == ".tcl":
            assert tcl.call("info", "complete", path.read_text("utf-8-sig")), name

    source_rows = []
    if live:
        pairs = [(p, ROOT / "project/rtl" / p.name) for p in sorted(
            (live / "SoundSight_STM32.srcs/sources_1/imports/rtl").iterdir()) if p.is_file()]
        pairs += [(p, ROOT / "project/sdc/stm32" / p.name) for p in sorted(
            (live / "SoundSight_STM32.srcs/constrs_1/imports/stm32").glob("*.xdc"))]
        assert len(pairs) == 28, "Expected 25 RTL files, one memory file, two XDC files"
        for source, target in pairs:
            assert target.is_file() and normalized(source) == normalized(target), str(source)
            source_rows.append({"repository": target.relative_to(ROOT).as_posix(),
                                "external_sha256": digest(source), "repository_sha256": digest(target),
                                "equal_ignoring_line_endings_and_trailing_spaces": True})
    return {"status": "PASS", "scope": "Static configuration/dependency/source comparison only",
            "bd_functional_events_matched": len(actual), "bd_gui_layout": "excluded; existing layout retained",
            "fft_explicit_parameters_matched": fft_counts, "unchanged_xci_sha256": ip_hashes,
            "run_properties_matched": count, "handoff_engineering_files": len(files),
            "external_debug_xdc": "disabled; not imported into maintained recipes",
            "live_sources_compared": source_rows,
            "export_sha256": {n: digest(export / n) for n in ("project.tcl", "soundsight_stm32_bd.tcl")},
            "vivado_started": False, "rtl_simulation": "SKIPPED; existing board fix synchronized",
            "recipe_rebuild": "NOT_RUN", "new_board_test": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=HERE / "original")
    parser.add_argument("--live-project", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.export_dir, args.live_project)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
