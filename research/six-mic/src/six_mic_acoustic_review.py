"""Six-channel FLOATING/SYNTHETIC acoustic pre-review; no RTL or hardware evidence.

Only NumPy and Pillow are required. See generated config.json and SUMMARY.md.
No four-microphone experiments, speech recordings, microphone-response measurements,
or calibrated room impulse responses are used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FS, C, N, L = 48000, 343.0, 1024, 4096
BAND = (300, 4000)
START = 1536
SEED = 20260907
R = np.sqrt(2) * .020
POS = np.array([[-.020, -.020, 0], [.020, -.020, 0],
                [.020, .020, 0], [-.020, .020, 0], [0, 0, R], [0, 0, -R]])
PAIRS = [(i, j) for i in range(6) for j in range(i + 1, 6)]
B = np.array([POS[i] - POS[j] for i, j in PAIRS])
SCENARIOS = ["clean", "noise20", "noise10", "noise0", "band_noise0", "reflection",
             "interferer0", "mismatch", "one_channel_noise"]


def unit(az, el):
    a, e = np.deg2rad([az, el])
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def angle(u, v):
    return float(np.rad2deg(np.arccos(np.clip(np.dot(u, v), -1, 1))))


def source(rng):
    f = np.fft.rfftfreq(L, 1 / FS)
    spec = np.fft.rfft(rng.normal(size=L))
    # Smooth spectral band edges; synthetic broadband probe, NOT natural speech.
    weight = np.clip((f - 200) / 200, 0, 1) * np.clip((4400 - f) / 600, 0, 1)
    x = np.fft.irfft(spec * weight, n=L)
    return x / np.std(x)


def shift(x, samples):
    """Periodic fractional shift; all reported samples come from an interior crop."""
    f = np.fft.rfftfreq(len(x))
    return np.fft.irfft(np.fft.rfft(x) * np.exp(-2j * np.pi * f * samples), n=len(x))


def render(x, u, distance=1.5, positions=POS, extra_delay=0):
    # Exact spherical path lengths; remove common distance/c (unknown emission time).
    d = np.linalg.norm(distance * u - positions, axis=1)
    delays = (d - distance) / C * FS + extra_delay
    return np.array([shift(x, t) * distance / di for t, di in zip(delays, d)])


def gcc(frame):
    x = np.fft.rfft(frame * np.hanning(N)[None, :], axis=1)
    f = np.fft.rfftfreq(N, 1 / FS)
    band = (f >= BAND[0]) & (f <= BAND[1])
    estimates = []
    for i, j in PAIRS:
        z = x[i] * x[j].conj()
        amp = np.abs(z)
        mask = band & (amp >= .02 * max(float(amp[band].max()), 1e-15))
        if mask.sum() < 12:
            estimates.append(np.nan)
            continue
        z = np.where(mask, z / np.maximum(amp, 1e-15), 0)
        corr = np.fft.irfft(z, n=N)
        bound = np.linalg.norm(POS[i] - POS[j]) / C * FS
        lim = int(np.ceil(bound))
        lags = np.arange(-lim, lim + 1)
        peak = int(lags[np.argmax(corr[lags % N])])
        ym, y0, yp = corr[(peak - 1) % N], corr[peak % N], corr[(peak + 1) % N]
        denom = ym - 2 * y0 + yp
        delta = np.clip(.5 * (ym - yp) / denom, -.5, .5) if denom < -1e-15 else 0.
        tau = peak + delta
        estimates.append(tau if abs(tau) <= bound + .05 else np.nan)
    return np.array(estimates)


def solve(tau):
    good = np.isfinite(tau)
    if good.sum() < 5 or np.linalg.matrix_rank(B[good]) < 3:
        return np.array([1., 0., 0.]), False, np.nan, np.nan
    # tau_ij = t_i - t_j; u points TO source, hence minus sign.
    raw = np.linalg.lstsq(B[good], -C / FS * tau[good], rcond=None)[0]
    norm = float(np.linalg.norm(raw))
    residual = float(np.sqrt(np.mean((B[good] @ raw * FS / C + tau[good]) ** 2)))
    valid = bool(.7 <= norm <= 1.3 and residual <= .5)
    return raw / max(norm, 1e-12), valid, residual, norm


def make_trial(az, el, repeat, scenario):
    # Same seeds across scenarios; mismatch is one fixed uncalibrated assembly.
    rng = np.random.default_rng(SEED + int(az) * 1000 + int(el + 90) * 10 + repeat)
    x, z = source(rng), source(rng)
    u = unit(az, el)
    actual = POS
    mrng = np.random.default_rng(SEED + 991)
    if scenario == "mismatch":
        actual = POS + mrng.uniform(-.0005, .0005, POS.shape)
    target = render(x, u, positions=actual)
    other = np.zeros_like(target)
    if scenario == "reflection":
        # Controlled two echoes, not a calibrated shoebox room or an RT60 model.
        target += .45 * render(x, unit(az + 110, -el / 2), positions=actual, extra_delay=FS * .003)
        target += .25 * render(x, unit(az - 75, 35), positions=actual, extra_delay=FS * .007)
    if scenario == "interferer0":
        other += render(z, unit(az + 90, 0), positions=actual)
    snr = {"clean": 120, "noise20": 20, "noise10": 10, "noise0": 0, "band_noise0": 120,
           "reflection": 20, "interferer0": 20, "mismatch": 20, "one_channel_noise": 20}[scenario]
    other += rng.normal(size=target.shape) * 10 ** (-snr / 20)
    if scenario == "band_noise0":
        other += np.array([source(rng) for _ in range(6)])
    if scenario == "one_channel_noise":
        # Channel 4 is noisy, not dropped. Baseline has no automatic channel detector.
        other[4] += rng.normal(size=L) * 10 ** (10 / 20)
    if scenario == "mismatch":
        gains = 10 ** (mrng.uniform(-1, 1, 6) / 20)
        ds = mrng.uniform(-.1, .1, 6)
        target = np.array([shift(t * g, d) for t, g, d in zip(target, gains, ds)])
        other = np.array([shift(t * g, d) for t, g, d in zip(other, gains, ds)])
    return u, target, other


def das(x, steering):
    # True arrival offset ~= -r dot u/c, so compensate by +r dot u/c.
    delays = POS @ steering / C * FS
    return np.mean([shift(s, d) for s, d in zip(x, delays)], axis=0)


def ratio(a, b):
    return float(10 * np.log10((np.mean(a * a) + 1e-20) / (np.mean(b * b) + 1e-20)))


def band_ratio(a, b):
    f = np.fft.rfftfreq(a.shape[-1], 1 / FS)
    use = (f >= BAND[0]) & (f <= BAND[1])
    aa = np.fft.rfft(a, axis=-1)[..., use]
    bb = np.fft.rfft(b, axis=-1)[..., use]
    return float(10 * np.log10((np.mean(np.abs(aa) ** 2) + 1e-20) /
                              (np.mean(np.abs(bb) ** 2) + 1e-20)))


def geometry_tests():
    assert len(PAIRS) == 15 and len(set(PAIRS)) == 15
    tests = []
    for az, el in [(0, 0), (90, 0), (180, 0), (270, 0), (0, 90), (0, -90), (35, 25)]:
        u = unit(az, el)
        est, valid, _, _ = solve(-B @ u / C * FS)
        assert valid and angle(u, est) < 1e-5
        tests.append({"test": "exact_tdoa_sign_and_unit", "az": az, "el": el, "pass": True})
        rng = np.random.default_rng(SEED)
        frame = render(source(rng), u)[:, START:START + N]
        est, valid, _, _ = solve(gcc(frame))
        err = angle(u, est)
        assert valid and err < 3, (az, el, err)
        tests.append({"test": "waveform_gcc_sign", "az": az, "el": el, "error_deg": err, "pass": True})
    for removed in range(6):
        p = np.delete(POS, removed, axis=0)
        assert np.linalg.matrix_rank(p[1:] - p[0]) == 3
        tests.append({"test": "single_channel_removed_geometry_rank3", "removed": removed, "pass": True})
    zero = np.zeros((6, N))
    assert not solve(gcc(zero))[1]
    tests.append({"test": "digital_zero_rejected", "pass": True})
    return tests


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def font(size=20):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def plot_panels(path, title, panels):
    """Small fixed-layout scientific plot renderer using already-installed Pillow."""
    im = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(im)
    d.text((45, 18), title, fill="#182b49", font=font(27))
    colors = ["#1965b0", "#d36a00", "#23823b", "#a13584"]
    for k, panel in enumerate(panels):
        x0, x1, y0, y1 = 105, 1320, 130 + k * 410, 425 + k * 410
        d.text((105, y0 - 52), panel["title"], fill="#182b49", font=font(22))
        lo, hi = panel["yrange"]
        xmin, xmax = panel["xrange"]
        px = lambda x: x0 + (x - xmin) / (xmax - xmin) * (x1 - x0)
        py = lambda y: y1 - (min(hi, max(lo, y)) - lo) / (hi - lo) * (y1 - y0)
        for tick in np.linspace(lo, hi, 5):
            yy = py(tick)
            d.line((x0, yy, x1, yy), fill="#d8dde4")
            d.text((25, yy - 9), f"{tick:.1f}", fill="#42536a", font=font(18))
        for tick, label in panel["xticks"]:
            xx = px(tick)
            d.line((xx, y0, xx, y1), fill="#eef0f3")
            d.text((xx - 34, y1 + 8), str(label), fill="#42536a", font=font(17))
        for idx, (name, xs, ys) in enumerate(panel["series"]):
            points = [(px(x), py(y)) for x, y in zip(xs, ys) if np.isfinite(y)]
            if len(points) >= 2:
                d.line(points, fill=colors[idx], width=3)
            for xx, yy in points[::max(1, len(points) // 15)]:
                d.ellipse((xx - 3, yy - 3, xx + 3, yy + 3), fill=colors[idx])
            d.text((700 + idx * 145, y0 - 27), name, fill=colors[idx], font=font(18))
        d.rectangle((x0, y0, x1, y1), outline="#42536a", width=1)
    im.save(path)


def ideal_beams(out):
    angles = np.arange(-180, 181)
    target = unit(0, 0)
    rows = []
    panels = [{"title": "Azimuth cut: elevation 0 deg; x-axis degrees; y-axis dB", "yrange": (-40, 0),
               "xrange": (-180, 180), "xticks": [(a, a) for a in range(-180, 181, 60)], "series": []},
              {"title": "Elevation cut: azimuth 0 deg; x-axis degrees; y-axis dB", "yrange": (-40, 0),
               "xrange": (-90, 90), "xticks": [(a, a) for a in range(-90, 91, 30)], "series": []}]
    for freq in [500, 1000, 2000, 4000]:
        for axis, panel in [("azimuth", panels[0]), ("elevation", panels[1])]:
            aa = angles if axis == "azimuth" else np.arange(-90, 91)
            dirs = np.array([unit(a, 0) if axis == "azimuth" else unit(0, a) for a in aa])
            response = np.abs(np.exp(2j * np.pi * freq / C * POS @ (target - dirs).T).mean(axis=0))
            db = 20 * np.log10(np.maximum(response, 1e-8))
            panel["series"].append((f"{freq} Hz", aa, db))
            for a, d in zip(aa, db):
                rows.append({"cut": axis, "frequency_hz": freq, "angle_deg": a, "response_db": d})
        onaxis = np.abs(np.exp(2j * np.pi * freq / C * POS @ (target - target)).mean())
        assert np.isclose(onaxis, 1)
    plot_panels(out / "six-mic-beam-cuts.png", "Six microphones / ideal Delay-and-Sum / target +x / model only", panels)
    write_csv(out / "beam-cuts.csv", rows)
    im = Image.new("RGB", (900, 720), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 20), "Six-mic candidate / dimensions in mm / not frozen", fill="#182b49", font=font(26))
    project = lambda p: (410 + 6 * p[0] - 4 * p[1], 365 + 2 * p[0] + 3 * p[1] - 7 * p[2])
    for axis, label in [(np.array([40, 0, 0]), "+x"), (np.array([0, 40, 0]), "+y"), (np.array([0, 0, 40]), "+z")]:
        end = project(axis)
        d.line((project(np.zeros(3)), end), fill="#9da6b3", width=2)
        d.text(end, label, fill="#42536a", font=font(20))
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5)]:
        d.line((project(POS[i] * 1000), project(POS[j] * 1000)), fill="#b8c1d0", width=2)
    for i, p in enumerate(POS * 1000):
        xx, yy = project(p)
        d.ellipse((xx - 8, yy - 8, xx + 8, yy + 8), fill="#1965b0")
        d.text((xx + 14, yy - 18), f"mic{i}", fill="#182b49", font=font(20))
        d.text((xx + 14, yy + 8), str(tuple(round(v, 1) for v in p.tolist())), fill="#42536a", font=font(17))
    d.text((30, 650), "Horizontal square: side 40; upper/lower: z = +/-28.284", fill="#42536a", font=font(22))
    im.save(out / "six-mic-geometry.png")
    return rows


def audio_demo(out):
    # Six original channels -> three outputs. No four-channel array involved.
    count = FS * 3
    rng = np.random.default_rng(SEED)
    f = np.fft.rfftfreq(count, 1 / FS)
    x = np.fft.irfft(np.fft.rfft(rng.normal(size=count)) * ((f >= 300) & (f <= 4000)))
    x /= np.std(x)
    z = np.fft.irfft(np.fft.rfft(rng.normal(size=count)) * ((f >= 1500) & (f <= 4000)))
    z /= np.std(z)
    u = unit(0, 30)
    target, other = render(x, u), .501187 * render(z, unit(90, 0))
    mixture = target + other
    estimates = []
    total_frames = 0
    for start in range(FS // 2, count - FS // 2 - N, 512):
        total_frames += 1
        est, valid, _, _ = solve(gcc(mixture[:, start:start + N]))
        if valid:
            estimates.append(est)
    if not estimates:
        return {"status": "no_valid_auto_direction", "speech": False}
    auto = np.mean(estimates, axis=0)
    auto /= np.linalg.norm(auto)
    signals = [mixture[0], das(mixture, u), das(mixture, auto)]
    # Static automatic direction from multiple frames: NOT a realtime streaming demo.
    crop = slice(FS // 4, count - FS // 4)
    signals = [s[crop] for s in signals]
    scale = .8 / max(max(np.max(np.abs(s)) for s in signals), np.max(np.abs(mixture[:, crop])))
    files = ["A-single-reference.wav", "B-manual-direction.wav", "C-auto-static-direction.wav"]
    for path, signal in zip(files, signals):
        with wave.open(str(out / path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(FS)
            w.writeframes((signal * scale * 32767).astype("<i2").tobytes())
    with wave.open(str(out / "six-channel-synthetic-input.wav"), "wb") as w:
        w.setnchannels(6)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes((mixture[:, crop].T * scale * 32767).astype("<i2").tobytes())
    inp = ratio(target[0, crop], other[0, crop])
    manual_snr = ratio(das(target, u)[crop], das(other, u)[crop])
    auto_snr = ratio(das(target, auto)[crop], das(other, auto)[crop])
    return {"status": "synthetic_noise_probe_only", "speech": False, "files": files,
            "common_gain": scale, "input_file": "six-channel-synthetic-input.wav",
            "wav_quantization": "16-bit shared scale; metrics computed before quantization",
            "target_az": 0, "target_el": 30,
            "auto_error_deg": angle(u, auto), "auto_valid_frames": len(estimates),
            "auto_total_frames": total_frames, "auto_valid_pct": 100 * len(estimates) / total_frames,
            "input_sir_db": inp, "manual_sir_db": manual_snr, "auto_sir_db": auto_snr,
            "manual_improvement_db": manual_snr - inp, "auto_improvement_db": auto_snr - inp}


def run(out, repeats):
    out.mkdir(parents=True, exist_ok=True)
    config = {"evidence": "floating_point_synthetic_only", "seed": SEED, "fs_hz": FS,
              "frame_samples": N, "hop_candidate": 512, "sound_speed_mps": C,
              "positions_m": POS.tolist(), "pair_order": PAIRS, "band_hz": BAND,
              "gcc": "1024 FFT/IFFT, Hann, PHAT 2% amplitude mask, parabolic sub-sample peak",
              "estimator": "unweighted all-available-pair LS; norm and residual rejection; no tracking",
              "valid_gate": {"raw_norm": [.7, 1.3], "residual_samples_max": .5, "min_pairs": 5},
              "target_distance_m": 1.5, "azimuths": list(range(0, 360, 30)),
              "elevations": [-60, -30, 0, 30, 60], "repeats": repeats,
              "noise_snr_definition": "direct target per-channel approximately unit RMS vs unfiltered independent sensor noise before GCC band mask",
              "scenarios": SCENARIOS, "microphone_context": "existing IM73D122V01/PDM selection unchanged; ideal identical omni transfer functions, not measured device response",
              "limitations": ["no natural speech", "no calibrated room RT60", "no microphone directivity/housing/occlusion model",
                              "no PDM decimator or fixed-point RTL", "no physical channel-fault detection",
                              "parameters chosen before run; exploratory not independent acceptance dataset",
                              "six microphones ONLY; no four-mic comparison"],
              "python": platform.python_version(), "numpy": np.__version__, "pillow": Image.__version__,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    tests = geometry_tests()
    (out / "self-tests.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
    beamrows = ideal_beams(out)
    rows = []
    for scenario in SCENARIOS:
        for az in range(0, 360, 30):
            for el in [-60, -30, 0, 30, 60]:
                for repeat in range(repeats):
                    u, target, other = make_trial(az, el, repeat, scenario)
                    est, valid, residual, norm = solve(gcc((target + other)[:, START:START + N]))
                    error = angle(u, est)
                    estel = float(np.rad2deg(np.arcsin(np.clip(est[2], -1, 1))))
                    rows.append({"scenario": scenario, "az_true": az, "el_true": el, "repeat": repeat,
                                 "valid": int(valid), "error_deg": error, "el_est": estel,
                                 "wrong_gt30": int(valid and error > 30),
                                 "hemisphere_wrong": int(valid and abs(el) >= 10 and el * estel < 0),
                                 "known_component_band_ratio_db": band_ratio(target, other),
                                 "residual_samples": residual, "raw_norm": norm})
        print(f"Finished {scenario}", flush=True)
    write_csv(out / "direction-trials.csv", rows)
    summaries = []
    for scenario in SCENARIOS:
        batch = [r for r in rows if r["scenario"] == scenario]
        accepted = [r["error_deg"] for r in batch if r["valid"]]
        valid_count = len(accepted)
        hemi = [r for r in batch if abs(r["el_true"]) >= 10]
        summaries.append({"scenario": scenario, "frames": len(batch), "valid_frames": valid_count,
                          "valid_pct": 100 * valid_count / len(batch),
                          "p50_valid_deg": float(np.median(accepted)) if accepted else np.nan,
                          "p95_valid_deg": float(np.percentile(accepted, 95)) if accepted else np.nan,
                          "median_input_band_component_ratio_db": float(np.median([r["known_component_band_ratio_db"] for r in batch])),
                          "wrong_all_pct": 100 * sum(r["wrong_gt30"] for r in batch) / len(batch),
                          "wrong_valid_pct": 100 * sum(r["wrong_gt30"] for r in batch) / max(valid_count, 1),
                          "hemisphere_wrong_all_pct": 100 * sum(r["hemisphere_wrong"] for r in hemi) / len(hemi),
                          "hemisphere_valid_pct": 100 * sum(r["valid"] for r in hemi) / len(hemi)})
    write_csv(out / "direction-summary.csv", summaries)
    bins = []
    for scenario in SCENARIOS:
        for az in range(0, 360, 30):
            for el in [-60, -30, 0, 30, 60]:
                group = [r for r in rows if r["scenario"] == scenario and r["az_true"] == az and r["el_true"] == el]
                acc = [r["error_deg"] for r in group if r["valid"]]
                bins.append({"scenario": scenario, "az": az, "el": el, "frames": len(group),
                             "valid_pct": 100 * len(acc) / len(group),
                             "p50_valid_deg": float(np.median(acc)) if acc else np.nan})
    write_csv(out / "direction-bins.csv", bins)
    labels = [s["scenario"] for s in summaries]
    short = ["clean", "wide20", "wide10", "wide0", "band0", "echoes", "SIR0", "mismatch", "bad ch4"]
    xp = list(range(len(labels)))
    vals = [s["p95_valid_deg"] for s in summaries]
    plot_panels(out / "six-mic-direction-summary.png", "Six-mic GCC-PHAT baseline / synthetic probes only", [
        {"title": "P95 spherical error (degrees): ACCEPTED FRAMES ONLY", "yrange": (0, max(15, np.nanmax(vals) * 1.1)),
         "xrange": (-.4, len(labels) - .6), "xticks": list(zip(xp, short)), "series": [("P95", xp, vals)]},
        {"title": "Valid outputs / ALL target-active frames (%)", "yrange": (0, 100),
         "xrange": (-.4, len(labels) - .6), "xticks": list(zip(xp, short)), "series": [("Valid %", xp, [s["valid_pct"] for s in summaries])]}])
    demo = audio_demo(out)
    (out / "audio-demo.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
    lines = ["# Six-microphone acoustic software pre-review", "", "Evidence: FLOATING / SYNTHETIC ONLY. Not hardware acceptance.", "",
             f"Self-tests: {len(tests)} PASS. Direction frames: {len(rows)}. Seed: {SEED}.", "",
             "| Scenario | Input band ratio dB | Valid % | P50 accepted deg | P95 accepted deg | Wrong >30 / all % |", "|---|---:|---:|---:|---:|---:|"]
    for s in summaries:
        lines.append(f"| {s['scenario']} | {s['median_input_band_component_ratio_db']:.2f} | {s['valid_pct']:.2f} | {s['p50_valid_deg']:.2f} | {s['p95_valid_deg']:.2f} | {s['wrong_all_pct']:.2f} |")
    lines += ["", "P50/P95 include accepted frames only; validity uses ALL target-active frames. Read both together.",
              "Single-channel-noise results use all six channels; no automatic channel removal is claimed.",
              "Two controlled echoes are not a measured room/RT60 model. Probes are random band-limited noise, not speech.",
              "No four-microphone simulations were run. See config.json for every assumption and limitation.", "",
              "## Ideal horizontal rejection at 90 degrees", "", "| Hz | Attenuation dB |", "|---|---:|"]
    for f in [500, 1000, 2000, 4000]:
        value = next(r["response_db"] for r in beamrows if r["cut"] == "azimuth" and r["frequency_hz"] == f and r["angle_deg"] == 90)
        lines.append(f"| {f} | {-value:.3f} |")
    lines += ["", "This is one geometry and angular cut, not broadband SNR or room measurement.", "",
              "## Audio", "", "A/B/C WAV files share one global scale and come from one SIX-channel synthetic recording.",
              "They contain noise probes, NOT speech. C uses a static mean of accepted direction estimates, not realtime tracking.",
              "Known clean target/interferer components permit SIR calculation; audio-demo.json has exact values.",
              "", "## Reproduction", "", "Run model/python/six_mic_acoustic_review.py --out <new_directory> --repeats 5.",
              "Compare config.json, CSVs, self-tests.json and audio-demo.json; plots may include renderer metadata."]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"}
    (out / "manifest.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps({"self_tests": len(tests), "frames": len(rows), "summary": summaries, "audio": demo}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    run(args.out, args.repeats)
