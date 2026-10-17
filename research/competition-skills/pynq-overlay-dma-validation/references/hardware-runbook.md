# Board runbook and failure map

**v0 stop:** no board adapter is delivered. The offline ownership implementation
and fault tests are executable, but only against a mock. Qualify the actual driver
binding below before replacing the protected board entrypoint. These are future
acceptance steps, not completed results. See [validation-status.md](validation-status.md).

## Admission gate

Before `--download`, confirm all of the following from actual evidence:

- exact board revision and full device part, including speed grade;
- a reproducible PYNQ image or board support package compatible with the board DDR/MIO/boot design;
- working DDR and a supported contiguous-buffer allocator;
- `.bit`, `.hwh`, and manifest hashes from one build and a compatible Vivado/PYNQ flow;
- authoritative AXI4-Lite identity/control semantics and a bounded safe source/sink;
- actual DMA direction, mode, DRE, widths, length-field and memory-map parameters;
- for loopback, an actual MM2S-to-S2MM route; for receive-only, a controllable
  bounded source with no invented MM2S channel;
- no test path can backpressure or disturb a live physical acquisition stream.

If one item is unknown, remain in offline mode. If PYNQ admission fails within the project schedule, keep the same register/DMA/interrupt contract and use a Vitis or PetaLinux runner.

## Safe execution order

1. Archive the current PL/application state and disconnect unsafe physical outputs.
2. Run offline validation and record the report hash.
3. Parse the Overlay without download and inspect `ip_dict`.
4. Download only after board/device/build/interface identity is consistent.
5. Read identity registers before any write.
6. Allocate only needed channels' buffers, proving address range/alignment,
   capacity, non-overlap and cache-line isolation. Immediately own each allocation.
7. Fill TX if present and initialize RX; flush TX and flush/invalidate dirty RX
   before arm unless allocation coherency is proven. Mark possible DMA ownership
   before S2MM submission; then start MM2S only for the actual loopback topology.
8. Use fresh transaction-bound completion, raw error status and whole-path
   quiescence with bounded driver calls; reconcile driver bookkeeping across
   repeated runs. On any error/timeout/cancellation, capture status before abort.
9. Verify actual received bytes (not capacity), then invalidate RX before CPU
   comparison. Prove CPU/other core/other master exclusion during DMA ownership.
10. Compare exact bytes or the declared golden result; record mismatch count and first mismatch.
11. Record byte count, elapsed time, throughput, latency, cache operations, statuses, environment, and hashes.
12. Release buffers only after both DMA channels are demonstrably quiescent.
    On partial startup, timeout or MMIO failure, retain ownership until an
    authorized, bounded abort proves that no bus master can access them. Simply
    exiting Python or skipping `freebuffer()` is not a safe lifetime guarantee.
    Recovery/reset is a separate, contract-authorized action.

For sustained paths, repeat across minimum, typical, maximum-safe, and non-power-of-two lengths allowed by the contract. Then perform long-run testing with sequence IDs and overflow counters. A loopback alone does not prove continuous sensor capture.

## Real-adapter qualification still required

- Pin PYNQ, allocator and DMA-driver versions; inspect the exact API's completion,
  actual-count, cache and repeated-transfer semantics. Do not map an idle flag to
  the mock's stronger quiescence guarantee without proof.
- Establish bounded status and abort behavior, reset scope and source shutdown;
  a deadline around polling cannot interrupt a blocking driver call. Never
  automatically reset the whole PL. Prove buffer lifetime across process failure,
  not just omission of freebuffer or retained Python references.
- Exercise partial arm failure, missing/early TLAST, short output, DMA errors,
  timeout, cache failure, cancellation and recovery under a safe test design.
  TLAST needs stream/ILA or equivalent direct evidence; completion alone is indirect.
- Test RO identity and authorized RW/atomic commit separately; prove actual
  interrupt events if required, not just HWH interrupt inventory. Polling-only
  contracts need not invent an interrupt requirement.
- Retain raw bytes, packet counts, patterns/seeds, hashes, addresses and command
  logs. Record repeated-run latency percentiles and payload throughput with timing
  boundaries for allocation/cache/copies/transfer/I/O; host polling is not PL cycles.
- Bind WNS/WHS, unconstrained-path review and utilization to the exact Vivado build
  and original report hashes. The Skill checks supplied numbers; it neither runs
  Vivado nor authenticates those reports.

## Competition requirement and typical-failure map

| Requirement or observation | Likely failure | Evidence to capture | Stop/fix direction |
|---|---|---|---|
| Overlay loads but IP names are absent | mismatched or stale HWH | bit/hwh hashes, `ip_dict`, build ID | stop; regenerate a matched artifact set |
| Identity read differs | wrong Overlay, address map, or interface version | HWH address, raw register read, manifest | stop before writes |
| MM2S completes, S2MM hangs | missing TLAST or stream path not connected | both DMA statuses, ILA TVALID/TREADY/TLAST | stop on deadline; inspect producer TLAST |
| S2MM completes with stale/zero data | RX cache not invalidated or wrong ownership | executed cache ops, buffer addresses, before/after bytes | fix ownership and invalidate timing |
| Hardware sees stale TX data | TX cache not flushed | TX fill/hash, flush record, ILA payload | flush after fill and before transfer |
| DMA reports internal/slave/decode error | bad address, interconnect, reset, or descriptor | raw DMASR, addresses/ranges, reset state | capture first; recover only per contract |
| Transfer rejected or truncated | length exceeds IP limit or violates beat/alignment | requested/actual lengths, width/alignment | correct profile or design; never silently round |
| Small tests pass, long tests fail | ring/descriptor/cache/overflow issue | sequence IDs, counters, per-block timing | add stress matrix and explicit loss policy |
| Golden compare fails without DMA error | payload format, byte order, transformation, or stale cache | first mismatch, input/output hashes, schema version | locate first semantic disagreement |
| Throughput varies or misses deadline | Linux scheduling, copies, DDR contention, or PL stalls | distribution across repeated runs, ILA stalls | separate control-plane jitter from PL timing |
| Notebook display looks correct | insufficient acceptance evidence | raw evidence JSON, reports, logs | do not claim hardware acceptance |

## Evidence claims

Use exact wording:

- **Offline validated:** profile, artifacts, contracts, and supplied reports passed static checks.
- **Mock validated:** host-side logic passed deterministic synthetic tests.
- **Board loopback passed:** named board, image, Overlay build, transfer sizes, and repetition count passed recorded loopback.
- **System path passed:** only after the real source/sink, long-run continuity, errors, performance, and recovery behavior are measured.

Never turn the first three into “the whole system passed.” Report RTL simulation, timing/CDC, board loopback, and application measurements independently.
