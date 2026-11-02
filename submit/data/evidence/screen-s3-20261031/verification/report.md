# S3 independent host verification

2026-10-31. Product author and test author are separate contexts. This context read the requirements, actual A runtime source ZIP and frozen S3 candidate; it wrote only verification assets. No product edits or hardware operations were performed.

Result: **19 tests passed, 0 failures/errors** in the final run (4.386 s). **5/5 deliberately incorrect in-memory variants were detected**. No product repair cycle was required.

Candidate tested: `delivery/soundsight_screen_control_s3.zip`.
SHA256: `414b087a0ff3e4743d543bd382760671f3952ba006c80b36c03c0648b0275c1b`.

## Evidence

- `host-tests.log`: actual Python unittest output, including the mock runtime/status lifecycle.
- `canaries.log`: five detected negative variants; these are intentional checker checks, not failures in the product.
- `test_control.py`: independent expectations and executable tests.
- `check_canaries.py`: temporary in-memory mutations; product files remain unchanged.

| Area | Input / expected behavior | Host result |
|---|---|---|
| Continuous routes | Actual A CLI parser accepts SOUND → follow-sound frames=0 and SPEAKER → speaker frames=0, seconds=0 | Pass |
| Touch actions | No autostart on mode change; mode/normal completion require axis reselection; busy blocks configuration; STOP/EXIT remain available; repeated held touch triggers once | Pass |
| Runtime completion | Parent/group exit followed by separate real backend status launch; no restart before valid readback | Pass with mocked processes |
| Stop evidence | All six required uint32 fields; bool/negative/overflow/missing invalid; active status/sys/actuator/dual-axis bits and non-STOP faults reject; fault 0x40 alone allowed | Pass |
| Bad status | Missing/duplicate/malformed DEVICE_STATE, nonzero status exit or active device cannot unlock | Pass |
| Failure ownership | Runtime nonzero remains latched after idle readback and Recheck; live process group blocks exit/restart; status timeout signals once without forcekill | Pass with mocked signals |
| Current direction | Actual A formatter produces different current/history values; current-only parser, NO_OUTPUT and UNOBSERVABLE expectations | Pass |
| Speaker telemetry | Actual A formatter produces low latest score with still-valid earlier permit; panel preserves runtime permit, decrements TTL, advances score age, masks after 2 s receive silence or STOP | Pass |
| Malformed telemetry | Nonfinite angles, wrong policy and overlong records cannot retain valid current/permit display | Pass |
| Package identity | ZIP installer equals frozen installer; all four payloads equal runtime files; CRC passes; 14 actual S2/A dependencies match manifest | Pass |
| Installation | Actual ZIP installer applied to minimal actual S2/A fixture; repeated install, backups, original hardware revision and installed_boot_id preserved | Pass |
| Preservation | Synthetic profile/calibration/selection/settings/log sentinels and all other fixture files unchanged | Pass |
| Transaction faults | Inject exception before each of six os.replace calls; exact original file bytes and absence restored; stage removed | 6/6 pass |
| Local changes | Individually modify all 14 dependencies and four target files; installer rejects before backup/write | 18/18 pass |
| Input rejection | Wrong receipt revision, missing dependency and corrupt payload reject before mutation | Pass |
| Linux entry guard | Both owner locks requested; all eight busy-process tokens and lock contention prevent install | Pass under mocks only |

Actual A ZIP functions were selected by AST and executed in memory: runtime_3d.angle_text/display, speaker_runtime_3d.display and board_3d.parser. No runtime algorithm was imported into a hardware execution path, and no personal recordings, profiles, embeddings or models were extracted. Installer fixtures contain only required public source/hardware files and synthetic protected sentinels; temporary fixtures were removed by TemporaryDirectory.

The negative variants remove active-state rejection, allow duplicate status, mix historical direction into current direction, increase rather than decrease TTL, and skip installer rollback. Each causes an assertion failure in the corresponding independent test, with no test errors.

## Scope of conclusion

The frozen S3 software candidate is consistent with the agreed basic panel and passes these host checks. No concrete product blocker was found. `session_failed` deliberately requires checking the saved runtime result and restarting the panel; Recheck does not clear the failed session.

This run used Windows Python. Actual Linux subprocess creation, process groups/signals, flock, /proc enumeration, root privileges and POSIX file permissions were **not exercised**; those boundaries were mocked. No PYNQ, touch, display DMA, audio DMA, solver/inference concurrency, servo movement or combined board run was performed. Existing S2 screen/touch board results do not establish S3 control or joint-performance results. The end-of-session status checks only the registers emitted by the original status CLI; audio DMA teardown still depends on the original runtime's successful cleanup/exit.

## Reproduce

```powershell
python -B F:/NUEC/ss-screen-control-s3/verification/test_control.py
python -B F:/NUEC/ss-screen-control-s3/verification/check_canaries.py
```

These tests use the existing frozen workspace baseline and actual source ZIP. They are host verification assets, not a board procedure.
