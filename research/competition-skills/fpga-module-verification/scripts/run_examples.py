"""Positive, mutated-DUT and restored-DUT XSim demonstration; author test only."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from run_xsim import run, digest


def two_stage_mutant(content):
    """Disposable two-slot implementation: intentionally violates one-slot latency."""
    if content.count("module elastic_stage #") != 1:
        raise ValueError("Expected one elastic_stage declaration")
    return content.replace("module elastic_stage #", "module inner_stage #", 1) + '''
module elastic_stage #(parameter WIDTH=8)(
    input wire clk, rst_n, in_valid, output wire in_ready,
    input wire [WIDTH-1:0] in_data,
    output wire out_valid, input wire out_ready,
    output wire [WIDTH-1:0] out_data
);
    wire mid_valid, mid_ready;
    wire [WIDTH-1:0] mid_data;
    inner_stage #(.WIDTH(WIDTH)) a(
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(in_ready),
        .in_data(in_data), .out_valid(mid_valid), .out_ready(mid_ready), .out_data(mid_data));
    inner_stage #(.WIDTH(WIDTH)) b(
        .clk(clk), .rst_n(rst_n), .in_valid(mid_valid), .in_ready(mid_ready),
        .in_data(mid_data), .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data));
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vivado-bin", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    if output.exists():
        parser.error("Use a new output directory")
    output.mkdir(parents=True)
    summary = {"status": "RUNNING", "scope": "author demonstration, not independent B review",
               "script_sha256": digest(__file__), "runs": []}
    cases = [("pcm4", root / "examples/pcm4/case.json", "PASS_SIMULATION"),
             ("elastic", root / "examples/elastic/case.json", "PASS_SIMULATION")]
    try:
        for label, old, new in (
            ("bad_data", "out_data <= in_data;", "out_data <= in_data ^ 1'b1;"),
            ("bad_ready", "!out_valid || out_ready", "out_ready"),
            ("two_stage", None, None),
        ):
            fixture = output / "fixtures" / label
            fixture.mkdir(parents=True)
            for path in (root / "examples/elastic").iterdir():
                if path.is_file():
                    shutil.copyfile(path, fixture / path.name)
            dut = fixture / "elastic_stage.v"
            content = dut.read_text(encoding="utf-8")
            if label == "two_stage":
                changed = two_stage_mutant(content)
            else:
                if content.count(old) != 1:
                    raise ValueError("Mutation no longer matches exactly once; update test explicitly")
                changed = content.replace(old, new)
            dut.write_text(changed, encoding="utf-8")
            cases.append((label, fixture / "case.json", "FAIL_SIMULATION"))
        cases.append(("restored", root / "examples/elastic/case.json", "PASS_SIMULATION"))
        for name, case, expected in cases:
            code, result = run(case, args.vivado_bin, output / name)
            ok = result["status"] == expected and result["stage"] == "simulate" and code == (0 if expected.startswith("PASS") else 1)
            item = {"name": name, "expected": expected, "actual": result["status"],
                    "matched": ok, "checks": result.get("checks"), "first_failure": result.get("first_failure"),
                    "result": name + "/result.json", "result_sha256": digest(output / name / "result.json")}
            summary["runs"].append(item)
            print(json.dumps(item), flush=True)
            if not ok:
                raise RuntimeError("Unexpected run outcome: " + name)
        summary["status"] = "PASS_DEMONSTRATION"
    except Exception as exc:
        summary.update(status="FAIL_OR_BLOCKED", error=str(exc))
    finally:
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["status"] == "PASS_DEMONSTRATION" else 1


if __name__ == "__main__":
    sys.exit(main())
