# Independent portable H3 software verification assets

These assets target product commit `204192fd69fae45512ca961063f575681697f7b9`
on Draft PR #34. The earlier asset commit `de12773d5dac8f3dd2477dfcc7e9116ef9e47f6f`
tested the original product `5efc4b67ad49de2c2bd99eb38ba8995b6f312289`.
Its first runner incorrectly returned zero on a failing index, and its old
boundary probe called the historic saturating adapter. Both original failures
remain in the first packet; the present runner and probe have new identities.

The claim is a candidate `FUNCTIONAL_SIM` result for portable software and
explicit `SYNTHETIC_TIME` only. Verification assets were written by B-REVIEW,
which may verify a product repair but may not independently approve its own
reference or checker. Production numbers, service latency, RTL handshakes,
recorded acoustics, AMD equivalence, and formal #17 evaluation are outside scope.

## Independent expectations fixed before DUT comparison

The B r2 and P17 contracts require two windows: S24 Hann for DOA and RNE mean
removal followed by S25 Hann for gate. Each of four channels in each domain
runs FFT29, then B14-02 RNE >>4. Signed25 is
`[-2^24,2^24-1]`; either component overflow makes one entire complex `(0,0)`
and sets separate real/imag overflow bits plus `numeric_valid=false`. The
positive S29 codes `2^28-8..2^28-1` overflow; `-2^28` remains valid. Six PHAT
pairs use the frozen 01/02/03/12/13/23 order, guarded Hermitian completion,
conditional IFFT25, lag and DOA/CORDIC. Gate closed still completes all eight
front-end transforms; later pair units are named SKIPPED. Numeric-only data
cannot become fresh. Synthetic-time `available <= commit <= take <= expiry`
and externally visible status are required. HOLD cannot renew Tracker or audio
deadlines. Source sample `n` emits at `n+8` with common coordinates on all
three audio lanes.

`independent_reference.py` implements signed RNE, recursive FFT (different
structure from the DUT's bit-reversed loop), PHAT integer square root and
reciprocal, Hermitian completion, inverse FFT, lag, vector solve and CORDIC.
It imports no DUT or historic leaf. It shares the frozen Hann/twiddle/atan
bytes as explicitly bound inputs; all 2046 twiddle complex values and 24 atan
codes are checked against their formula. Shared ROM bytes do not independently
prove the ROM generator or AMD/RTL implementation. The positive seven-frame
scene is deterministic xorshift32 synthetic PCM, not a real acoustic reference.
`boundary_probe.py` separately checks the new authoritative fixed4 entry
against an integer oracle and isolated output mutations. Its direct overflow
vectors do not claim legal PCM naturally reaches those S29 codes.

For the seven-frame scene, `independent_contract.py` fixes all 53 B14-05/P17
instance names independently of DUT `expected`/`units`. Frames 0–1 require
closed-gate SKIPPED states; frames 2–6 require active states. The active lag
status is derived from the independent inverse-FFT reference, so a physical
TAU_BOUND rejection is allowed only for the corresponding pair. The contract
also constructs one external completion per scheduled `(frame, unit)` and
separate Tracker, result-binding and take events with their own time/result.
Neither the DUT's external-visible summary nor the count of matching events
defines the expected event set.

## Reproduce

Use Python 3.13 and NumPy 2.2.0; the known executable is `D:/Python/python.exe`.
Pass a new output directory each time:

```text
D:/Python/python.exe -B data/fixtures/h3_portable/run_verification.py \
  --repo F:/NUEC/develop --python D:/Python/python.exe \
  --fixed-input-index F:/NUEC/codex_out/i17-h3-assembly-plan-20260928/INPUTS.json \
  --out F:/NUEC/codex_out/<unique-run>/normal
```

The runner records child commands, logs, exit codes, product Git-blob and
worktree byte hashes, source identity, asset hashes, and CLI executed-module
identity. The two JSON manifests can have Git LF and checkout CRLF; both raw
hashes are kept. It stops at a failed child and exits nonzero. The option
`--inject-failure-step reference` is a runner-only negative canary: the child
raises `CONTROLLED_CHILD_FAILURE`, the index says `FAIL_INCOMPLETE`, and the
runner exits 1. This canary never reaches the DUT.

For the first acceptance-asset repair, replay the prior frozen `final02`
results with `checker.py --self-test` and run `asset_repair_canary.py` with
`--saved <prior-final02> --out <new-directory>`. This runs no DUT or reference
generation. The canary uses in-memory copies for missing/extra/duplicate or
incorrect unit and event records, then passes a separately copied, corrupted
result through the actual checker subprocess. The expected failure is nonzero
with no success directory; the prior saved input hashes must remain identical.

## Requirement → Test → Checker → Cover

| Requirement | Test | Checker | Covered scope / limit |
| --- | --- | --- | --- |
| Exact product, dependency and execution identity | runner plus both CLI invocations | raw Git/worktree/source/CLI module hashes; wrong-manifest, missing config and illegal type negatives | fixed commit and local bytes; no remote service identity |
| Dual windows, eight FFT29/fixed4 instances | seven 1024/512 windows | independent RNE/Hann/recursive FFT and complete half spectra | all normal frames; no new AMD proof |
| B14-02 signed boundary, flags and atomicity | direct gate/doa boundary probe | separate integer oracle and five output corruption canaries | real/imag/both overflow, ties, endpoints, bin0/512, neighbor isolation and rejection; no natural PCM overflow claim |
| Error propagation from single domain/channel | test-side one S29 forward-output injection | frame units, gate/Tracker reset, no fresh/successful commit/take, neighbor statuses | injected boundary, not legal PCM reachability |
| PHAT→Hermitian→IFFT→lag→DOA/CORDIC | five active frames, six pairs | independent integer normalization, inverse FFT and direction metadata; PHAT/IFFT/angle canaries | 30 conditional inverses; bounded scene, not all leaf-code space |
| Gate and Tracker normal path | seven-frame CLI and candidate rejection/gap probes | named status closure, SEARCH→ACQUIRE→LOCKED, four fresh; HOLD and expiry/gap checks | synthetic events; injected rejection labelled |
| B14-05 complete instance closure | frozen seven-frame result replay | independent 53-name set, unique declaration, exact per-instance terminal status from fixed scene and independent lags | `I17-H3-V2-01` test-asset repair; no DUT `expected` as oracle |
| External event identity and lifecycle | frozen result replay and mutated CLI subprocess | fixed schedule plus independent external-unit map; exactly one event per `(frame,unit)`, declared time/result, separate Tracker/binding/take categories | `I17-H3-V2-02` test-asset repair; output summary cannot certify its own log |
| TTL, status and priority | event probe | equality, exceeded, zero expiry, overflow, missing/late/error status, fatal>STOP and tail length | declared research schedule; no hardware service bound |
| Three audio lanes and fades | normal CLI plus 6000-sample test-side control scenes | independent Q12 beam/mix for 0°→19°→mono, all emits, source `n`→`n+8`, 480 fades; overlap return at 760 ≤960 samples | no second naturally derived PCM angle or public chunk API |
| Checker and runner sensitivity | seven original in-memory corruptions, five fixed4 corruptions, 19 asset-repair mutations, runner child failure | intended first error and nonzero exit; one corrupted saved result checked in a real subprocess | not exhaustive fault injection |

## Interpretation

The baseline CLI must have genuine active frames and fresh results; zero-fresh
or empty arrays cannot pass this fixture. Positive CLI results and isolated
negative probes are separate. Test-side mutations are not evidence that the
unmodified DUT naturally reaches a fault. The main flow has accepted
`I17-H3-V1-01` as `VERIFIED_CLOSED` only for the portable software boundary.
The new `I17-H3-V2-01/02` checker changes are authored here and remain
`FIXED_PENDING_REVIEW`; they do not self-approve the acceptance assets.

## I17-H3-R-01 cancellation increment

`cancel_contract.py` derives the publication queue from the frozen schedule,
the predeclared 53-unit set and the existing independent integer reference.
`cancel_checker.py` checks exact event rows, same-edge observations, transaction
identity, 53-unit termination partition, earlier terminal values, and prior
commit/take history. It does not import the composer or derive its oracle from
DUT event/termination fields. `cancel_runner.py` checks the original A saved
fixture hashes, records the manifest rebind as new local bytes, and invokes the
authority CLI plus checker for 12 bounded schedules. `cancel_canary.py` submits
isolated corrupted result copies through real checker subprocesses; the
runner's `--only-case fatal2561 --inject-checker-failure` is an isolated
failure-propagation canary and must exit nonzero. `cancel_audio_check.py`
compares saved CLI sample prefixes, fatal hard cuts and STOP completion against
the no-cancel run. The old `event_probe.py` remains connected with the new
termination reason and frame suppression fields.

Example, using a new output directory and the fixed A input files:

```text
D:/Python/python.exe -B data/fixtures/h3_portable/cancel_runner.py \
  --repo F:/NUEC/develop --python D:/Python/python.exe \
  --source-fixture F:/NUEC/codex_out/i17-r01-receipt-20260928/inputs/inputs/final02 \
  --reference F:/NUEC/codex_out/i17-portable-independent-v2-20260928-172100/final02/reference/expected-stages.npz \
  --out F:/NUEC/codex_out/<unique-run>/cancel
```

The reference path is a previously frozen B independent reference, not a DUT
output. A receiving machine must carry or regenerate that reference using
`independent_reference.py` and the fixed table identities. The full normal
runner checks 119 arrays, five direction frames and three audio lanes on the
current product candidate. The four-frame STOP window is too short to prove
all 480 fade samples; the separate 6000-sample `audio_probe.py` supplies that
bounded Q12 check. These are portable software and synthetic-time claims only.

No public portable chunk API is present. The audio composition consumes one
real source sample at each emit and only zero-pads real record boundaries;
the synthetic source join at sample 4096 is checked without an inserted zero.
The underlying old DynamicDAS leaf's chunk behavior is a shared dependency,
not reapproved here. Timing is in source/visible/commit/take/emit sample
coordinates, never RTL clock cycles. All new reference/checker code still
requires a different technical reviewer and real A-member acceptance.
