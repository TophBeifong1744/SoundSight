# Validation status - 2026-09-13

## Current outcome

Offline implementation and author regression only: **50 tests passed** on
Python 3.14; skill-creator quick_validate passed; Python 3.8 syntax parsing,
JSON parsing, English-path and scoped whitespace checks passed. Python 3.8
runtime compatibility was not executed.

No board was contacted, no Overlay was downloaded, and no real DMA, Vivado
implementation or physical performance measurement was performed. The supplied
[evidence report](../evidence/offline-2026-09-13.json) binds the actual regression
to source hashes. It is not B acceptance or merge approval.

An [independent forward trial](../evidence/forward-test-2026-09-13.json) exercised
104-byte receive/loopback and seven injected failure cases. It found the large
integer golden false PASS; after correction the same inputs correctly returned
FAIL with one differing value, and the independent agent reran all 50 tests
(39 subtests) successfully. The archived summary keeps initial and corrected
observations distinct. This extra skill-creator check is not team B acceptance.

## What changed beyond the board guard

| Demonstrated risk | Executable correction and test |
|---|---|
| RX allocation fails after TX allocation | Own each allocation immediately; release TX once |
| RX starts, then RX/TX call raises or cancellation arrives | Mark possibly active before first arm; capture status; abort only if authorized |
| Timeout or abort/status failure | Bounded deadline plus poll budget; retain buffers unless fresh quiescence is proven |
| Stale/missing status or swallowed flag-read error | Require transaction-bound typed flags/error/raw status; never default to success |
| Adapter reuses a mutable status dictionary | Deep-copy observations so abort cannot overwrite pre-abort evidence; reproduced failing test before correction |
| Completion without whole-path quiescence | Do not read/free; deadline and fail-stop |
| Short output despite adequate capacity | Compare actual received count, not allocation length; stop before CPU read |
| RX initialized dirty, TX stale, RX cache stale | Prepare RX before DMA, flush TX, invalidate RX after completion; separate CPU/device byte model |
| False coherent declaration | Require allocator-confirmed coherent memory |
| Golden mismatch | Record first mismatch/hash; fail and block later tests |
| Repeated success reuses stale completion | Fresh sequence, rearm and multiple successful iterations |
| Allocator returns duplicate/overlapping buffers | Reject before DMA; no duplicate release |
| Release exception | Mark indeterminate, hold reference, block retry rather than double free |
| Packet length confused with buffer address alignment | Separate length granularity; 96-byte packets on 64-byte-aligned addresses tested |
| Large integer golden values round to the same float | Independent trial reproduced false PASS; preserve JSON integers and compare with exact rational arithmetic, including tolerance-overflow regression |
| Unsafe dormant board prototype | Remove it; keep protected entrypoint and move reusable mechanics into the tested offline core |

The mock covers receive-only and loopback at 8/96/512/4096 bytes; it accepts
project lengths, not these constants as limits. Tests include fault combinations
and subcases; the headline count is unittest test methods, not physical runs.

The full-profile validator also retains synthetic bit/HWH/manifest, hash tamper,
RO identity access, width/mask, finite-number, malformed evidence, golden and
second-board-profile regressions. The two synthetic board profiles use different
device/IP/register/stream settings with unchanged code. This proves parameterized
software reuse only.

## Reproduction

From the Skill directory:

```sh
python -B scripts/run_offline_tests.py --output results/retest.json
python -B scripts/simulate_dma.py --contract references/example-session.json --output results/receive.json
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout --output results/retained.json
python -B <skill-creator>/scripts/quick_validate.py .
```

The third command intentionally returns 1. Use fresh output filenames.
System quick_validate needs PyYAML; all delivered runtime scripts/tests use the
standard library. Test reports include environment, source/test/example hashes,
per-test status and explicit NOT_RUN hardware categories.

[Input audit](input-audit.md) contains current_build, compiled PS and HWH sources
and their hashes. No rebuilding or automatic profile generation was performed.
Full-profile loopback validation must not be used to invent missing MM2S or
identity registers in the current receive-only project.

## Remaining board work

See [hardware-runbook.md](hardware-runbook.md) for actual admission and testing:

- pin physical board identity, PYNQ image, same-build deployable bit/HWH/manifest;
- qualify allocator/cache-line isolation and actual driver completion/count/error;
- qualify source stop, bounded abort, whole-path quiescence and process lifetime;
- test real single-direction capture, authorized loopback only on a matching design,
  TLAST/short output, register side effects, interrupts, repeated runs and long-run;
- compare externally supplied algorithm golden data and original captures;
- measure real latency/throughput; bind original timing/resource reports to build.

Synthetic timing is not a hardware benchmark. TLAST is null in lifecycle reports.
Evidence JSON is unsigned: a label, hash or source filename does not authenticate
physical measurement. PL real-time operation remains Python-independent.

## Historical baseline and contest mapping

2026-09-12 baseline: 13 host tests passed and the unqualified board prototype was
guarded. That snapshot identified lifecycle/cache gaps; the present revision
implements and tests their portable software portion, while real-driver
qualification remains open. Do not describe the guard as the implementation.

Repository AMD selection guide, printed pages 19-21 (PDF pages 22-24), sections
3.3.2 and 3.3.5.2: reusable Overlay/register/DMA/golden/evidence tooling,
usage/failure conditions, and applicability beyond the team's topic. No fixed
bonus is guaranteed. Report the actual offline tests, failure injection, second
synthetic profile and board gaps; do not claim completed PYNQ migration or measured
FPGA acceleration. [B handoff](review-handoff.md) defines the independent review.
