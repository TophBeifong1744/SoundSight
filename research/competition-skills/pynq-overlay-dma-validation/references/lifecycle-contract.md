# Offline DMA lifecycle contract

This contract exercises software decisions, not PYNQ APIs. It is separate from
the full artifact/profile schema. No board name, register offset or payload layout
is embedded in the lifecycle core. See [example-session.json](example-session.json)
for a runnable, synthetic receive-only example.

## Inputs

`simulate_dma.py` takes JSON containing `schema_version: 1`, `pattern`, `mock_coherent` (boolean) and
`transfer`. Patterns are counter8, alternating and xorshift32 (fixed reproducible
seed 0x6D2B79F5, little-endian words). They are test stimuli, not an algorithm model.

| Transfer field | Meaning |
|---|---|
| mode | receive (RX only) or loopback (RX then TX) |
| length_bytes | Exact expected/requested bytes for this one transfer |
| buffer_alignment_bytes | Allocator device-address multiple; not packet size |
| length_granularity_bytes | Transfer-length multiple, derived externally from the real interface |
| max_transfer_bytes | Per-transaction limit, not total capture capacity |
| timeout_seconds / abort_timeout_seconds | Separate finite positive deadlines, each at most 60 seconds |
| allow_abort | Explicit authority for the mock abort operation, default false; never authority for a physical reset |
| tx_policy / rx_policy | flush/coherent and invalidate/coherent respectively |
| poll_interval_seconds / max_polls | Positive interval and independent positive integer poll budget |

Integers reject booleans. Length must be positive, within the maximum and a
multiple of the length granularity. No silent rounding. The real board's DRE,
memory/stream width, TKEEP, burst and maximum-length rules must be translated
into this input by a reviewed adapter; the mock cannot discover them.

Direct callers use `DmaSession.run(spec, expected=bytes, tx_data=bytes)`.
Expected bytes must match length exactly; TX is mandatory for loopback and
forbidden for receive. This enables external golden data without hard-coding
SoundSight's eight-word groups or another algorithm's format.

## Mock adapter boundary

All methods must be synchronous and nonblocking except the controlled clock
sleep. The deadline cannot interrupt a blocked driver call; therefore passing
these tests does not qualify a real PYNQ API. Only adapters labeled `mock` are
accepted and every session report has `evidence_level=mock`,
`board_execution=false`. Labels are not a security sandbox or attestation:
review adapter code, not just its label.

- `allocate(role, length)` returns a new buffer with role, nbytes,
  device_address and boolean coherent. Returning the same object or overlapping
  ranges is rejected. Allocation failure before return must be cleaned up by
  the allocator; the session cannot own an object it never received.
- Buffer methods: `write_bytes`, `flush`, `invalidate`, `read_bytes`,
  `release`. CPU operations and release are forbidden while DMA owns memory.
  Independent allocations must not share cache lines or aliases; actual allocator
  cache-line isolation is still a hardware-adapter qualification item.
- `arm_receive(buffer, length, transaction_id)`, then for loopback
  `arm_send(...)`. Either may start hardware-equivalent activity before raising.
- `snapshot()` returns a transaction-bound dictionary: exact integer
  transaction_id, boolean rx_completed/tx_completed/quiescent, error (null or
  string), raw_status dictionary and actual_bytes. Missing flags never default
  to success. For receive-only, TX completion is false and ignored for completion.
- Quiescence means **all masters that can access these buffers are stopped**,
  not just one channel's idle flag. A real adapter must reconcile driver
  bookkeeping, bus completion and source/sink behavior before returning it.
- `request_abort()` only requests stop. Fresh, bounded status observations
  must establish quiescence. An exception or inability to prove quiescence
  leaves allocations retained and the session blocked.

## Ownership sequence

CPU fill -> TX flush and RX flush/invalidate -> possible DMA ownership before RX
submission -> completion + quiescence + actual-count check -> RX invalidate ->
CPU golden comparison -> one release per allocation.

If a transfer may have started, capture pre-abort status first; retain primary
and diagnostic errors separately. Request abort only with authority. Failure
never becomes PASS after successful recovery. Golden mismatch also blocks later
tests. Any release exception is indeterminate (it might already have freed
memory), so do not retry it. Strong references in `retained_buffers` model an
obligation, **not safe lifetime across Python garbage collection or process
exit on real hardware**. Production supervision/recovery remains unimplemented.

The mock keeps CPU and device bytes separately and simulates dirty RX eviction.
No-op cache faults therefore change compared bytes rather than merely flipping
a canned success flag. Coherent mode shares memory only when confirmed by the
mock allocator. Repeated successful calls get fresh transaction IDs.

## Reports and reproducibility

A report contains requested/actual lengths, errors, stage/cache events, raw
snapshots, buffer disposition, mismatch count/first offset and input/output
hashes. The simulator adds contract hash, injected faults and adapter trace.
Tests bind their results to script/test/example hashes.

Synthetic duration/throughput values are for exercising report logic only.
TLAST remains null: neither a mock completion flag nor a real S2MM completion
alone is a waveform proof. Failed runs report no throughput. Resource/timing
claims require separate original reports.

The simulator and test runner return 0 for PASS and nonzero for FAIL/invalid
input. New output filenames are required; existing evidence is not overwritten.
The protected board entrypoint exits before file reads, PYNQ import or allocation.

Useful fault experiments:

```sh
python -B scripts/simulate_dma.py --contract references/example-session.json --fault short-output
python -B scripts/simulate_dma.py --contract references/example-session.json --fault rx-invalidate-noop
python -B scripts/simulate_dma.py --contract references/example-session.json --fault timeout --fault abort-timeout
```

These should fail respectively on actual byte count, real cache-byte mismatch,
and bounded recovery with retained buffers. Unit tests additionally exercise
partial startup, cancellation, allocator aliasing, stale/unreadable status and
release failure.
