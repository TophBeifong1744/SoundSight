"""Frozen CF1 versus final CF1A, full/sparse audio replay and real host timings."""
import importlib.util
import json
import platform
import statistics
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'verification/runtime'
sys.path[:0] = [str(RUNTIME/'software/ps'), str(RUNTIME/'software/tetra3d/linux')]
from coherent_frontend import CoherentSolver
from solver_3d import Solver3D
from pcm_capture import decode_packet
from filter_3d import SpatialFilter
spec = importlib.util.spec_from_file_location('frozen_cf1', ROOT.parent/'ss-three-d-coherent-cf1/runtime/software/tetra3d/linux/coherent_frontend.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
SOURCES = [('A_STATIC', 'ss-ab-3d-analysis-20261101/A'),
           ('B_STATIC', 'ss-b-static-3d-analysis-20261101/B_STATIC'),
           ('B_DYNAMIC', 'ss-ab-3d-analysis-20261101/B'),
           ('USER_SPEECH', 'ss-user-3d-analysis-20261101'),
           ('C_SPEECH_UNCONTROLLED', 'ss-c-3d-analysis-20261101')]
geo = json.loads((RUNTIME/'software/tetra3d/core/tetra40-nominal.json').read_text())
library = ROOT.parent/'ss-c-3d-analysis-20261101/reference/solver.dll'
hann = RUNTIME/'software/tetra3d/linux/cf1_hann.mem'

def load(path):
    raw = ROOT.parent/path/'raw'
    data = json.loads((raw/'result.json').read_text())
    pcm = (raw/'packets.bin').read_bytes()
    packets = [(pcm[i:i+8224], decode_packet(pcm[i:i+8224], data['epoch'], i//8224)) for i in range(0, len(pcm), 8224)]
    frames = [f for f in data['frames'] if f.get('audio', {}).get('valid') and f['audio']['covered_by_recording']]
    return data['epoch'], packets, frames

def run(cls, data, sparse=False, timing=False):
    epoch, packets, frames = data
    # Fixed source clock intentionally excludes wall latency from replay acceptance.
    solver = cls(Solver3D(library, geo), epoch, hann, lambda: 10.)
    filt = SpatialFilter(3, 1)
    cursor = 0
    out = []
    times = []
    cpu = []
    filtered = raw_valid = high_valid = 0
    for index, frame in enumerate(frames):
        end = frame['audio']['sample_start']+1024
        while cursor*512 < end:
            solver.accept_packet(*packets[cursor])
            cursor += 1
        if sparse and index % 6 == 5:
            continue
        wall_start, cpu_start = time.perf_counter(), time.process_time()
        result = solver.solve(frame)
        times.append(time.perf_counter()-wall_start)
        cpu.append(time.process_time()-cpu_start)
        assert result['bridge_status'] == result['api_status'] == 0
        if not timing:
            direction = filt.apply(frame, result, 12500)
            filtered += int(direction['direction_output']['valid'] and direction['angle_filter']['complete'])
            raw_valid += int(bool(result['direction_valid']))
            high_valid += int(frame['energy'] >= 12500 and bool(result['direction_valid']))
            out.append(dict(index=index, result=result))
    return out, dict(consumed=len(times), raw_valid=raw_valid, high_valid=high_valid,
                     filtered_valid_groups=filtered, frontend=solver.summary(),
                     clock_note='Frontend internal clock fixed for offline source freshness; zero internal times are not benchmarks'), dict(
                         total_wall_seconds=sum(times), total_cpu_seconds=sum(cpu),
                         median_wall_seconds=statistics.median(times), max_wall_seconds=max(times))

def compare(reference, candidate):
    ref = {row['index']: row['result'] for row in reference}
    max_error = 0.
    for row in candidate:
        before, after = ref[row['index']], row['result']
        for key in ('reason', 'direction_valid', 'valid_pairs', 'azimuth_valid', 'elevation_valid'):
            assert before[key] == after[key], (row['index'], key, before[key], after[key])
        if before['direction_valid']:
            max_error = max(max_error, max(abs(before[k]-after[k]) for k in ('ux','uy','uz')))
    assert max_error < 1e-5, max_error
    return dict(compared=len(candidate), classification_equal=len(candidate), max_vector_abs_difference=max_error)

reports = []
for label, path in SOURCES:
    data = load(path)
    full_old, old_summary, _ = run(old.CoherentSolver, data)
    full_new, new_summary, _ = run(CoherentSolver, data)
    sparse_new, sparse_summary, _ = run(CoherentSolver, data, sparse=True)
    report = dict(dataset=label, full=compare(full_old, full_new), sparse=compare(full_old, sparse_new),
                  cf1=old_summary, cf1a=new_summary, cf1a_sparse=sparse_summary,
                  filter=dict(window=3, min_valid=1, level=12500))
    reports.append(report)
    print(json.dumps(report), flush=True)
(ROOT/'verification/replay.json').write_text(json.dumps(reports, indent=2))

data = load(SOURCES[0][1])
rounds = []
for iteration in range(4):
    result = {}
    order = [('cf1',old.CoherentSolver),('cf1a',CoherentSolver)]
    if iteration % 2: order.reverse()
    for name, cls in order:
        _, _, measurements = run(cls, data, timing=True)
        result[name] = measurements
    rounds.append(result)
    print('TIMING_ROUND='+json.dumps(result), flush=True)
totals = {name: statistics.median(r[name]['total_wall_seconds'] for r in rounds) for name in ('cf1','cf1a')}
report = dict(scope='PC_RECORDED_INPUT_FRONTEND_ONLY_NO_DMA_NO_SPEAKER', platform=platform.platform(),
              python=sys.version, numpy=np.__version__, rounds=rounds, median_total_wall_seconds=totals,
              wall_reduction=1-totals['cf1a']/totals['cf1'], board_latency_measured=False)
(ROOT/'verification/timing.json').write_text(json.dumps(report, indent=2))
print('TIMING_SUMMARY='+json.dumps(report), flush=True)
