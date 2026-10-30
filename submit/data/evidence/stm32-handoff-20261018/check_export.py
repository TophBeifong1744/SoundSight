"""Compare normalized recipes with the user's export using Tcl, without Vivado.

This records commands and properties only. It cannot validate IP parameter
legality, propagate BD properties, elaborate RTL, or establish physical timing.
"""
import json
import re
import tkinter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def interpreter():
    tcl = tkinter.Tcl()
    events = []

    def record(command, *args):
        events.append((command, args))
        return args[-1] if args else ""

    for command in ("create_bd_cell", "create_bd_port", "create_bd_intf_port",
                    "connect_bd_net", "connect_bd_intf_net", "set_property",
                    "regenerate_bd_layout", "create_ip"):
        tcl.createcommand(command, lambda *args, cmd=command: record(cmd, *args))
    for command in ("get_bd_cells", "get_bd_pins", "get_bd_ports",
                    "get_bd_intf_ports", "get_bd_intf_pins", "get_ips",
                    "get_files", "get_runs"):
        tcl.createcommand(command, lambda *args: args[-1])
    tcl.createcommand("get_property", lambda *args: "hier")
    for command in ("current_bd_instance", "create_bd_design", "validate_bd_design",
                    "save_bd_design"):
        tcl.createcommand(command, lambda *args: "/")
    return tcl, events


def main():
    original = (HERE / "original/stm32_bd.tcl").read_text("utf-8-sig")
    # Evaluate only the exported cell-building procedure, never its project opener.
    body = original[original.index("proc create_root_design {"):
                    original.index("# End of create_root_design()")]
    old, expected = interpreter()
    old.eval(body)
    old.eval('create_root_design ""')
    new, actual = interpreter()
    new.setvar("ss_root", ROOT.as_posix())
    new.call("source", str(ROOT / "project/bd/stm32.tcl"))
    if actual != expected:
        differences = [(i, a, b) for i, (a, b) in enumerate(zip(expected, actual)) if a != b]
        raise AssertionError((len(expected), len(actual), differences[:3]))

    fft, fft_events = interpreter()
    fft.setvar("destination", ".")
    # Suppress mkdir while evaluating the original Tcl, retaining list semantics.
    fft.eval("rename file real_file; proc file {sub args} {if {$sub eq {mkdir}} {return}; real_file $sub {*}$args}")
    fft.call("source", str(ROOT / "project/ip/create_fft_ip.tcl"))
    fft_counts = {}
    for command, args in fft_events:
        if command != "set_property":
            continue
        values = fft.splitlist(args[1])
        props = dict(zip(values[::2], values[1::2]))
        name = args[2]
        xci = json.loads((HERE / "original" / (name + ".xci")).read_text())
        exported = xci["ip_inst"]["parameters"]["component_parameters"]
        for key, value in props.items():
            assert exported[key.removeprefix("CONFIG.")][0]["value"] == value, (name, key)
        # These two fields are not set_property overrides in the shared recipe.
        assert exported["Component_Name"][0]["value"] == name
        assert exported["blocking_run_time_configuration"][0]["value"] == "false"
        assert len(exported) == len(props) + 2
        fft_counts[name] = len(props)

    settings, setting_events = interpreter()
    settings.call("source", str(ROOT / "project/script/stm32_settings.tcl"))
    project_export = (HERE / "original/project.tcl").read_text("utf-8-sig")
    run_properties = 0
    for command, args in setting_events:
        if args[0] != "-name":
            continue
        _, prop, _, value, _, run = args
        start = project_export.rindex("set obj [get_runs " + run + "]")
        end_marker = "# Create 'impl_1' run" if run == "synth_1" else "# set the current impl run"
        block = project_export[start:project_export.index(end_marker, start)]
        parsed, expected_settings = interpreter()
        parsed.setvar("obj", run)
        line = next(s for s in block.splitlines() if s.startswith('set_property -name "' + prop + '"'))
        parsed.eval(line)
        assert expected_settings == [(command, args)], (run, prop, value)
        run_properties += 1

    manifest = ROOT / "document/build/stm32-handoff-files.txt"
    files = [s for s in manifest.read_text().splitlines() if s and not s.startswith("#")]
    assert len(files) == len(set(files))
    for name in files:
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), name
    for name in files:
        path = ROOT / name
        if path.suffix in (".tcl", ".py", ".bat", ".v", ".sv", ".xdc"):
            text = path.read_text("utf-8-sig")
            assert not re.search(r"[EF]:[/\\]", text), name
        if path.suffix == ".tcl":
            assert new.call("info", "complete", path.read_text("utf-8")), name
    result = {"status": "PASS", "scope": "Static export equivalence and dependency existence only",
              "bd_cells": sum(c == "create_bd_cell" for c, _ in actual),
              "bd_signal_nets": sum(c == "connect_bd_net" for c, _ in actual),
              "bd_interface_nets": sum(c == "connect_bd_intf_net" for c, _ in actual),
              "bd_export_events_matched": len(actual), "fft_explicit_parameters_matched": fft_counts,
              "run_properties_matched": run_properties, "handoff_engineering_files": len(files),
              "vivado_started": False, "rebuild_validate_simulation_sta_board": "NOT_RUN"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
