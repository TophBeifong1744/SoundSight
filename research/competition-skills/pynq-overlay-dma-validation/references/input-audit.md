# Read-only project input audit - 2026-09-13

This is a SoundSight case study, **not a generic default profile**. Only local
files were read. No current_build/Vivado/Vitis build, PYNQ command, board download
or physical measurement was performed for this audit.

## Inspected sources

Repository-relative inspection root:
`task-packages/PKG-A-ACQ/tasks/four-channel-diagnostic-01/current_build/`.

Read its README and `ps_contract.py`, plus its nested
`repair_ps_contract/README.md` and the existing
`repair_ps_contract/evidence/legal-ps-02/result.json` report. The existing
compiled-proof directory is evidence inventory, not a new compilation by this
Skill. The result is labeled `PS_CONTRACT_PASS_NOT_HW_BUILD`.

The report points to these real local inputs, which were also read:

- `F:/College/verilog_digital_system/Vitis/four_mic_capture/src/main_four_capture.c`
- `F:/College/verilog_digital_system/Vitis/c_adapter_platform/export/c_adapter_platform/hw/system_c_adapter.xsa`
  (inspected embedded `system.hwh`)
- `F:/College/verilog_digital_system/AMD/Competiton/one/one.srcs/sources_1/bd/system/system.bd`
  (current build metadata/topology input)

The paths are traceability pointers only. A different project supplies its own
build export and compiled PS contract; scripts do not search these paths.

## Actual reusable declarations

| Source observation | Reusable input | Limit of evidence |
|---|---|---|
| XSA/HWH declares xc7z020clg400-2; build uses Vivado 2025.2 | Expected target part/toolchain and artifact binding | Software build target; not an independent reading of the physical chip |
| AXI DMA v7.1 revision 37, S2MM=1, MM2S=0, SG=0, S2MM DRE=0 | Direction=receive; simple mode; no invented TX channel | Not a deployable PYNQ loopback |
| S2MM memory width 64, stream width 32, length-register width 14 | Address/length granularity and per-transfer upper-bound review | Translate against actual driver/IP rules; do not equate cache alignment with packet length |
| S2MM master maps to PS HP0 DDR; hardware DDR range 0..0x3fffffff | DDR path and address-window declarations | No PYNQ allocator or DMA coherency measurement |
| PS contract: 32000 groups, 8 words/group, 4 bytes/word; 1024000 bytes total | External payload/capture schema and total capacity | These values must never become generic defaults |
| 8000-byte packets, 128 packets, 64-byte guard | Distinguish per-transfer length, capture size and guard | Packet fits a 14-bit length field; total capture is not one DMA transaction |
| Compiled memory range 0x00100000..0x3fffffff; RX 0x01000000..0x01100000 exclusive | Static memory overlap/guard checks | Fixed bare-metal reservation is not a PYNQ allocation |
| Current inventory includes axi_dma_0, axi_gpio_0, four_mic_top_0, start_pulse_0, PS and interconnect | Real IP names and control/source topology | No separate custom control_regs identity/version block was found |

The 2026-09-06 M0 snapshot established ATK-DF7010P_7020P family, V3.9 baseboard,
XC7Z020 family and Vivado 2025.2, with exact part/image/DDR still open then.
This later export narrows the **build declaration** to xc7z020clg400-2; neither
snapshot alone proves physical part identification or PYNQ readiness.

## PS behavior worth extracting, not copying

The inspected standalone C reserves RX plus guard, initializes sentinel data,
flushes and invalidates before DMA, avoids CPU RX access while DMA owns it,
and invalidates after completion before examining payload/guard. It documents
core0-only ownership. Packet completion polls IOC/IDLE, checks errors and actual
received packet length. Failures capture status before bounded DMA reset;
a reset timeout enters a retain loop rather than exporting clean data.

These motivate portable ownership/count/abort invariants. The Skill must not
copy bare-metal addresses, register offsets, reset sequences or the retain loop
into a PYNQ driver. Real PYNQ cache and allocator behavior require new evidence.

## Missing for a deployable PYNQ profile

1. Versioned board PYNQ image, kernel/driver versions and physical board/device
   identity tied to a new acceptance record.
2. Same-build adjacent bit/HWH plus a manifest binding build/interface/tool
   versions and hashes; an XSA containing HWH is not that completed bundle.
3. Actual control/identity register access semantics, version expectations,
   source start/stop, overflow and interrupt/event contract. Do not add imaginary
   RO identity registers to satisfy the example validator.
4. PYNQ allocation address range, alignment/cache-line isolation, coherency,
   ownership across exceptions/process exit and bounded abort/quiescence proof.
5. Driver-specific repeated-completion bookkeeping, actual-length reporting,
   TLAST/short-packet/error observations, safe source stop and restart.
6. Physical receive capture, authorized loopback only if a separate design
   actually supplies MM2S, long-run evidence, golden payload binding, latency/
   throughput distributions and exact-build Vivado resource/timing reports.

No existing acceptance or historical board result is revoked by these gaps.
They are specifically missing inputs for this Skill's PYNQ binding. Offline
mock work may proceed without pretending that a full deployable profile exists.

## Read-only input hashes

SHA-256 values recorded during this turn and compared again after implementation:
all eight inputs were unchanged. These are not signatures or board attestation,
and do not claim a hash audit of every file in the external engineering tree.

| Input | SHA-256 |
|---|---|
| current_build/build_current.py | 4ab46c52a9dd031b40d1dd9a6b5cb2a7a9e960b0177cef2a283ac196be486aad |
| current_build/ps_contract.py | dea232b20b0f6fff473c53b229da4a182cb853ea2698103cb4162ebcd2c68ccf |
| current_build/build_hw.tcl | 9b1efe37fe9eb20ced7edc82372db31b0374e2e6805d7b2686c7c698d4c97e35 |
| current_build/README.md | 39d04525299b1d6cd77c30192bb5f1ab9b9f306e0feadd14f6acb020bbc2b78d |
| current_build/repair_ps_contract/evidence/legal-ps-02/result.json | 2c1bf7e6b148478fcd603f5a058f88e086496c70c7916579640a77fa00657ba7 |
| main_four_capture.c | c7ea5352a172287aa4890a948b4aeb00c48cc11acaa044ec909b2ee24980b7de |
| system_c_adapter.xsa | 71e7bf6d4fcb769582e5485660515b8f615b2027aa2ff18c1f8d3f67f9457baa |
| system.bd | 0be89e6da3f914e4eb914e92c79f8fb774942723db5bf4cb02e123169dfcb181 |
