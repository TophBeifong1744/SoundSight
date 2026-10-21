"""Offline-only comparison of raw angles and causal 20-frame target estimates.

No PYNQ imports, MMIO, actuator calls or changes to the recorded solver verdicts.
Run from the repository root; matplotlib is needed only to produce figures.
"""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from zipfile import ZipFile

WINDOW = 20
MIN_VALID = 12
RADIUS_DEG = 10.0
CONSENSUS = 2 / 3
DEADBAND_DEG = 3.0


def difference(a, b):
    """Signed shortest angular displacement, in [-180, 180)."""
    return (a - b + 180) % 360 - 180


def circular_mean(angles):
    x = sum(math.cos(math.radians(a)) for a in angles)
    y = sum(math.sin(math.radians(a)) for a in angles)
    # Opposing directions have no meaningful mean, not a valid zero angle.
    if not angles or math.hypot(x, y) <= 1e-12 * len(angles):
        return None
    return difference(math.degrees(math.atan2(y, x)), 0)


def estimate(angles, min_valid=MIN_VALID, radius=RADIUS_DEG):
    """A circular L1 medoid locates the current window's majority direction.

    Keep samples within a fixed radius; require 12 retained samples AND at least
    two thirds of all valid samples. Parameters are experimental, not calibrated.
    The previous target is deliberately absent: genuine new directions can pass.
    """
    result = dict(valid_count=len(angles), arithmetic=None, circular_unfiltered=None,
                  center=None, inlier_count=0, filtered=None, decision='insufficient_valid')
    if len(angles) < min_valid:
        return result
    result['arithmetic'] = mean(angles)
    result['circular_unfiltered'] = circular_mean(angles)
    # Deterministic tie-break only; split populations are rejected by consensus.
    center = min(sorted(angles), key=lambda a: sum(abs(difference(b, a)) for b in angles))
    kept = [a for a in angles if abs(difference(a, center)) <= radius]
    result.update(center=center, inlier_count=len(kept))
    if len(kept) < min_valid or len(kept) / len(angles) < CONSENSUS:
        result['decision'] = 'insufficient_consensus'
        return result
    result['filtered'] = circular_mean(kept)
    result['decision'] = 'accepted' if result['filtered'] is not None else 'undefined_mean'
    return result


def replay(frames, window=WINDOW):
    """Non-overlapping windows emit only at their last frame; no look-ahead.

    held_target is a display of the last simulated command, not a fresh estimate
    or permission to keep moving. Rejected windows produce no new command.
    No simulated rate limiting is claimed without real actuator parameters.
    """
    windows = []
    held = None
    for start in range(0, len(frames), window):
        batch = frames[start:start + window]
        angles = [r['result']['angle_q8'] / 256 for r in batch
                  if r['result']['direction_valid'] == 1]
        item = estimate(angles)
        if len(batch) != window:
            item.update(arithmetic=None, circular_unfiltered=None, filtered=None, decision='incomplete_window')
        candidate = item['filtered']
        changed = candidate is not None and (held is None or abs(difference(candidate, held)) >= DEADBAND_DEG)
        if changed:
            held = candidate
        item.update(first_sequence=batch[0]['frame']['sequence'],
                    last_sequence=batch[-1]['frame']['sequence'],
                    frame_count=len(batch), emitted=changed, held_target=held)
        windows.append(item)
    return windows


def stats(values):
    """Observed output spread, never ground-truth localization error."""
    if not values:
        return {'count': 0}
    steps = [abs(difference(b, a)) for a, b in zip(values, values[1:])]
    return dict(count=len(values), min_deg=min(values), max_deg=max(values),
                span_deg=max(values)-min(values), median_deg=median(values),
                max_output_step_deg=max(steps) if steps else 0,
                total_output_travel_deg=sum(steps))


def draw(frames, windows, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    raw = [r for r in frames if r['result']['direction_valid']]
    seq = [r['frame']['sequence'] for r in raw]
    angle = [r['result']['angle_q8']/256 for r in raw]
    ends = [w['last_sequence'] for w in windows]
    nan = float('nan')
    arithmetic = [w['arithmetic'] if w['arithmetic'] is not None else nan for w in windows]
    filtered = [w['filtered'] if w['filtered'] is not None else nan for w in windows]
    for zoom in (False, True):
        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True,
                                 gridspec_kw={'height_ratios': [3, 2, 1.2]}, layout='constrained')
        ax, target, counts = axes
        ax.scatter(seq, angle, s=9, color='#64748b', alpha=.45, label='原始有效角度')
        ax.plot(ends, arithmetic, 'o-', markersize=3, color='#ea580c', label='20帧普通平均')
        ax.plot(ends, filtered, 'o-', markersize=3, color='#0284c7', label='筛选后环形平均')
        ax.set(ylabel='算法角度 / °', title='1000帧离线回放：窗口结束才产生估计；断线表示无新估计')
        ax.legend(loc='lower left', ncol=3, fontsize=9)
        if zoom:
            ax.set_ylim(-30, 0)
            ax.set_title('主方向局部放大（−30°～0°）；范围外离群值见全范围图')
        target.plot(ends, filtered, 'o', markersize=4, color='#0284c7', label='筛选后候选目标')
        target.step(ends, [w['held_target'] if w['held_target'] is not None else nan for w in windows],
                    where='post', color='#15803d', label='3°死区后的模拟目标（不是实测舵机）')
        changed = [w for w in windows if w['emitted']]
        target.scatter([w['last_sequence'] for w in changed], [w['held_target'] for w in changed],
                       marker='D', s=24, color='#15803d')
        target.set(ylabel='模拟目标 / °')
        target.legend(loc='best', fontsize=9)
        counts.bar(ends, [w['valid_count'] for w in windows], width=17, color='#cbd5e1', label='有效帧')
        counts.bar(ends, [w['inlier_count'] for w in windows], width=9, color='#38bdf8', label='筛选保留帧（不足12有效时不筛选）')
        counts.axhline(MIN_VALID, color='#b91c1c', linestyle='--', linewidth=1)
        counts.set(xlabel='帧序号（无逐帧采样时间戳，不换算为实测秒数）', ylabel='每窗帧数', ylim=(0, 22))
        counts.legend(loc='lower left', ncol=2, fontsize=8)
        for axis in axes:
            axis.grid(alpha=.2)
        fig.savefig(output / ('replay-zoom.png' if zoom else 'replay-full.png'), dpi=160)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with ZipFile(args.archive) as z:
        rows = [json.loads(s) for s in z.read('ram-real-1000-001.jsonl').decode().splitlines() if s.strip()]
    frames = [r for r in rows if 'frame' in r]
    seq = [r['frame']['sequence'] for r in frames]
    if len(frames) != 1000 or not all(b == a+1 for a, b in zip(seq, seq[1:])):
        raise ValueError('Expected 1000 consecutive original frames')
    if any(r['frame']['fault'] or r['frame']['drops'] or r['motion_requested'] for r in frames):
        raise ValueError('Unexpected fault, drops or motion in this no-motion dataset')
    windows = replay(frames)
    raw = [r['result']['angle_q8']/256 for r in frames if r['result']['direction_valid']]
    common = [w for w in windows if w['filtered'] is not None]
    result = dict(parameters=dict(window=WINDOW, min_valid=MIN_VALID, radius_deg=RADIUS_DEG,
                                 min_consensus=CONSENSUS, deadband_deg=DEADBAND_DEG),
                  source_log='ram-real-1000-001.jsonl', decision_counts=dict(Counter(w['decision'] for w in windows)),
                  raw=stats(raw), arithmetic=stats([w['arithmetic'] for w in windows if w['arithmetic'] is not None]),
                  filtered=stats([w['filtered'] for w in common]),
                  arithmetic_same_windows=stats([w['arithmetic'] for w in common]),
                  deadband_commands=stats([w['held_target'] for w in windows if w['emitted']]),
                  windows=windows)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'replay-results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    with (args.output/'replay-windows.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(windows[0]))
        writer.writeheader(); writer.writerows(windows)
    draw(frames, windows, args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='windows'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
