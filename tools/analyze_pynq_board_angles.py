"""Read archived board logs without hardware access; retain rejected rows in CSV.

Angles are solver coordinates, not calibrated mechanical angles. The circular
mean avoids the discontinuity at -180/+180 degrees. Plotting needs matplotlib.
"""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from zipfile import ZipFile


def percentile(values, fraction):
    """Linear interpolation between sorted samples (including endpoints)."""
    values = sorted(values)
    p = (len(values) - 1) * fraction
    i = int(p)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (p - i)


def summarize(frames):
    accepted = [r for r in frames if r['result']['direction_valid'] == 1]
    angles = [r['result']['angle_q8'] / 256 for r in accepted]
    seq = [r['frame']['sequence'] for r in frames]
    sx = sum(math.cos(math.radians(a)) for a in angles)
    sy = sum(math.sin(math.radians(a)) for a in angles)
    return {
        'frames': len(frames), 'valid': len(accepted),
        'first_last': [seq[0], seq[-1]] if seq else [],
        'contiguous': bool(seq) and all(b == a + 1 for a, b in zip(seq, seq[1:])),
        'reasons': dict(sorted(Counter(r['result']['reason'] for r in frames).items())),
        'faults': sorted({r['frame']['fault'] for r in frames}),
        'drops': sorted({r['frame']['drops'] for r in frames}),
        'zero_mask_frames': sum(all((r['frame']['words'][5*i] >> 16) & 127 == 0
                                   for i in range(6)) for r in frames),
        'angle_deg': None if not angles else {
            'circular_mean': math.degrees(math.atan2(sy, sx)),
            'median': median(angles), 'p05': percentile(angles, .05),
            'p95': percentile(angles, .95), 'min': min(angles), 'max': max(angles)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.archive) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError('Archive CRC failure: ' + bad)
        inventories = []
        logs = {}
        for info in archive.infolist():
            if info.filename.endswith('.jsonl'):
                rows = [json.loads(s) for s in archive.read(info).decode('utf-8').splitlines() if s.strip()]
                frames = [r for r in rows if 'frame' in r]
                inventories.append({'name': info.filename, 'bytes': info.file_size,
                                    'rows': len(rows), 'frames': len(frames)})
                logs[info.filename] = (rows, frames)
    name = 'ram-real-1000-001.jsonl'
    rows, frames = logs[name]
    result = summarize(frames)
    result['archive_files'] = inventories
    result['previous_100'] = summarize(logs['ram-real-100-003.jsonl'][1])
    result['blocks'] = [summarize(frames[i:i+100]) for i in range(0, len(frames), 100)]
    result['events'] = [r for r in rows if 'frame' not in r]
    # Diagnostic sorting only: this is not a new acceptance/rejection threshold.
    center = result['angle_deg']['median']
    farthest = sorted((r for r in frames if r['result']['direction_valid']),
                      key=lambda r: abs((r['result']['angle_q8']/256-center+180)%360-180), reverse=True)[:10]
    result['farthest_valid_samples'] = farthest
    with (args.output / 'angle-analysis.json').open('w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write('\n')
    with (args.output / 'angles-1000.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['sequence', 'direction_valid', 'angle_deg', 'reason', 'valid_pairs', 'fault', 'drops']
                        + ['mask_' + str(i) for i in range(6)])
        for r in frames:
            fr, rs = r['frame'], r['result']
            writer.writerow([fr['sequence'], rs['direction_valid'],
                             rs['angle_q8']/256 if rs['direction_valid'] else '',
                             rs['reason'], rs['valid_pairs'], fr['fault'], fr['drops']]
                            + [(fr['words'][5*i] >> 16) & 127 for i in range(6)])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    fig, (ax, reasons) = plt.subplots(2, 1, figsize=(11, 6), sharex=True,
                                     gridspec_kw={'height_ratios': [3, 1]}, layout='constrained')
    valid = [r for r in frames if r['result']['direction_valid']]
    ax.scatter([r['frame']['sequence'] for r in valid],
               [r['result']['angle_q8']/256 for r in valid], s=9, alpha=.65, label='有效方向（771帧）')
    a = result['angle_deg']
    ax.axhline(a['median'], color='#b45309', linestyle='--', label=f"中位数 {a['median']:.2f}°")
    ax.axhspan(a['p05'], a['p95'], color='#2563eb', alpha=.1, label='有效角度P5～P95（非误差界限）')
    ax.set(ylabel='算法坐标角度 / °', title='SoundSight：1000帧实采角度；无运动、未做角度精度标定')
    ax.legend(loc='lower left', fontsize=9)
    for code, label in [(1, '合格对不足'), (3, '残差超限'), (4, '模长超限')]:
        seq = [r['frame']['sequence'] for r in frames if r['result']['reason'] == code]
        reasons.scatter(seq, [code]*len(seq), s=13, label=label)
    reasons.set(xlabel='帧序号（非实测时间轴）', ylabel='拒绝码', yticks=[1, 3, 4], ylim=(.4, 4.6))
    reasons.legend(loc='upper right', fontsize=8, ncol=3)
    for axis in (ax, reasons):
        axis.grid(alpha=.2)
    fig.savefig(args.output / 'angles-1000.png', dpi=160)
    plt.close(fig)
    print(json.dumps({k: v for k, v in result.items() if k not in ('archive_files', 'events', 'farthest_valid_samples', 'blocks')}, ensure_ascii=False, indent=2))
    print('FARTHEST_VALID', [(r['frame']['sequence'], r['result']['angle_q8']/256, r['result']['valid_pairs']) for r in farthest])


if __name__ == '__main__':
    main()
