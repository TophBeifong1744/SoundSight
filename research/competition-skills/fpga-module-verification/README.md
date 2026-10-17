# FPGA module development and verification Skill

2026-09-14 S1 repair candidate (on top of 0.3.0): B found that ordered
transaction comparisons did not enforce the one-edge/one-slot contract.
The TB now checks occupancy, valid, ready and valid payload before/after each
edge, plus reset-discard accounting. The original two-stage mutant still
reproduces the old false PASS (1149 checks); the repaired TB rejects it at
cycle 2 after the first accepted edge. Correct/restored elastic runs pass
13800 actual checks, not the historical 1125 below. The runner retains data
and ready faults and adds a two-stage fault. See the [S1 repair handoff](../../task-packages/PKG-A-SKILLS/REPAIR-S1.md)
for commands, fresh logs and scope. Author regression is not B approval;
historical source manifests/logs remain unchanged and refer to their old SHA.

SKL-001, technical candidate 0.3.0; author A, independent reviewer B pending. Supersedes the workflow-only `soundsight-engineering-workflow`; its original v0 and unreviewed 0.2.0 package remain in the [upgrade archive](../../archive/2026-09-13-before-skl001-technical-upgrade/README.md), not as a second active Skill. This source directory is a working candidate, not approved production RTL or a published main release.

## Purpose and use

Use [SKILL.md](SKILL.md) to develop/debug a bounded module: interface and numeric contract → RTL → independently justified self-checking TB → actual XSim execution → first-failure analysis → scoped correction and retest. Team review rules support this technical loop; they are no longer the main product.

Give the agent the module request, allowed edit paths, existing sources/contract and simulator version. It should read the Skill and relevant reference, implement only the requested scope, then return code, actual commands/results and limitations. For an unfamiliar team, use the standalone non-acoustic elastic example. The PCM example deliberately references the team's existing C-authored module and needs the repository (or an attributed export of that single source).

From the repository root with Python 3.10+ and Vivado 2025.2:

```text
python -B -m unittest discover -s skill/fpga-module-verification/tests -v
python -B skill/fpga-module-verification/scripts/run_examples.py --vivado-bin F:/AMD/2025.2/Vivado/bin --output task-packages/PKG-A-SKILLS/evidence/xsim-new
```

Use a new output directory. Replace the explicit tool path for another installation; do not accidentally use an older PATH version. The runner supports standalone `.v`/`.sv`, not VHDL, IP simulation libraries or arbitrary Tcl projects. It opens no existing Vivado project and does not synthesize, constrain or program hardware. No external subSkill is required; all Python runtime helpers use the standard library.

## Verified effect and failures

On Windows/Python 3.12.14 and actual Vivado XSim 2025.2, author tests produced (the system Skill validator separately used Python 3.14.6):

| Run | Actual result | What this supports |
| --- | --- | --- |
| Existing pcm4_signext_pack, widths2/24/32 | PASS, 792 word comparisons | Interface/sign-extension test on a real project module; not room acoustics |
| Non-acoustic elastic stage, widths1/8/16 | PASS, 1125 checks | Contract/TB/runner reuse across a different module; stall/reset/full-rate behavior |
| Deliberately flip one output bit in a disposable DUT | FAIL at first compared transaction | TB detects this data fault; failure is expected test evidence |
| Deliberately prevent empty-stage acceptance | FAIL at empty acceptance | Directed contract check detects a throughput/handshake defect |
| Restore the correct DUT, unchanged test inputs | PASS, 1125 checks | Fault evidence preserved and same-case retest executes |

Raw commands, source snapshots, first failures and result hashes are in [the task package](../../task-packages/PKG-A-SKILLS/README.md). Runner unit tests also check absent/duplicate PASS, late fatal, zero checks, wrong version, failed tools, missing input, timeout classification and refusing old output directories. These are author software tests, not independent B review or a held-out agent benchmark. Windows was executed; other OS/Python versions are not certified.

## Derivation and own contribution

- The user identified that the old Skill mostly said what evidence should exist without teaching/executing the RTL/TB work. The correction is a narrow technical workflow, actual runner and two reproducible module examples; old evidence was archived unchanged rather than relabeled as new technical validation.
- Existing project work established separate compile/elaborate/run records and source manifests. This candidate generalizes the case configuration, requires positive assertions, keeps the first failure and refuses stale output directories. It does not infer hardware success from a log or a push.
- The two deliberate faults demonstrate why data comparison alone is insufficient: the second needs an explicit acceptance/throughput assertion. The failures were intentionally injected, not falsely described as historical field defects.
- Structural/static validation is not behavioral quality. B still needs an unfamiliar module/request, a held-out fault and actual use without this chat. No percentage improvement in AI productivity or token use is claimed.

## Limits, ownership and license

Single-clock/combination module workflow only. CDC, full AXI protocol, vendor-IP libraries, fixed-point algorithm derivation, synthesis/timing/board acceptance and full-system integration need additional task-specific work. The elastic example is a reference module, not a production replacement. It has combinational ready, not a registered-ready timing guarantee.

Owned new files follow the repository MIT license. Existing PCM module belongs to C's credited C-RTL-003 work and is referenced without duplicating its maintained source. The system skill-creator and xilinx-suite were authoring aids, not copied dependencies or the team's original contribution. No third-party Skill scripts were installed or incorporated.

For contest submission, README scope/use/failure/provenance/effect records are required. Preserve visible user/AI corrections in the task report; never submit hidden reasoning. Use the [submission naming/export rule](../../docs/skills-delivery-plan.md) and test the actual exported package. A static Skill check, author demonstration, B approval and main publication are separate states.
