# Portable H3 research composition

This package is the authority for the **new portable composition only**. The
historic fixed leaves remain at their manifest paths; their bytes and Git blobs
are checked before use. This is `PORTABLE_RESEARCH_CONFIG_ONLY`, not a production
profile, FPGA implementation, timing measurement, or complete H3 acceptance.

## Entry

From `models/python`, run:

```text
python -B -m soundsight_h3_portable --repo <repository-root> --config <research.json> --pcm <four-channel.npy> --out <new-directory>
python -B -m soundsight_h3_portable --repo <repository-root> --config <research.json> --pcm <four-channel.npy> --schedule <synthetic-events.json> --manual-angle-q8 <integer> --out <new-directory>
```

The first form is **numeric only**: no external clock, fresh, take, or automatic
audio control is inferred. The second requires explicit `SYNTHETIC_TIME` and
an independent manual angle. Input PCM is integer `[4,T]`, signed 24-bit code
range, 48 kHz. It is not normalized floating audio. A pre-existing output path
is rejected. `run-index.json` binds input, package source, leaf source, tables,
and output hashes. `result.json` contains stages, reasons, unit states, source
sample IDs and causal events; `stages-and-audio.npz` holds original integer
arrays. No result is a golden or formally scored output.

## Required research configuration

`contracts.validate_config` is the executable schema. All fields are required:

- `scope=RESEARCH_ONLY`, `profile_id=soundsight-fixed4-dual-domain-research-v1`,
  exact `source_manifest_sha256` and `table_manifest_sha256`, `backend=portable_q30_frozen`,
  `sample_rate_hz=48000`, `frame_length=1024`, `hop=512`.
- `geometry`: four channels at `[[0,0],[40,0],[40,40],[0,40]]` mm,
  `sound_speed_m_s=343`, `correction_policy=UNAPPLIED_CANDIDATE`,
  `basis=CANDIDATE_NOT_MEASURED`. These are candidate model assumptions, not
  independently measured deployment facts or calibrated corrections.
- `activity`: explicit `on_power_ratio=4`, `off_power_ratio=2`,
  `attack_frames=3`, `release_frames=3`, `minimum_active_channels=3`,
  four unsigned 64-bit `noise_power_u64` values, `band_rms_floor_codes`,
  `reference_sha256`, `initial_state=INACTIVE`,
  `invalid_policy=RESET_ACTIVITY_AND_TRACKER`. No background is estimated
  from target audio. Other activity policies are unsupported.
- `tracker`: explicit integer Q8 `half_angle_q8`, `acquire_frames`,
  `acquire_spread_q8`, `track_step_q8`, `hold_samples`, `max_gap_samples`, and
  `time_domain=SESSION_SAMPLE`. The supported fixed sector has
  `0 < half_angle_q8 < 90° Q8`; cross-wrap sector averaging is unsupported.
  No `TrackerConfig()` defaults are taken. `audio_fade_samples=480` is required.

The author diagnostic uses explicit historical research values to exercise the
branch, including 30°/2-frame acquisition/8° spread/20° step/9600-sample
hold/1440-sample gap and a synthetic unit noise reference. These are **not**
production parameter choices or calibrated noise measurements.

## Synthetic event contract

`schedule` requires `time_basis=SYNTHETIC_TIME`, explicit nonempty
`boot_id`/`session_id`/`interval_id`, integer `generation`, absolute `first_sample_id`,
nonnegative `result_ttl_samples`, and one `frames` row per complete 1024/512
window. Each row gives `frame_index`, exact issued
`external_visible_at` unit→absolute sample ID, `external_error_units`,
`available`, `commit_now`, `take_now`, and `audio_valid_through_emit` (null
unless a fresh beam will use it). For every issued external unit:

```text
frame.last_id <= external_visible_at <= available <= commit_now <= take_now
take_now <= frame.last_id + result_ttl_samples
```

Equality at the expiry boundary is valid; overflow, missing/unissued statuses,
same-tick frames/takes, and out-of-record events are rejected. Tracker updates
once at `available`; its `hold_samples` counts from the last fresh update.
The portable software precomputes numeric arrays offline, then publishes local
numeric and qualification unit states at `available`. This publication time is
a research abstraction, not a measured computation or hardware completion
time. Each external status publishes at its own `external_visible_at`, even
when another frame's take is pending. At one timestamp, cancellation precedes
normal publication; otherwise external status and local qualification precede
Tracker, binding at `commit_now`, and take at `take_now`. A prior successful
binding remains `BOUND_FRESH` or `BOUND_NO_FRESH` after later cancellation.
An offline error calculated for a cancelled frame remains diagnostic only.

`events` keeps its existing `{frame,unit,visible_at,result}` rows for normal
events strictly before cancellation. `terminations` adds one record per frame:
full boot/session/interval/frame/generation identity, `SYNTHETIC_TIME`, edge,
reason, all 53 expected units, the pre-edge final unit→status map, remaining
cancelled units, and whether successful commit/take occurred. The 53-unit
partition excludes take, which is a separate service event. A prior binding
is never retroactively rewritten; `prior_binding_retracted` is always false.
`observations` records statuses arriving on the cancellation edge without
counting them as earlier completion. `diagnostic_invalid_reasons` retains
offline numeric findings separately from pre-edge published external errors.
Consumers of `result.json` should read these additional fields for cancelled
transactions; existing normal event row fields and completed frame fields are
unchanged. Neither audit field represents RTL beats or hardware done.
Cancelled frame rows remain present for every planned window; a frame already
taken before a later interval end keeps its normal row, with the later end
recorded separately in its termination audit. STOP keeps the existing smooth
audio fallback, while fatal still cuts emission before its edge.
`result_ttl_samples` counts from raw `last_id`; audio expiry is a separate
absolute emit coordinate. No result waits for its own Tracker status. A normal
rejection updates Tracker with no candidate. ACQUIRE keeps Tracker history but
asks S5 audio for SEARCH. HOLD carries no new delays or expiry and never counts
fresh. A numeric or external protocol error resets activity/Tracker and asks
audio to fall back. Optional `fatal_emit` hard-cancels before that emission;
`stop_emit` requests a smooth STOP. Fatal wins on the same event edge.

`take_now` is an explicitly supplied synthetic service event, **not** a measured
latency. The source→emit `+8` offset belongs only to the dynamic delay stream.
Physical sample clocks, service bounds, bridge status, and real audio deadlines
are not yet established.

## Data path and frozen identities

Gate and DOA have independent centered/S24 windows and each runs four FFT29 and
four fixed4 adapters. Gate power uses its own bins 7..72; conditional DOA
uses six fixed pairs, bins 7..85 PHAT, protected conjugation, IFFT25 and lag,
unchanged vector/qualification arithmetic, then normalized CORDIC. Numeric
errors prohibit fresh; skipped units retain named reasons. The frozen FFT
table contains forward/inverse radix-2 ten-stage Q30 signed little-endian
twiddles in ascending size/j order. The atan table has 24 signed Q16 entries.
The Hann U18F17 and delay ROM S16 identities are in
`tables/source-manifest.json`; all table bytes and encoding are in
`tables/table-manifest.json`. `tables/generate_once.py` records the one-time
extraction method; normal runs consume the stored table bytes and never
regenerate them. The leaf FFT is used only for bounded author comparison.

The new composition's sole fixed4 entry is
`soundsight_h3_portable.fixed4.adapt_half_s29(values, frame_identity=...,
domain=..., bindings=...)`. It accepts four 513-bin S29 half spectra and
returns `payload_s25[4,513,2]`, `numeric_valid[4,513]`, and
`overflow_components[4,513,2]` (component order real, imaginary), plus a
summary with original frame identity, domain, per-channel component and
invalid-complex counts, and exact channel/bin/component error locations. A
single overflowing component makes that complex payload `(0,0)` without
clearing a legal neighbor. Both gate and doa arrays are published in the
normal `stages-and-audio.npz` as `<domain>_half25`,
`<domain>_fixed4_numeric_valid`, and
`<domain>_fixed4_overflow_components`; summaries appear under
`result.json` `stage_details[*].detail.fixed4.<domain>`; frame totals are in
`stage_details[*].detail.fixed4_totals`. Per-channel fixed4
unit states reflect only bins owned by that channel; a frame-level error
still prevents fresh and requests the established fallback. Causal rows then
mark scheduled commit/take attempts `REJECTED_NUMERIC_OR_PROTOCOL_INVALID`;
the recorded times are attempts, not successful events. The old bound
`guards.checked_adapter(..., fixed_golden.adapt_fft29_to_s25)` retains its
historic saturating behavior and is not the new composition entry. These
software arrays do not model RTL ready/valid, held beats, or DMA drain.

Normal audio lanes use source `n=0..T-1` at emit `n+8`: common mic0, fixed
manual direction with the S5 Q12 interpolation rule, and S5 dynamic automatic
direction. The untrimmed dynamic stream has startup/tail eight samples as
separate evidence. Only real record ends are zero padded. Fatal intervals are
ABORTED and do not promise complete equal-length lanes or an EOF tail.

## Evidence boundary

The product author runs bounded `DIAGNOSTIC_SMOKE` only. The old
`fixed_golden.full_chain` uses a different window, embedded atan2, default
Tracker, and immediate retarget audio. Its full outputs are not this chain's
expected results. New independent combination fixtures and a real non-author
review are required before any stronger claim. AMD IP equivalence, FPGA timing,
production thresholds, calibrated activity truth, real capture performance,
EDA, and hardware are NOT_RUN.
