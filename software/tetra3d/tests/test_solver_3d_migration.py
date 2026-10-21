"""Offline 3D migration tests, Python 3.8+. No board or STM32 toolchain.

Run natively on PYNQ with --library and --golden to verify the actual ARM .so.
"""
import argparse
import copy
import ctypes as C
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'software/tetra3d/linux'))
from solver_3d import Solver3D, INFO, VALUES, PAIR, read_json

PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]


def synthetic(az, el):
    # Independent analytic forward model, not the solver inverse/config builder.
    a, h, x = 40, 40 * math.sqrt(2 / 3), 40 / math.sqrt(3)
    pos = [(x, 0, -h / 4), (-x / 2, a / 2, -h / 4),
           (-x / 2, -a / 2, -h / 4), (0, 0, 3 * h / 4)]
    ar, er = math.radians(az), math.radians(el)
    u = (math.cos(er) * math.cos(ar), math.cos(er) * math.sin(ar), math.sin(er))
    arrival = [-sum(v*w for v, w in zip(p, u)) * 48 / 343 for p in pos]
    pairs = []
    for aa, bb in PAIRS:
        tq = round((arrival[aa] - arrival[bb]) * 4096)
        lag = round(tq / 4096)
        delta = tq - lag * 4096
        pairs.append([lag, 100000, 95904 - 2 * delta, 95904 + 2 * delta, 10000, 79, 0x11003800])
    return dict(name='AZ_%s_EL_%s' % (az, el), sequence=100, flags=0x10,
                pairs=pairs, expected_angles=[az, el])


def wire(case):
    words = []
    for i, (lag, peak, left, right, second, mask, flags) in enumerate(case['pairs']):
        words += [flags | mask << 16 | i << 8 | (lag & 255)]
        words += [v & 0xffffffff for v in (peak, left, right, second)]
    return dict(sequence=case['sequence'], status=case['flags'] | 1, words=words)


def cases():
    result = [synthetic(a, e) for a in range(-180, 180, 30) for e in range(-75, 76, 15)]
    result += [synthetic(a, e) for a, e in [(45, 30), (-45, -30), (0, 90), (0, -90), (90, 0), (-90, 0)]]
    base = synthetic(45, 30)
    for name in ['mask11', 'insufficient', 'legacy_bist', 'cancel', 'source_numeric',
                 'pending', 'first_error', 's25', 'lag_range', 'mask80', 'zero_norm',
                 'residual', 'incomplete']:
        c = copy.deepcopy(base)
        c.pop('expected_angles')
        c['name'] = name
        if name == 'mask11':
            for p in c['pairs']: p[5] = 11
        elif name == 'insufficient':
            for p in c['pairs'][3:]: p[5] = 0
        elif name == 'legacy_bist': c['flags'] |= 8
        elif name == 'cancel': c['flags'] |= 0x100000
        elif name == 'source_numeric': c['pairs'][0][6] |= 0x4000
        elif name == 'pending': c['pairs'][0][6] &= ~0x7000000
        elif name == 'first_error': c['flags'] |= 0x01000000
        elif name == 's25': c['pairs'][0][1] = 16777216
        elif name == 'lag_range': c['pairs'][0][0] = 32
        elif name == 'mask80': c['pairs'][0][5] = 80
        elif name == 'zero_norm':
            for p in c['pairs']: p[:4] = [0, 100000, 95904, 95904]
        elif name == 'residual': c['pairs'][0][0] += 3
        elif name == 'incomplete': c['flags'] = 0
        result.append(c)
    # Preserve both frozen transport BISTs, explicitly rejected by the 3D API.
    for name, lags, right in [('BIST_REJECT', [5, -3, 0, 1, -1, 2], 600),
                              ('BIST_ZERO', [4, 4, 0, 0, -4, -4], 800)]:
        result.append(dict(name=name, sequence=1, flags=0x18,
                           pairs=[[lag, 1000, 800, right, 100, 79, 0x66001800] for lag in lags]))
    c = copy.deepcopy(base)
    c.pop('expected_angles')
    c['name'] = 'wide_margin_int64'
    # Margin exceeds int32; first pair is outside tau bound so still no direction
    # acceptance assertion here. The direct-reference comparison covers all pairs.
    c['pairs'][0] = [31, 1, 0, 0, -16777216, 79, 0x11003800]
    result.append(c)
    return result


def close_lib(lib):
    if os.name == 'nt':
        import _ctypes
        _ctypes.FreeLibrary(lib._handle)


def compare(actual, expected, golden=False):
    for key in INFO[:12] + ['bridge_status']:
        tolerance = 1 if golden and key in ('azimuth_q8', 'elevation_q8') else 0
        difference = actual[key] - expected[key]
        if golden and key == 'azimuth_q8': difference = (difference + 46080) % 92160 - 46080
        assert abs(difference) <= tolerance, (key, actual, expected)
    for key in VALUES:
        if golden and key == 'azimuth_deg':
            difference = abs((actual[key] - expected[key] + 180) % 360 - 180)
            assert difference <= max(1e-5, 2e-6 * abs(expected[key])), (key, actual, expected)
        else:
            assert math.isclose(actual[key], expected[key], rel_tol=2e-6, abs_tol=1e-5), (key, actual, expected)
    assert actual['pairs'] == expected['pairs']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    ap.add_argument('--library', type=Path)
    ap.add_argument('--golden', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT/'software/build/tetra3d-migration/RESULT.json')
    args = ap.parse_args()
    cc = shutil.which(args.cc)
    if not cc: raise RuntimeError('C99 compiler not found: ' + args.cc)
    common = ROOT/'software/common'
    tests = ROOT/'software/tetra3d/tests'
    core = ROOT/'software/tetra3d/core'
    sources = [common/'s1/doa_solver.c'] + [core/n for n in
               ('doa_solver_3d.c', 'doa_geometry.c', 'doa_target_3d.c', 'doa_dispatch.c')]
    opts = [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Wshadow', '-Werror', '-pedantic']
    opts += ['-I'+str(p) for p in (common, common/'s1', core)]
    if os.name == 'nt': opts += ['-D__USE_MINGW_ANSI_STDIO=1']
    else: opts += ['-fPIC']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logs, records = [], []
    with tempfile.TemporaryDirectory(prefix='3d-test-', dir=args.output.parent) as folder, ExitStack() as stack:
        tmp = Path(folder)
        def run(cmd):
            p = subprocess.run(list(map(str, cmd)), cwd=ROOT, capture_output=True, text=True)
            logs.append(p.stdout + p.stderr)
            if p.returncode: raise RuntimeError(p.stdout + p.stderr)
            return p.stdout
        for profile, name in [(0, 'test_doa_3d.c'), (1, 'test_doa_3d.c'), (1, 'test_target_3d.c')]:
            exe = tmp/('test_%s_%s' % (profile, name) + ('.exe' if os.name == 'nt' else ''))
            run(opts + ['-DSS_DOA_PROFILE=%d' % profile, *sources, tests/name, '-lm', '-o', exe])
            output = run([exe])
            assert 'failures=0' in output
            print(output.splitlines()[-1])
        library = args.library or tmp/('solver.dll' if os.name == 'nt' else 'solver.so')
        if not args.library:
            run(opts + ['-shared', *sources, ROOT/'software/tetra3d/linux/ss_solver_3d_bridge.c', '-lm', '-o', library])
        refpath = tmp/('ref.dll' if os.name == 'nt' else 'ref.so')
        run(opts + ['-shared', *sources, tests/'solver_3d_reference.c', '-lm', '-o', refpath])
        geometry = read_json((core/'tetra40-nominal.json').read_text(encoding='utf-8'))
        solver = Solver3D(library, geometry)
        stack.callback(close_lib, solver.lib)
        ref = C.CDLL(str(refpath)); stack.callback(close_lib, ref)
        ref.reference3d.argtypes = [C.c_uint32, C.c_uint32, C.POINTER(C.c_int64),
                                    C.POINTER(C.c_int32), C.POINTER(C.c_float), C.POINTER(C.c_int64)]
        ref.reference3d.restype = C.c_int
        for case in cases():
            frame = wire(case)
            actual = solver.solve(frame)
            info, vals, pairs = (C.c_int32*12)(), (C.c_float*8)(), (C.c_int64*30)()
            rc = ref.reference3d(case['sequence'], case['flags'],
                 (C.c_int64*42)(*[v for p in case['pairs'] for v in p]), info, vals, pairs)
            expected = dict(zip(INFO[:12], info)); expected.update(zip(VALUES, vals))
            expected.update(bridge_status=rc, pairs=[dict(zip(PAIR, pairs[i*5:i*5+5])) for i in range(6)])
            compare(actual, expected)
            assert actual['servo_cmd_valid'] == 0
            if 'expected_angles' in case:
                az, el = case['expected_angles']
                assert actual['direction_valid'] and actual['elevation_valid']
                assert abs(actual['elevation_deg']-el) < 0.03
                if abs(el) == 90: assert not actual['azimuth_valid']
                else:
                    assert actual['azimuth_valid']
                    assert abs((actual['azimuth_deg']-az+180) % 360 - 180) < 0.03
            elif case['name'] == 'wide_margin_int64':
                assert actual['pairs'][0]['margin_q15'] == 549755846656
            else: assert not actual['direction_valid'], case['name']
            records.append(dict(name=case['name'], frame=frame, result=actual))

        # Direct C entry rejects malformed transport and clears stale success.
        frame = wire(synthetic(45, 30))
        negatives = 0
        for kind, code in [('zero_seq', -1), ('reserved_status', -2), ('unlocked', -3),
                           ('pair_echo', -4), ('reserved_feature', -4)]:
            f = copy.deepcopy(frame)
            if kind == 'zero_seq': f['sequence'] = 0
            elif kind == 'reserved_status': f['status'] |= 0x40
            elif kind == 'unlocked': f['status'] &= ~1
            elif kind == 'pair_echo': f['words'][5] &= ~0x700
            elif kind == 'reserved_feature': f['words'][0] |= 0x800000
            result = solver.solve(f)
            assert result['bridge_status'] == code and not result['direction_valid'], (kind, result)
            negatives += 1
        # The wrapper must not silently wrap Python ints to uint32.
        for value in (-1, 2**32, True, 1.5):
            for field in ('word', 'sequence', 'status'):
                f = copy.deepcopy(frame)
                if field == 'word': f['words'][0] = value
                else: f[field] = value
                try: solver.solve(f)
                except ValueError: negatives += 1
                else: raise AssertionError((field, value))

        # Validate configuration through the same C function used in production.
        geometry_cases = 0
        for kind in ('duplicate', 'channel256', 'coplanar', 'flat', 'large', 'nan',
                     'rate', 'zero_revision', 'measured_unknown', 'uncertain', 'source', 'unknown_key'):
            g = copy.deepcopy(geometry)
            if kind == 'duplicate': g['microphones'][0]['channel'] = 1
            elif kind == 'channel256': g['microphones'][0]['channel'] = 256
            elif kind == 'coplanar':
                for row in g['microphones']: row['xyz_mm'][2] = 0
            elif kind == 'flat':
                for row in g['microphones']: row['xyz_mm'][2] *= 0.01
            elif kind == 'large':
                for row in g['microphones']: row['xyz_mm'] = [v*2 for v in row['xyz_mm']]
            elif kind == 'nan': g['microphones'][0]['xyz_mm'][0] = float('nan')
            elif kind == 'rate': g['sample_rate_hz'] = 44100
            elif kind == 'zero_revision': g['revision'] = 0
            elif kind == 'measured_unknown': g['provenance'] = 'MEASURED'
            elif kind == 'uncertain': g.update(provenance='MEASURED', position_error_mm=2)
            elif kind == 'source': g['source_id'] = 'bad\nsource'
            else: g['unexpected'] = 1
            # Failed initialization may load a DLL; explicitly release on Windows.
            obj = Solver3D.__new__(Solver3D)
            try:
                obj.__init__(library, g)
            except ValueError: geometry_cases += 1
            else: raise AssertionError('accepted ' + kind)
            finally:
                if hasattr(obj, 'lib'): close_lib(obj.lib)
        g = copy.deepcopy(geometry)
        g['microphones'].reverse()  # physical row order, not wire channel order
        permuted = Solver3D(library, g); stack.callback(close_lib, permuted.lib)
        compare(permuted.solve(frame), solver.solve(frame))
        geometry_cases += 1
        g.update(provenance='MEASURED', position_error_mm=0.5, revision=2)
        measured = Solver3D(library, g); stack.callback(close_lib, measured.lib)
        assert measured.solve(frame)['coordinates_measured'] == 1
        geometry_cases += 1  # declared provenance only, no physical measurement here
        try: read_json('{"schema":1,"schema":1}')
        except ValueError: geometry_cases += 1
        else: raise AssertionError('duplicate JSON key')

        # Exercise the actual JSONL CLI, including recording an input error before
        # stopping and rejecting empty inputs / accidental overwrite.
        replay_input, replay_output = tmp/'input.jsonl', tmp/'replay.jsonl'
        sample = [records[0]['frame'], records[132]['frame'],
                  next(r['frame'] for r in records if r['name'] == 'mask11')]
        replay_input.write_text(''.join(json.dumps(f)+'\n' for f in sample), encoding='utf-8')
        cli = [sys.executable, str(ROOT/'software/tetra3d/linux/solver_3d.py'), '--library', str(library),
               '--geometry', str(core/'tetra40-nominal.json'),
               '--input', str(replay_input), '--output', str(replay_output)]
        assert 'frames=3' in run(cli)
        lines = [read_json(line) for line in replay_output.read_text(encoding='utf-8').splitlines()]
        for f, line in zip(sample, lines):
            assert line['frame'] == f and line['geometry'] == geometry
            compare(line['result'], solver.solve(f))
        original = replay_output.read_bytes()
        assert subprocess.run(cli, cwd=ROOT, capture_output=True).returncode != 0
        assert replay_output.read_bytes() == original
        cli[-1] = str(tmp/'bad.jsonl')
        bad_frame = copy.deepcopy(frame); bad_frame['sequence'] = 0
        replay_input.write_text(json.dumps(bad_frame)+'\n'+json.dumps(frame)+'\n', encoding='utf-8')
        assert subprocess.run(cli, cwd=ROOT, capture_output=True).returncode != 0
        bad_lines = (tmp/'bad.jsonl').read_text(encoding='utf-8').splitlines()
        assert len(bad_lines) == 1 and read_json(bad_lines[0])['result']['bridge_status'] == -1
        cli[-1] = str(tmp/'empty.jsonl'); replay_input.write_text('', encoding='utf-8')
        assert subprocess.run(cli, cwd=ROOT, capture_output=True).returncode != 0

        if args.golden:
            golden = json.loads(args.golden.read_text(encoding='utf-8'))
            assert golden['geometry'] == geometry and len(golden['cases']) == len(records)
            for now, before in zip(records, golden['cases']):
                assert now['name'] == before['name'] and now['frame'] == before['frame']
                compare(now['result'], before['result'], golden=True)
        timings = []
        for _ in range(200):
            start = time.perf_counter_ns(); solver.solve(frame)
            timings.append(time.perf_counter_ns()-start)
        report = dict(schema=1, platform=platform.platform(), machine=platform.machine(),
                      python=platform.python_version(), compiler=run([cc, '--version']).splitlines()[0],
                      geometry=geometry, cases=records, bridge_negatives=negatives,
                      geometry_cases=geometry_cases, motion='DISABLED',
                      replay_checks=4,
                      timing_scope='Python+ctypes+C geometry validation+solve; not acquisition or deadline proof',
                      call_ns=dict(min=min(timings), median=statistics.median(timings), max=max(timings)),
                      golden_checked=bool(args.golden), native_logs=logs)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print('MIGRATION_3D_PASS equivalence=%d bridge_negative=%d geometry=%d motion=DISABLED' % (
            len(records), negatives, geometry_cases))
        print('HOST_CALL_NS', report['call_ns'], platform.machine())


if __name__ == '__main__':
    main()
