# Six-microphone floating acoustic baseline

`six_mic_acoustic_review.py` implements the user-authorized six-microphone-only software pre-review. It does not run four-microphone comparisons, modify the existing MATLAB baseline, or implement FPGA/PS logic.

Dependencies: Python 3, NumPy, Pillow. The current desktop bundled runtime provides these; no new installation was performed.

Run from repository root:

The model body retains its original bytes. Any old paths embedded in historical output or source description refer to the original layout; the command below uses the migrated entry and does not claim a new acoustic run.

```text
python models/python/six_mic_acoustic_review.py --out codex_out/six-mic-acoustic-review-new --repeats 5
```

This regenerates same-named simulation artifacts in the output directory. Choose an empty directory for an independent reproducibility run. Parameters, coordinate convention, source seed, channel map, validity thresholds and limitations are recorded in `config.json`; `manifest.json` contains artifact hashes.

Read the [Chinese review](../../document/six-mic-acoustic-software-review.md) before interpreting outputs. Synthetic probes and controlled echoes do not demonstrate natural-speech, real-room, PDM, fixed-point, timing or board acceptance. A/B/C outputs and the source WAV all use the same six-channel simulation; C is an offline static direction estimate, not a streaming tracker.
