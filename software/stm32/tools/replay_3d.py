"""D3 offline six-pair feature replay through the existing C 3D solver.
No PCM/FFT, SPI, timing emulation, runtime consumption or actuator operations.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import io
import json
import math
import subprocess
import sys
import tempfile
from prepare_geometry import ROOT, header, keys, unique, gcc_executable

PAIRS = ('01', '02', '03', '12', '13', '23')
API = ('OK', 'BAD_ARGUMENT', 'INPUT_RANGE', 'INPUT_FLAGS', 'INCOMPLETE_FRAME', 'NUMERIC_RANGE')
REASONS = ('VALID', 'PAIRS', 'SINGULAR', 'RESIDUAL', 'NORM', 'LEGACY_BIST', 'CANCELLED', 'SOURCE', 'CONFIG', 'CONDITION')
PAIR_REASONS = ('OK', 'MASK', 'STAGE', 'TAU', 'NOT_EVALUATED')
PAIR_FIELDS = ('lag', 'peak', 'r_minus', 'r_plus', 'second_peak', 'mask_count', 'flags')
MAX_BYTES, MAX_FRAMES = 16 * 1024 * 1024, 4096


def strict_json(s):
    def bad_constant(value):
        raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(s, object_pairs_hook=unique, parse_constant=bad_constant)


def token(v):
    if type(v) is not str or not 1 <= len(v) <= 63 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-' for c in v):
        raise ValueError('ID must be 1..63 ASCII letters/digits/._:-')
    return v


def integer(v, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError('Integer outside storage range')
    return v


def finite(v, lo, hi):
    if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError('Invalid finite angle')
    return v


def read_bytes(path, limit):
    with path.open('rb') as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Input too large: ' + str(path))
    return data


def parse_input(data, geometry):
    lines = data.decode('utf-8').splitlines()
    if not 2 <= len(lines) <= MAX_FRAMES + 1 or any(not s.strip() or len(s) > 16384 for s in lines):
        raise ValueError('Require metadata then 1..4096 nonblank JSONL frame lines, each <=16KiB characters')
    meta = strict_json(lines[0])
    keys(meta, 'schema session_id source_kind source_id geometry_revision geometry_source_id pair_order')
    if meta['schema'] != 'SS_3D_FEATURE_REPLAY_V1':
        raise ValueError('Unknown replay schema')
    token(meta['session_id']); token(meta['source_id'])
    if meta['source_kind'] not in ('SYNTHETIC_FEATURES', 'RECORDED_FEATURES'):
        raise ValueError('Unknown feature source kind')
    integer(meta['geometry_revision'], 1, 0xffffffff)
    if (meta['geometry_revision'] != geometry['revision'] or meta['geometry_source_id'] != geometry['source_id'] or meta['pair_order'] != list(PAIRS)):
        raise ValueError('Geometry identity/pair order mismatch')
    frames = []
    for line_number, line in enumerate(lines[1:], 2):
        try:
            f = strict_json(line)
            keys(f, 'frame_id flags pairs reference')
            integer(f['frame_id'], 0, 0xffffffff); integer(f['flags'], 0, 0xffffffff)
            if type(f['pairs']) is not list or len(f['pairs']) != 6:
                raise ValueError('Exactly six pairs required; unavailable pairs retain flags/mask')
            for p in f['pairs']:
                keys(p, ' '.join(PAIR_FIELDS))
                for name in PAIR_FIELDS[:5]:
                    integer(p[name], -0x80000000, 0x7fffffff)
                integer(p['mask_count'], 0, 255); integer(p['flags'], 0, 0xffffffff)
            ref = f['reference']
            if ref is not None:
                keys(ref, 'kind source_id azimuth_deg elevation_deg')
                expected = 'SYNTHETIC' if meta['source_kind'] == 'SYNTHETIC_FEATURES' else 'INDEPENDENT'
                if ref['kind'] != expected:
                    raise ValueError('Reference must be synthetic truth or independently measured, matching source kind')
                token(ref['source_id'])
                finite(ref['azimuth_deg'], -180, 180); finite(ref['elevation_deg'], -90, 90)
            frames.append(f)
        except (ValueError, TypeError, KeyError) as e:
            raise ValueError(f'Line {line_number}: {e}') from e
    return meta, frames


def sequence(frames):
    last = None
    rows = []
    for f in frames:
        current = f['frame_id']
        delta = None if last is None else (current - last) & 0xffffffff
        if delta == 0:
            rows.append(('DUPLICATE', 0)); continue
        if delta is not None and delta >= 0x80000000:
            rows.append(('BACKWARD_OR_AMBIGUOUS', 0)); continue
        rows.append(('FIRST' if last is None else ('GAP' if delta > 1 else 'NEXT'), 0 if delta is None else delta - 1))
        # Structurally valid records advance observed chronology even if solver rejects.
        last = current
    return rows


def run_solver(geometry_header, frames, seq):
    build = ROOT / 'software/stm32/build/replay-d3'
    build.mkdir(parents=True, exist_ok=True)
    selected = [f for f, (s, _) in zip(frames, seq) if s not in ('DUPLICATE', 'BACKWARD_OR_AMBIGUOUS')]
    data = []
    for f in selected:
        numbers = [f['frame_id'], f['flags']]
        for p in f['pairs']:
            numbers.extend(p[name] for name in PAIR_FIELDS)
        data.append(' '.join(map(str, numbers)))
    with tempfile.TemporaryDirectory(prefix='worker-', dir=build) as d:
        temp = Path(d)
        (temp / 'selected_geometry.h').write_text(geometry_header, encoding='ascii')
        exe = temp / 'replay.exe'
        command = [str(gcc_executable()), '-std=c99', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Wshadow', '-Werror', '-pedantic',
                   '-D__USE_MINGW_ANSI_STDIO=1', '-I'+str(temp), '-Isoftware/common', '-Isoftware/common/s1', '-Isoftware/common/s1_3d',
                   'software/stm32/tools/replay_3d_bridge.c', 'software/common/s1_3d/doa_solver_3d.c',
                   'software/common/s1_3d/doa_geometry.c', '-lm', '-o', str(exe)]
        logs = []
        for cmd, stdin in ((command, None), ([str(exe)], '\n'.join(data) + '\n')):
            p = subprocess.run(cmd, cwd=ROOT, input=stdin, text=True, capture_output=True, timeout=120)
            log = 'COMMAND: ' + subprocess.list2cmdline(cmd) + '\n' + (p.stdout if stdin is None else '') + p.stderr + f'\nEXIT_CODE: {p.returncode}\n'
            logs.append(log)
            if p.returncode:
                raise ValueError('C replay failed:\n' + log)
        rows = [strict_json(s) for s in p.stdout.splitlines()]
    if len(rows) != len(selected)+1 or rows[0].get('solver_api') != 0x10000 or rows[0].get('geometry_valid') is not True:
        raise ValueError('Incomplete/incompatible C replay output')
    for f, result in zip(selected, rows[1:]):
        if (result['frame_id'] != f['frame_id'] or len(result['pairs']) != 6 or
                not 0 <= result['api_status'] < len(API) or not 0 <= result['reason'] < len(REASONS)):
            raise ValueError('Unexpected C replay result identity/status')
    return rows[0], iter(rows[1:]), '\n'.join(logs)


def unit_direction(az, el):
    az, el = math.radians(az), math.radians(el)
    return (math.cos(el)*math.cos(az), math.cos(el)*math.sin(az), math.sin(el))


def vector_error(u, ref_az, ref_el):
    # atan2(cross magnitude, dot) is scale invariant for positive norm. Use
    # fitted vector so Q8 rounding and pole-azimuth suppression hide no error.
    v = unit_direction(ref_az, ref_el)
    cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    return math.degrees(math.atan2(math.sqrt(sum(x*x for x in cross)), sum(x*y for x, y in zip(u, v))))


def angular_error(az, el, ref_az, ref_el):
    return vector_error(unit_direction(az, el), ref_az, ref_el)


def stats(values):
    if not values:
        return {'count': 0, 'mean_deg': None, 'rms_deg': None, 'max_deg': None}
    return dict(count=len(values), mean_deg=sum(values)/len(values),
                rms_deg=math.sqrt(sum(x*x for x in values)/len(values)), max_deg=max(values))


def reports(meta, geometry, frames, seq, solved):
    output, pair_output = [], []
    counts, reasons, api_counts, seq_counts = Counter(), Counter(), Counter(), Counter()
    errors, az_errors, el_errors = [], [], []
    for index, (f, (order, gap)) in enumerate(zip(frames, seq), 1):
        ref = f['reference']
        row = dict(record=index, session_id=meta['session_id'], source_kind=meta['source_kind'],
                   geometry_revision=geometry['revision'], geometry_source_id=geometry['source_id'],
                   frame_id=f['frame_id'], frame_flags=f['flags'], sequence=order, frame_id_gap=gap,
                   disposition='', api_status='', direction_reason='', direction_valid=0, azimuth_valid=0, elevation_valid=0,
                   azimuth_q8='', elevation_q8='', azimuth_deg='', elevation_deg='',
                   ux='', uy='', uz='', norm='', residual_rms_samples='', normal_condition='',
                   valid_pair_count='', valid_pair_mask='', first_error='', bad_pair='',
                   reference_kind=ref['kind'] if ref else '', reference_source_id=ref['source_id'] if ref else '',
                   reference_azimuth_deg=ref['azimuth_deg'] if ref else '', reference_elevation_deg=ref['elevation_deg'] if ref else '',
                   azimuth_error_deg='', elevation_error_deg='', angular_error_deg='')
        seq_counts[order] += 1
        result = None
        if order in ('DUPLICATE', 'BACKWARD_OR_AMBIGUOUS'):
            row['disposition'] = 'SEQUENCE_REJECT'
        else:
            result = next(solved)
            api_counts[API[result['api_status']]] += 1
            row['api_status'] = API[result['api_status']]
            row['direction_reason'] = REASONS[result['reason']]
            for src, dst in [('ux','ux'),('uy','uy'),('uz','uz'),('norm','norm'),('residual','residual_rms_samples'),
                             ('condition','normal_condition'),('pair_count','valid_pair_count'),('pair_mask','valid_pair_mask'),
                             ('first_error','first_error'),('bad_pair','bad_pair')]:
                row[dst] = result[src]
            if result['api_status'] != 0:
                row['disposition'] = 'INPUT_REJECT'
            elif not result['valid']:
                row['disposition'] = 'ALGORITHM_REJECT'
                reasons[row['direction_reason']] += 1
            else:
                row['disposition'] = 'VALID'
                row['direction_valid'] = 1
                row['azimuth_valid'], row['elevation_valid'] = result['az_valid'], result['el_valid']
                az, el = result['azimuth_deg'], result['elevation_deg']
                if result['az_valid']:
                    row['azimuth_q8'], row['azimuth_deg'] = result['azimuth_q8'], az
                if result['el_valid']:
                    row['elevation_q8'], row['elevation_deg'] = result['elevation_q8'], el
                if ref and result['el_valid']:
                    e = el-ref['elevation_deg']; row['elevation_error_deg'] = e; el_errors.append(abs(e))
                    if result['az_valid'] and abs(math.cos(math.radians(ref['elevation_deg']))) > 1e-4:
                        e = (az-ref['azimuth_deg']+180) % 360-180
                        row['azimuth_error_deg'] = e; az_errors.append(abs(e))
                    e = vector_error((result['ux'], result['uy'], result['uz']), ref['azimuth_deg'], ref['elevation_deg'])
                    row['angular_error_deg'] = e; errors.append(e)
        counts[row['disposition']] += 1
        output.append(row)
        for name, raw, j in zip(PAIRS, f['pairs'], range(6)):
            p = dict(record=index, frame_id=f['frame_id'], pair=name, **raw,
                     delta_q12='', tau_q12='', margin_q15='', qualified='', pair_reason='NOT_EVALUATED')
            if result is not None:
                q = result['pairs'][j]
                p.update({k:q[k] for k in ('delta_q12','tau_q12','margin_q15','qualified')})
                p['pair_reason'] = PAIR_REASONS[q['reason']]
            pair_output.append(p)
    summary = dict(run_status='COMPLETED', scope='OFFLINE_FEATURE_REPLAY_ONLY', input_declaration=meta,
                   geometry_declaration=geometry, total_records=len(frames), disposition_counts=dict(counts),
                   sequence_counts=dict(seq_counts), observed_frame_id_gap_total=sum(g for _, g in seq),
                   api_status_counts=dict(api_counts), algorithm_rejection_counts=dict(reasons),
                   reference_records=sum(f['reference'] is not None for f in frames),
                   accuracy=dict(angular=stats(errors), azimuth_absolute=stats(az_errors), elevation_absolute=stats(el_errors)),
                   limits=['Source/reference provenance is declared, not independently verified by this tool.',
                           'Feature-level replay; no PCM, FFT/PHAT, board timing, SPI or acoustic acceptance.',
                           'Frame ID gaps do not prove physical drop count; no capture timestamps.',
                           'Accuracy uses valid referenced frames only; rejection counts remain in denominator report.',
                           'No-reference accuracy is unavailable, not zero; undefined pole azimuth stays empty.'])
    return output, pair_output, summary


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    # Keep untrusted declaration IDs inert when a CSV is opened in a spreadsheet.
    # Numeric columns remain numbers; exact declarations stay in summary JSON.
    for row in rows:
        writer.writerow({k: ("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v)
                         for k,v in row.items()})
    return stream.getvalue()


def replay(input_path, geometry_path, out):
    if out.exists():
        raise ValueError('Output directory already exists; use a new path')
    data, geometry_data = read_bytes(input_path, MAX_BYTES), read_bytes(geometry_path, 16384)
    geometry = strict_json(geometry_data.decode('utf-8'))
    generated = header(geometry)  # reuse D2 field checking, C validates geometry below
    meta, frames = parse_input(data, geometry)
    seq = sequence(frames)
    checked, solved, log = run_solver(generated, frames, seq)
    rows, pairs, summary = reports(meta, geometry, frames, seq, solved)
    summary['geometry_preflight'] = checked
    # Serialize all content before publishing. summary.json is written LAST;
    # absent COMPLETED summary means interrupted/failed output, not acceptance.
    text = json.dumps(summary, indent=2, allow_nan=False) + '\n'
    frame_csv, pair_csv = csv_text(rows), csv_text(pairs)
    out.mkdir(parents=True, exist_ok=False)
    (out/'input.jsonl').write_bytes(data)
    (out/'geometry.json').write_bytes(geometry_data)
    (out/'frames.csv').write_text(frame_csv, encoding='utf-8', newline='')
    (out/'pairs.csv').write_text(pair_csv, encoding='utf-8', newline='')
    (out/'build-run.log').write_text(log, encoding='utf-8')
    (out/'summary.json').write_text(text, encoding='utf-8')
    print('REPLAY_COMPLETE,'+str(out))
    print(json.dumps({k:summary[k] for k in ('total_records','disposition_counts','algorithm_rejection_counts','accuracy')}, allow_nan=False))
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--geometry', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    try:
        replay(args.input, args.geometry, args.out)
    except (ValueError, OSError, TypeError, KeyError, OverflowError, subprocess.TimeoutExpired) as e:
        print('REPLAY_FAILED,'+str(e), file=sys.stderr)
        return 2
    return 0  # completion, NOT every direction valid or system acceptance


if __name__ == '__main__':
    raise SystemExit(main())
