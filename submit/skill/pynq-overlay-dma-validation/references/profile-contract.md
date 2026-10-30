# Validation profile contract

The actual `register_contract.ip_name` and `dma_contract.ip_name` must resolve
to MODULE instances in the same hash-validated HWH, independently of
`overlay.required_ip`. Prefer HWH FULLNAME (without its leading slash), otherwise
INSTANCE/NAME; hierarchical paths must be complete. A port, parameter name,
module type or mere suffix match is not an instance binding. In run evidence,
`dma_runs` IDs must be unique non-empty strings: any duplicate is an error,
regardless of order or whether one or both records indicate success.

## Purpose

This full JSON profile supplies artifact/board identity and loopback acceptance
inputs. Scripts must not derive a board, address, transfer size or payload layout
from filenames. The separate [lifecycle contract](lifecycle-contract.md) exercises
receive-only or loopback mocks without pretending a deployable profile exists.
Do not feed its reports to this profile's evidence validator.

## Required top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Contract version; current value is `1` |
| `profile_id` | Stable, portable identifier |
| `board` | Expected board/device/PYNQ environment |
| `overlay` | `.bit`, `.hwh`, manifest, and required HWH-visible IP |
| `register_contract` | AXI4-Lite IP and register definitions |
| `dma_contract` | DMA instance, channels, geometry, cache and TLAST rules |
| `self_tests` | Bounded loopback tests safe for this design |
| `acceptance` | Golden, performance, timing, and resource criteria |

Unknown values must be `null` or absent during drafting. `validate_profile.py` treats required unknowns as errors; do not invent placeholders to make the validator pass.

## Board

```json
{
  "profile_id": "vendor-board-overlay-v1",
  "board": {
    "board_name": "vendor-board-revision",
    "board_revision": "revision",
    "device_part": "full-vivado-part",
    "pynq_image": "image-version",
    "compatibility_contains": ["device-tree-token"]
  }
}
```

Use the full Vivado part when known, including package and speed grade. A device family alone is insufficient for board acceptance.

## Overlay and manifest

Paths are resolved relative to the profile. Absolute paths are accepted for laboratory runs but produce a portability warning.

```json
{
  "overlay": {
    "bit": "artifacts/design.bit",
    "hwh": "artifacts/design.hwh",
    "manifest": "artifacts/build-manifest.json",
    "build_id": "build-identifier",
    "interface_version": 3,
    "vivado_version": "2025.2",
    "required_ip": ["control_regs", "axi_dma_0"],
    "required_interrupts": ["dma_irq"]
  }
}
```

The manifest must contain:

```json
{
  "build_id": "build-identifier",
  "interface_version": 3,
  "vivado_version": "2025.2",
  "device_part": "full-vivado-part",
  "bit_sha256": "64-lowercase-hex",
  "hwh_sha256": "64-lowercase-hex"
}
```

The validator compares actual files with these hashes and compares identity fields with the profile. Matching basenames alone are not proof of a common build.

List only interrupts the design contract actually uses. An empty `required_interrupts` list is valid for polling-only designs; used interrupts must remain part of the backend-neutral event contract.

## Register contract

```json
{
  "register_contract": {
    "ip_name": "control_regs",
    "address_span_bytes": 4096,
    "registers": [
      {"name": "hardware_id", "offset": 0, "width_bits": 32, "access": "ro"},
      {"name": "interface_version", "offset": 4, "width_bits": 32, "access": "ro"}
    ],
    "identity": [
      {"register": "hardware_id", "expected": 305419896, "mask": 4294967295},
      {"register": "interface_version", "expected": 3, "mask": 4294967295}
    ]
  }
}
```

Offsets are byte offsets, must be unique and word-aligned, and must fit the declared address span. v0 supports only 32-bit registers. `access` is one of `ro`, `rw`, `wo`, `w1c`, or `rc`, but identity entries must reference side-effect-free `ro` registers with a nonzero 32-bit mask. Wider or side-effecting identity access requires a separately reviewed adapter. The bundled PYNQ probe is currently disabled; it does not prove register writes, atomic commit or interrupt delivery.

The `.bit` and `.hwh` must share both basename and parent directory. Hash matching
proves file consistency with the supplied manifest, not that a mock bitstream is
deployable or that the manifest is authentic. HWH checks are inventory-level;
address windows, IP parameters and real device identity need independent review.

## DMA contract

```json
{
  "dma_contract": {
    "ip_name": "axi_dma_0",
    "mode": "simple",
    "mm2s_channel": "sendchannel",
    "s2mm_channel": "recvchannel",
    "stream_data_width_bits": 32,
    "buffer_alignment_bytes": 64,
    "length_granularity_bytes": 4,
    "max_transfer_bytes": 1048576,
    "cache_policy": {"tx": "flush", "rx": "invalidate"},
    "tlast_required": true,
    "status_offsets": {"mm2s": 4, "s2mm": 52}
  }
}
```

The stream width must be byte-addressable. Test lengths must be multiples of the
stream beat and `length_granularity_bytes` (defaults to stream beat for older
profiles). Buffer alignment constrains addresses, not packet lengths: a 96-byte
transfer may use a 64-byte-aligned buffer. This profile still restricts transfers
to whole stream beats; partial TKEEP/DRE packets need a reviewed extension.
`cache_policy` is mandatory even on a coherent platform: use `coherent` only when
the documentation and actual allocation path prove coherency. RX CPU initialization
must be flushed/invalidated before arm, then RX invalidated after completion.

`status_offsets` is optional metadata for a future reviewed adapter, valid only
when confirmed for the instantiated IP. No supplied script reads these offsets.

`simple` and `sg` are accepted contract labels, not claims of driver support.
The old unqualified probe was removed; the board entrypoint only refuses access.
This full profile still requires MM2S/S2MM and loopback, while the independent
offline lifecycle contract supports receive-only tests. Do not invent a channel
to fit this profile. Never silently round requested lengths to make a test pass.

## Self-tests

The full-profile validator accepts exact byte loopback test declarations:

```json
{
  "self_tests": [
    {
      "id": "counter-loopback-4k",
      "kind": "loopback",
      "length_bytes": 4096,
      "pattern": "counter8",
      "timeout_seconds": 2.0,
      "golden": "exact"
    }
  ]
}
```

Supported patterns are `counter8`, `alternating`, and `xorshift32`. A loopback is valid only when the loaded PL design deliberately routes MM2S output to S2MM input or through a deterministic function represented by another runner. Do not run the generic loopback against a physical actuator or an unbounded acquisition stream.

## Acceptance and evidence

```json
{
  "acceptance": {
    "minimum_throughput_bytes_per_second": 1000000,
    "maximum_latency_seconds": 0.05,
    "timing": {"minimum_wns_ns": 0.0},
    "resources": {"lut_max": 20000, "ff_max": 30000, "bram_max": 100, "dsp_max": 100}
  }
}
```

For externally supplied evidence, timing/resource sections have this form (the
protected board entrypoint does not collect them):

```json
{
  "timing": {"wns_ns": 0.125, "source": "reports/timing_summary.rpt"},
  "resources": {
    "lut": 1234,
    "ff": 2345,
    "bram": 12,
    "dsp": 8,
    "source": "reports/utilization.rpt"
  }
}
```

Evidence JSON provides `performance`, `timing`, and `resources`; each section must name its source, and source report hashes belong in the final archive. A hardware run must additionally contain `evidence_level: hardware`, `overlay_downloaded: true`, board observation, actual artifact hashes, identity register reads, cache-operation records, and one result per declared self-test.

Do not place algorithm-specific channel order, fixed-point format, or frame metadata in the generic DMA contract. Put those fields in a project payload schema and hash/reference that schema from the build or experiment manifest.
