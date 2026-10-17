# Six-microphone acoustic software pre-review

Evidence: FLOATING / SYNTHETIC ONLY. Not hardware acceptance.

Self-tests: 21 PASS. Direction frames: 2700. Seed: 20260907.

| Scenario | Input band ratio dB | Valid % | P50 accepted deg | P95 accepted deg | Wrong >30 / all % |
|---|---:|---:|---:|---:|---:|
| clean | 128.03 | 100.00 | 0.01 | 0.02 | 0.00 |
| noise20 | 28.03 | 100.00 | 0.22 | 0.47 | 0.00 |
| noise10 | 18.03 | 100.00 | 0.67 | 1.49 | 0.00 |
| noise0 | 8.03 | 100.00 | 2.12 | 4.34 | 0.00 |
| band_noise0 | 0.00 | 47.00 | 4.82 | 10.20 | 0.00 |
| reflection | 29.06 | 100.00 | 1.50 | 3.94 | 0.00 |
| interferer0 | -0.01 | 26.00 | 40.07 | 75.31 | 17.33 |
| mismatch | 28.03 | 100.00 | 0.65 | 1.25 | 0.00 |
| one_channel_noise | 5.80 | 99.33 | 1.59 | 5.54 | 0.00 |

P50/P95 include accepted frames only; validity uses ALL target-active frames. Read both together.
Single-channel-noise results use all six channels; no automatic channel removal is claimed.
Two controlled echoes are not a measured room/RT60 model. Probes are random band-limited noise, not speech.
No four-microphone simulations were run. See config.json for every assumption and limitation.

## Ideal horizontal rejection at 90 degrees

| Hz | Attenuation dB |
|---|---:|
| 500 | 0.194 |
| 1000 | 0.777 |
| 2000 | 3.077 |
| 4000 | 9.352 |

This is one geometry and angular cut, not broadband SNR or room measurement.

## Audio

A/B/C WAV files share one global scale and come from one SIX-channel synthetic recording.
They contain noise probes, NOT speech. C uses a static mean of accepted direction estimates, not realtime tracking.
Known clean target/interferer components permit SIR calculation; audio-demo.json has exact values.

## Reproduction

Run model/python/six_mic_acoustic_review.py --out <new_directory> --repeats 5.
Compare config.json, CSVs, self-tests.json and audio-demo.json; plots may include renderer metadata.
