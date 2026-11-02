# Historical portable numeric model

This research module retains integer window/FFT/PHAT/lag and direction calculations. It is not the current product or a hardware acceptance test.

```text
python -B -m soundsight_h3_portable --repo <research-source-root> --config <research.json> --pcm <four-channel.npy> --out <new-directory>
```

Only numeric frames are supported; output arrays are in `stages.npz`. Input is integer signed-24 `[4,T]` PCM at 48 kHz. Exact research source/table bindings and explicit config remain required. Historical fixed leaves named in the manifest are not included in the current project, so this is not a self-contained runtime entry. Use the maintained `software/tetra3d` implementation for current work.

The numerical stages were retained during the 2026-11-02 scope cleanup. No new full-chain verification or FPGA equivalence is claimed.
