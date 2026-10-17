---
name: fpga-module-verification
description: Develop or debug a bounded FPGA RTL module from an interface and numeric contract, build a self-checking testbench, run Vivado XSim, locate the first mismatch, and retest a scoped correction. Use for module RTL/TB implementation and simulation debugging; not for general team administration, board pin selection, or claiming timing and hardware success from simulation.
---

# FPGA module development and verification

Deliver an executable module-level result, not just a review checklist. Resume the supplied RTL/TB and reuse approved inputs. Ask only for missing facts that change behavior; provisional interfaces may support isolated work. Respect requests to explain/review without editing and projects where the user must write the RTL themselves.

## Establish the module contract

Read the requested module, existing ports and tests, relevant project rules and version. Use [references/rtl-and-tb.md](references/rtl-and-tb.md) for RTL/TB work. Record in the existing package (or adapt [assets/module-contract.md](assets/module-contract.md)):

- combinational vs clocked operation, reset polarity/synchrony and priority;
- bit widths, signedness, fixed-point units, rounding/overflow;
- the event that accepts input/output, latency and initiation interval;
- backpressure/hold behavior, reset in flight, unsupported inputs;
- observable acceptance cases and an independent expected-result method.

No physical pin map is needed for pure behavioral simulation. Unknown power/pins stop related board operations, not independent TB work. Multi-clock CDC, vendor IP or algorithm admission require their own contracts; do not pretend the small runner verifies them.

## Implement and verify

1. Implement only the authorized module. Explicitly size arithmetic and casts; separate combinational next-state from clocked state when useful. Never make an unapproved algorithm a production subsystem. Use the project's HDL convention rather than mass-converting existing files.
2. Construct the TB from the contract, not a copy of the DUT expression. Drive away from the sampling edge; compare at the documented observation time. For streams, queue only accepted inputs and remove only accepted outputs; verify stable valid/data while stalled. For numeric functions use boundary values and independently computed golden values.
3. Include reset/idle, normal, boundary and relevant fault/stall cases. Fix seeds, require a nonzero check count, add a simulation watchdog and stop on first mismatch with transaction/cycle/expected/actual. Drain pipelines and require no queued transactions at completion. An unknown X/Z is a failure, not an integer value to coerce away.
4. Read [references/xsim-and-debug.md](references/xsim-and-debug.md), then run `scripts/run_xsim.py` on a bounded `case.json`. Reuse examples for configuration: `examples/pcm4` tests a real existing module; `examples/elastic` is an independently usable non-acoustic ready/valid module and self-checking TB.
5. Read the actual compile/elaboration/simulation logs. Fix the first causal failure, change only authorized source, and run again into a NEW output directory using the same inputs. Preserve failing logs. Do not change the TB expectation merely to agree with the DUT; an erroneous contract/golden must be explicitly corrected and old results marked incomparable.
6. Prove test sensitivity with a disposable faulty DUT copy, or another justified negative case. Do not mutate approved source to create the fault. A rejected mutant proves detection of that fault, not complete RTL correctness or statistical Skill improvement.

## Return a technical handoff

Give contract, changed RTL/TB, exact command/tool version, input/source hashes, first failure and repair, actual simulation result and remaining boundaries. Use the project's normal reviewer and exact version approval; do not self-merge. Simulation PASS is not synthesis, timing, CDC, board or system PASS. Report those as NOT_RUN unless executed separately.

Use `README.md` for demonstrated behavior and reproduction. Core use does not require another installed Skill or online service. Do not load archived workflow rules as a second active Skill or require every historical audit before writing a small TB.
