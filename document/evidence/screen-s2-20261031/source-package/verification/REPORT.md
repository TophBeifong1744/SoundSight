# PS I2C0/EMIO S2 verification report

Date: 2026-10-31. Scope: independent static product review and explicitly assigned host-software verification batch. Product RTL, constraints, firmware and EDA outputs were read-only. This report recommends a limited board candidate; the author of these tests does not independently sign their acceptance evidence. Parent/root review is required before release.

## Result and limits

**HOST_TEST_PASS: 18 Linux-boundary methods + 4 real-installer methods; 5/5 negative canaries detected by assertions, zero canary infrastructure errors.** No unresolved software blocker was found in the executed scope. Recommend the matched payload for an axes-off 60-second board test, subject to a separate review of these assets. This is not a claim that the prior black-screen/touch fault is fixed.

Actual PS I2C0 Linux binding, ARM ctypes/ioctl execution, electrical transactions, GT911 ready-clear, screen stability, stop/restart and touch behavior remain **NOT RUN**. Real kernel syscall timeout is **UNVERIFIED**. No RTL functional simulation or new EDA run was performed by this verifier; RTL simulation was skipped under the authorized board-fault-repair workflow. No ILA, board operation, driver unbind, forced ownership, direct PS MMIO or Linux ps7_init execution was used.

## Requirement-to-test traceability

Basis: the user's PS I2C0/EMIO migration instruction; actual board DT/sysfs evidence in release `BOARD-PREFLIGHT.md`; Linux I2C UAPI message semantics; generated S2 HWH parsed with official PYNQ 2.7.0; retained axes-off startup/shutdown requirements; installer preservation/rollback contract. See `MODEL-CARD.md` for model assumptions.

| Requirement | Checker/evidence | Result and boundary |
|---|---|---|
| Identify actual I2C0 controller and bound Cadence adapter; never assume bus 0 | DiscoveryTests: bus 7 selected; wrong reg/IRQ/clock/status, pinctrl, client or driver rejected | HOST_TEST_PASS; synthetic filesystem, real property bytes |
| Own dedicated bus before reset/probe; fail on subsequent competing client | ConstructorTests, runtime ownership test, LifecycleTests | HOST_TEST_PASS; mocked locks/open/fstat/ioctl boundary |
| Exact combined pointer-write/read, read flag and byte count; preserve errno; no user retry | TransferTests decode native structures through independently declared Linux UAPI types | HOST_TEST_PASS on Windows x64; ARM/Linux ABI execution NOT RUN |
| Reject invalid bounds; clean fd/lock after error and repeated close | TransferTests, ConstructorTests | HOST_TEST_PASS |
| Prepare only appropriate disabled controller; no silent reconfigure of wrong enabled state | PrepareTests plus static review of insertion path | Wrong frequency/status and already-ready branches HOST_TEST_PASS; actual configfs apply NOT RUN |
| Match actual PS I2C0/EMIO hardware; reject old AXI IIC or wrong loaded image | MetadataTests use real generated HWH with official parser; altered parameters/connection and old metadata rejected | HOST_TEST_PASS; real PYNQ loading NOT RUN |
| Check bus before GPIO, DMA before video lock, first-frame acknowledgment before backlight; orderly error cleanup | LifecycleTests call real ui.main with boundary models, success/poll failure/ownership refusal/demo | HOST_TEST_PASS; MMIO/device behavior modeled |
| Accept supported S1/S1a/S1b, repeated installation; preserve personal assets and unrelated files | InstallerTests with real A runtime ZIP, actual S1 payload and S1/S1a/S1b software | HOST_TEST_PASS, separate fresh runtime for each variant |
| Reject unknown local/hardware state and bad checksum/revision before changes | InstallerTests snapshots before/after rejection | HOST_TEST_PASS |
| Restore present/absent files on replacement error, retain backup ledger, remove staging | Failure injected at all **15** replacement positions: 13 payload files + SOURCE.json + SCREEN-INSTALL.json | HOST_TEST_PASS |
| Critical checkers fail on intentionally bad behavior | short-transfer accepted; read flag removed; client ignored; GPIO before ownership; EMIO check disabled | 5/5 detected, assertion failure and no test errors |
| Existing screen/servo/audio hardware preserved within migration scope | Static BD/source/address/pin review; routed reports and relocation evidence | Bounded static review only; not whole-system sign-off |

## Exact executed evidence

Environment: CPython 3.13.0, Windows 11 x64, 8-byte native pointer. Deterministic directed tests; no random seed applies. Temporary directories are unique per case and removed by the fixtures. All logs and canary output remain beside this report.

From this directory:

```text
python test_linux_boundary.py       # 18 methods, 0.713 s, exit 0; linux-boundary.log
python test_installer_s2.py         # 4 methods, 14.574 s, exit 0; installer-s2.log
python test_boundary_canaries.py    # 5 detected, exit 0; canaries.log + canary-results.json
```

Counts are unittest methods, not board transactions or RTL coverage. Installer parameter loops and 15 injected failure positions are additional cases within those methods. No product changed for canaries: variants exist only in memory and module state is restored after each case.

The tested ZIP is release `test-candidate.zip` (INTERNAL_REVIEW_ONLY). `tested-artifacts.json` binds that candidate, its 13 payload members, installer and test assets. Final packaging may change review/manifest metadata only; payload and installer equality must be checked by the release owner. A changed executable payload requires impacted tests to be rerun.

Linux-boundary tests support the source-package `../screen-ui/software/screen` and `../output/soundsight.hwh` layout. Installer tests additionally require the actual baseline fixture directories referenced in the script: `../download/soundsight_pynq_3d_speaker.zip`, `../ss-screen-release-s1/delivery/soundsight_screen_s1.zip`, original S1/S1a/S1b software, and `../ss-screen-ps-i2c-release-s2`. They are not claimed to be self-contained in a standalone source ZIP.

## Static hardware evidence and retained gaps

Read-only review of S2 routed reports: WNS +0.203 ns/TNS 0; WHS +0.036 ns/THS 0; WPWS +2.208 ns/TPWS 0; 40846/40846 nets routed, zero route errors. These are results under existing constraints. `check-timing.rpt` still has 3 input and 30 output delay omissions, including LCD/GPIO; external panel/I2C timing is not closed by these results.

`cdc.rpt` retains CDC-10 critical x1 (bus_reset to screen_pixel_release asynchronous clear qualification) and CDC-11 critical x2 (screen_video locked status to screen_lock_sync and internal CDC_SINGLE_LOCKED). These same endpoint structures occur in S1. There are 1252 CDC-15 warnings. No waiver or full CDC/RDC sign-off is asserted. DRC/methodology warnings and truncated REQP1839/1840 details remain open. The retained build log directory-C environment diagnostic is not reclassified as fixed merely because the build exited 0.

Static migration review found GPIO at 0x41200000 and VDMA at 0x43000000 preserved; only unused AXI control port removed after AXI IIC deletion. PS IIC_0 connects through official IOBUF to SCL R19/SDA P20; no ILA BD instance. Historical ILA constraint is disabled. Existing audio/constraint source comparison was unchanged. The final source manifest contains 51 entries. ps7_init command sequence is unchanged (501 commands), so it supplies no reason to execute PS initialization under Linux.

Release `relocation/relocation-summary.json` and `relocation-result.txt` record a separately generated, closed/reopened Vivado 2025.2 XPR: exit 0, 122 inputs, 35 managed IPs, zero missing/old-root inputs, matching IP/port/net/ps7_init state. **Synthesis and implementation were Not started in that relocated workspace**; relocation is project-preparation evidence, not a second routed build.

## Defects and verification development issues

Two packaging path defects were corrected by root before this candidate: Windows manifest separators needed normalization for relocated packaging; the README source is root SCREEN-README.md. No unresolved product defect was found by the final executed host cases.

The initial sysfs fixture omitted aliases after platform-path resolution and falsely triggered OWNERSHIP_CHANGED: **TESTBENCH_FAIL**, corrected in the fixture. The initial installer fixture reused an already-upgraded tree between variants; it was strengthened to a fresh S1 runtime per variant and rerun. A module-reload warning was removed by importing NumPy/PIL before module mocking. These were test development issues, not firmware failures. Fetching the nonexistent PYNQ v2.7 tag was corrected to v2.7.0; no product change resulted.

## Required board evidence

The next bounded evidence is installation/reboot and explicit prepare on the known board, then axes-off 60-second screen/touch/stop and repeat-start logs. Observe actual adapter identity/100 kHz ownership, GT911 transactions, no black-screen regression, DMA shutdown and process exit. Stop at this scope; motion and joint endurance are not accepted here. No additional host rerun is needed if final payload/installer remain identical and separate review accepts these tests.
