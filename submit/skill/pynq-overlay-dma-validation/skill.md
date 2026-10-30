---
name: pynq-overlay-dma-validation
description: Audit PYNQ Overlay artifacts and AXI4-Lite/DMA contracts, exercise DMA ownership and failure paths with offline mocks, compare golden data, and prepare evidence-gated board acceptance. Use for Overlay/DMA validation or diagnosis; the bundled release does not execute real hardware.
---

# PYNQ Overlay DMA Validation

Current capability: offline artifact checks and executable mock DMA lifecycle
tests. Board execution is protected; no PYNQ hardware adapter is delivered.
Do not remove the protection to produce a demonstration.

Keep board identity, IP names, registers, lengths, payload semantics and limits
in project inputs. Do not infer them from a board/project name. PYNQ is a
replaceable control/validation backend; the real-time PL algorithm must not depend
on Python. AXI4-Lite, AXI DMA and interrupt contracts also serve Vitis/PetaLinux.

## Choose the task and inputs

- **Existing-project audit:** read the current build, exported hardware metadata
  and compiled PS contract without rebuilding. Separate software declarations
  from physical observations. For the SoundSight input snapshot only, see
  [input-audit.md](references/input-audit.md); do not copy its constants into code.
- **Artifact/profile checks:** read [profile-contract.md](references/profile-contract.md).
  Supply the board profile, same-build bit/HWH/manifest, register contract,
  self-test and acceptance limits. This v1 full profile describes loopback,
  not arbitrary receive-only hardware; missing identity or MM2S is a gap, not
  permission to invent an IP or channel.
- **Offline DMA lifecycle:** read [lifecycle-contract.md](references/lifecycle-contract.md).
  Supply a transfer contract and exact expected bytes; loopback also takes TX
  bytes. This mode needs no board, PYNQ image or deployable bitstream. It supports
  receive-only and loopback mocks, not SG/cyclic or physical capture.
- **Board acceptance planning:** read [hardware-runbook.md](references/hardware-runbook.md).
  A separately reviewed, version-pinned adapter and explicit authorization are
  required before hardware mutation. The bundled board entrypoint always stops.

## Offline execution

Paths below are relative to the Skill directory. Runtime uses Python standard
library only (tested Python 3.14; Python 3.8 syntax checked, not runtime-tested).

```sh
python -B scripts/simulate_dma.py --contract references/example-session.json --output results/mock-receive.json
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output results/mock-timeout.json
python -B scripts/run_offline_tests.py --output results/offline-tests.json
python -B scripts/validate_profile.py --profile <project-profile.json> --mode offline --output <static-report.json>
python -B scripts/compare_golden.py --expected <golden.bin> --actual <capture.bin> --format bytes --output <comparison.json>
```

The injected timeout command should exit 1 with FAIL and retained buffers.
Use new report filenames. The session simulator and test runner refuse overwrite;
the older profile/golden tools require the caller to select fresh output paths.

Do not feed lifecycle reports to the full-profile evidence validator: they are
different schemas. A mock duration is a synthetic clock value, never measured
throughput. For transformed payloads use an external golden model/schema;
`compare_golden.py` compares files, it does not invent an algorithm reference.
Numeric tolerance must come from that schema, not be enlarged after failure.
JSON integers retain exact precision; decimal/exponent literals use binary64
parsing. Use an external exact-decimal model if that distinction matters.

## Ownership and stopping rules

The executable mock core owns each allocation immediately, marks a transfer
possibly active **before** RX submission, and does not read or release DMA-owned
buffers. Prepare dirty RX cache lines before arm; flush TX after fill; invalidate
RX after validated completion and before CPU comparison. Coherent policies
require allocator confirmation.

On timeout, partial start, status/cache/length error, cancellation or golden
mismatch: fail the session and do not start another test. Preserve the primary
failure and pre-abort raw status. Request abort only when the transfer contract
authorizes it; release only after fresh, transaction-bound quiescence proof.
Otherwise retain ownership. Failed release is indeterminate and must not be
retried blindly. Strong references alone do not make hardware process exit safe.

Stop before board access if board/image/DDR support, exact device/build identity,
register side effects, DMA geometry/cache/TLAST, safe source/sink, or recovery
scope is unresolved. Never reset the whole PL as an inferred recovery step.
An admission gap blocks board execution, not unrelated offline development.

## Evidence and outputs

- `static`: schema/hash/inventory checks; does not prove bitstream deployability.
- `mock`: executable synthetic memory/transfer tests; no board observation.
- `hardware`: requires actual named board/image/build, raw logs and measurements.
  A supplied JSON label or `validate_profile.py --mode hardware` cannot
  authenticate that provenance. Review original logs/reports independently.

Deliver PASS/FAIL reports with sources/hashes, errors, actual lengths, cache
events, snapshots, ownership disposition and unresolved items. Report real
DMA timing, PL cycle latency, resource/timing closure and system continuity
separately; missing measurements remain NOT_RUN, not zero or PASS.

Read [validation-status.md](references/validation-status.md) for the checked
release and [review-handoff.md](references/review-handoff.md) when handing it
to a reviewer. Author tests are not B acceptance or permission to merge.
