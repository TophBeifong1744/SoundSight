# XSim runner and first-failure debugging

Requirements: Python 3.10+, Vivado XSim tools, a reviewed local case manifest. Windows is the tested platform; tool directory is passed explicitly so an older Vivado on PATH is not accidentally used. No pip dependency is needed by the runner. The project uses Vivado 2025.2; another team sets its actual expected version in its manifest.

`case.json` uses schema_version 1, an ASCII name/top, tool_version, a contract path, an ordered list of Verilog/SystemVerilog sources, and minimum_checks >= 1. Paths resolve relative to the manifest. Only standalone `.v`/`.sv` sources are supported; includes, vendor IP libraries, VHDL, Tcl hooks and external data files are not silently inferred. Extend the runner and tests explicitly when these become necessary.

Example, from the repository root:

```text
python -B skill/fpga-module-verification/scripts/run_xsim.py --case skill/fpga-module-verification/examples/elastic/case.json --vivado-bin F:/AMD/2025.2/Vivado/bin --output task-packages/PKG-A-SKILLS/runs/elastic-new
```

The output directory must not exist. It receives `result.json`, original source/contract snapshots and compiler/elaboration/runtime logs; `work/` is reproducible simulator cache, not source. No existing project is opened or edited. A TB is executable code: inspect third-party cases before running them. The runner is not a sandbox or permission grant.

Exit codes: 0 simulation PASS; 1 executed tool/test failure; 2 invalid inputs or unavailable/mismatched tools; 3 timeout (execution incomplete). Read `status` and `stage`, not the exit code alone. On timeout the runner attempts to terminate only its own process tree, retains logs and reports whether cleanup succeeded. It never deletes a run directory.

Successful TB termination requires exactly one line `SKILL_PASS cases=<positive integer> checks=<positive integer>` and at least minimum_checks checks, without fatal/error/fail evidence. Result hashes identify bytes, not reviewer approval or physical measurement. A source changed during the run cannot silently pass against an old source identity because the copied snapshot is the compiled input.

Debug in order:

1. **Environment/version:** fix missing tools, paths or license environment; do not rewrite RTL for an unexecuted simulation. The runner supplies PROCESSOR_ARCHITECTURE to its Windows child if the environment omitted it.
2. **Compile:** inspect the first syntax/type/port error and source line. Cascading later errors may disappear after this one repair.
3. **Elaborate:** check selected TB top, parameter limits, duplicate module names and missing source files.
4. **First mismatch:** distinguish wrong signed arithmetic, channel mapping, reset, latency or accepted-transaction ordering. Compare the contract and reference before modifying either.
5. **Timeout/missing marker:** inspect clock/reset, blocked ready, waiting for impossible counts, undrained queues and a TB that finished without assertions. A larger timeout is not a functional fix.

After a scoped repair, preserve the previous run and repeat the exact case into a fresh directory. Report failing and repaired artifacts together. The built-in examples establish a reproducible technical workflow; B must still test a held-out module/task to evaluate unfamiliar-context Skill use.
