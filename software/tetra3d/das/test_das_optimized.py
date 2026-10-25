"""Compatibility/calibration tests; --benchmark prints PC-only time/peak memory.

Golden comparisons read the released 3347989 source from Git into memory.
They explicitly skip if that Git object is unavailable (e.g. a source-only ZIP).
No historical source tree, personal path, hardware, or network is required.
"""
import copy
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
import tracemalloc
import types
import unittest

import numpy as np

from das_3d import Geometry, TetraDAS
from dynamic_das import DynamicDAS, Q

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def config():
    return json.loads((HERE.parent/'core/tetra40-nominal.json').read_text())


def legacy_core():
    try:
        run = subprocess.run(['git', 'show', '3347989:software/tetra3d/das/dynamic_das.py'],
                             cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise unittest.SkipTest('released 3347989 Git object unavailable: ' + str(exc))
    module = types.ModuleType('released_das_reference')
    exec(compile(run.stdout, 'git:3347989/dynamic_das.py', 'exec'), module.__dict__)
    return module.DynamicDAS


def controls_and_blocks(core, pcm, seed, include_trace=None):
    rng = np.random.default_rng(seed)
    outputs, traces = [], []
    controls = [(0, dict(state='LOCKED', delays=(-8*Q, 8*Q, 13, -17), valid_through=49)),
                (13, dict(state='LOCKED', delays=(8*Q, -8*Q, Q//2, -Q//2), valid_through=36)),
                (27, dict(state='HOLD')),
                (39, dict(state='LOCKED', delays=(0, 0, 0, 0), valid_through=81)),
                (50, dict(state='SEARCH')),
                (71, dict(state='LOCKED', delays=(Q, -Q, 7*Q-1, -7*Q+1), valid_through=199)),
                (72, dict(state='STOP')),
                (250, dict(state='LOCKED', delays=(14, 29, -30, 2), valid_through=pcm.shape[1]+5))]
    for index, (start, control) in enumerate(controls):
        if start >= pcm.shape[1]:
            break
        core.control(**control)
        end = min(controls[index+1][0] if index+1 < len(controls) else pcm.shape[1], pcm.shape[1])
        while start < end:
            stop = min(start + int(rng.integers(1, 45)), end)
            kw = {} if include_trace is None else {'trace': include_trace}
            out, diag = core.push(pcm[:, start:stop], **kw)
            outputs.append(out); traces.extend(diag)
            start = stop
    kw = {} if include_trace is None else {'trace': include_trace}
    out, diag = core.push(np.zeros((4, 0), dtype=np.int32), final=True, **kw)
    outputs.append(out); traces.extend(diag)
    return np.concatenate(outputs), traces


class GoldenCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_type = legacy_core()

    def test_random_control_chunks_pcm_and_all_diagnostics(self):
        for seed in range(8):
            pcm = np.random.default_rng(seed).integers(-2**23, 2**23, (4, 1024), dtype=np.int32)
            pcm[:, ::31] = -2**23
            pcm[:, 1::31] = 2**23-1
            fade = (1, 3, 17, 480)[seed % 4]
            old, new = self.old_type(fade), DynamicDAS(fade)
            expected, old_trace = controls_and_blocks(old, pcm, seed+90)
            actual, new_trace = controls_and_blocks(new, pcm, seed+90, True)
            with self.subTest(seed=seed, fade=fade):
                np.testing.assert_array_equal(actual, expected)
                self.assertEqual(new_trace, old_trace)
                self.assertEqual(new.events, old.events)
                for name in ('time', 'closed', 'input_end', 'max_history', 'max_beams', 'saturations'):
                    self.assertEqual(getattr(new, name), getattr(old, name), name)
                quiet = DynamicDAS(fade)
                without_trace, no_trace = controls_and_blocks(quiet, pcm, seed+400, False)
                np.testing.assert_array_equal(without_trace, expected)
                self.assertEqual(no_trace, [])
                self.assertEqual(quiet.events, old.events)
                self.assertEqual(len(quiet.samples), 17)

    def test_empty_short_full_scale_and_eof(self):
        for count in (0, 1, 7, 8, 16, 17, 33):
            for level in (-2**23, 2**23-1):
                for target in (None, (-8*Q, 8*Q, -8*Q, 8*Q), (0, 1, -1, 0)):
                    old, new = self.old_type(1), DynamicDAS(1)
                    if target is not None:
                        old.control(state='LOCKED', delays=target, valid_through=count+3)
                        new.control(state='LOCKED', delays=target, valid_through=count+3)
                    pcm = np.full((4, count), level, dtype=np.int32)
                    a, ta = old.push(pcm, final=True)
                    b, tb = new.push(pcm, final=True)
                    with self.subTest(count=count, level=level, target=target):
                        np.testing.assert_array_equal(a, b)
                        self.assertEqual(ta, tb)
                        self.assertEqual(old.events, new.events)


class OptimizedDAS(unittest.TestCase):
    def test_trace_switch_does_not_affect_subsequent_calls(self):
        pcm = np.random.default_rng(930).integers(-10000, 10000, (4, 300), dtype=np.int32)
        a, b = DynamicDAS(7), DynamicDAS(7)
        for core in (a, b):
            core.control(state='LOCKED', delays=(0, Q//2, -Q//2, 3*Q), valid_through=80)
        for lo in range(0, 300, 30):
            y, tr = a.push(pcm[:, lo:lo+30], trace=(lo % 60 == 0))
            expected, all_trace = b.push(pcm[:, lo:lo+30])
            np.testing.assert_array_equal(y, expected)
            self.assertEqual(tr, all_trace if lo % 60 == 0 else [])
        self.assertEqual(a.events, b.events)

    def test_invalid_input_does_not_advance(self):
        core = DynamicDAS()
        for pcm in (np.zeros((3, 2), dtype=int), np.zeros((4, 2)),
                    np.full((4, 2), 2**23, dtype=np.int32)):
            with self.assertRaises(ValueError):
                core.push(pcm, trace=False)
            self.assertEqual(core.time, 0)
        for trace in (None, 0, 1, 'false'):
            with self.assertRaises(ValueError):
                core.push(np.zeros((4, 2), dtype=int), trace=trace)
            self.assertEqual(core.time, 0)

    def test_steady_linear_interpolation_frequency_response(self):
        # Independent frequency-domain expectation of half-sample interpolation.
        # This checks loss, not claims of ideal broadband delay or enhancement.
        n = np.arange(4800)
        for frequency in (1000, 4000, 8000):
            omega = 2*math.pi*frequency/48000
            pcm = np.tile(np.rint(1e6*np.sin(omega*n)).astype(np.int32), (4, 1))
            core = DynamicDAS(1)
            core.control(state='LOCKED', delays=(Q//2,)*4, valid_through=5000)
            y, trace = core.push(pcm, trace=False)
            indices = n[480:4320]
            actual = y[488:4328]
            expected = 1e6*math.cos(omega/2)*np.sin(omega*(indices-0.5))
            with self.subTest(hz=frequency):
                self.assertLess(float(np.max(np.abs(actual-expected))), 1.5)
                ratio = np.linalg.norm(actual)/np.linalg.norm(1e6*np.sin(omega*indices))
                self.assertAlmostEqual(ratio, math.cos(omega/2), places=5)
                self.assertEqual(trace, [])
                print('LINEAR_HALF_SAMPLE_HZ=%d AMPLITUDE_DB=%.6f' % (frequency, 20*math.log10(ratio)))


class Calibration(unittest.TestCase):
    def test_identity_calibration_is_bit_exact(self):
        rng = np.random.default_rng(921)
        pcm = rng.integers(-2**23, 2**23, (4, 1024), dtype=np.int32)
        variants = [None, {'schema': 1},
                    {'schema': 1, 'channel_delay_samples': [0]*4, 'channel_gain': [1]*4},
                    {'schema': 1, 'channel_delay_samples': [0.5]*4}]
        output = []
        for calibration in variants:
            das = TetraDAS(config(), 7, calibration=calibration)
            self.assertEqual(das.steer((1, 2, 3), valid_through=1040), Geometry(config()).delays((1, 2, 3)))
            output.append(das.push(pcm, start_sample=0, final=True))
        for actual in output[1:]:
            np.testing.assert_array_equal(output[0], actual)

    def test_delay_sign_and_gain_restore_known_wave(self):
        geometry = Geometry(config())
        direction = np.array((1, 2, 3), dtype=float)
        direction /= np.linalg.norm(direction)
        geometric = geometry._offsets @ direction * 48000/343
        biases = np.array((0, 0.5, -0.5, 1))
        sensor_gains = np.array((1, 0.5, 2, 0.25))
        n = np.arange(4800)
        omega = 2*math.pi*1000/48000
        pcm = np.rint(1e6*sensor_gains[:, None]*np.sin(omega*(n[None, :]+geometric[:, None]-biases[:, None]))).astype(np.int32)
        calibration = {'schema': 1, 'channel_delay_samples': biases.tolist(),
                       'channel_gain': (1/sensor_gains).tolist()}
        corrected = TetraDAS(config(), 1, calibration=calibration)
        delays = corrected.steer(direction, valid_through=5000)
        self.assertEqual(delays, tuple(round(float(v)*Q) for v in geometric-biases))
        y = corrected.push(pcm, start_sample=0)
        raw = TetraDAS(config(), 1)
        raw.steer(direction, valid_through=5000)
        bad = raw.push(pcm, start_sample=0)
        expected = 1e6*np.sin(omega*n[480:4320])
        error = float(np.mean((y[488:4328]-expected)**2))
        bad_error = float(np.mean((bad[488:4328]-expected)**2))
        self.assertLess(math.sqrt(error)/1e6, 0.002)
        self.assertGreater(bad_error, error*100)

    def test_relative_ch0_time_reference_and_gain_fallback(self):
        cal = {'schema': 1, 'channel_delay_samples': [0.5, 1, 0, -0.5],
               'channel_gain': [0.5, 1, 1, 1]}
        das = TetraDAS(config(), 1, calibration=cal)
        self.assertEqual(das.calibration.delays(das.geometry, (0, 0, 1))[0], 0)
        pcm = np.tile(np.array((-5, -3, -1, 0, 1, 3, 5), dtype=np.int32), (4, 1))
        y = das.push(pcm, start_sample=0, final=True)
        np.testing.assert_array_equal(y[:8], np.zeros(8, dtype=np.int64))
        np.testing.assert_array_equal(y[8:], np.rint(pcm[0]*0.5))

    def test_capacity_checked_for_all_directions_before_stream(self):
        cfg = {'schema': 1, 'channel_delay_samples': [-1, 1, -1, 1]}
        das = TetraDAS(config(), calibration=cfg)
        self.assertAlmostEqual(das.calibration.max_delay_samples, 7.59766763848, places=8)
        for index in (1, 2, 3):
            for sign in (-1, 1):
                d = das.calibration.delays(das.geometry, sign*das.geometry._offsets[index])
                self.assertLessEqual(max(map(abs, d)), 8*Q)
        # A single current direction could fit; reject the profile because a
        # future opposite direction would overflow the fixed history/lookahead.
        larger = config()
        for microphone in larger['microphones']:
            microphone['xyz_mm'] = [v*1.25 for v in microphone['xyz_mm']]
        self.assertLess(Geometry(larger).max_delay_samples, 8)
        with self.assertRaisesRegex(ValueError, 'capacity'):
            TetraDAS(larger, calibration=cfg)

    def test_reject_bad_calibration(self):
        invalid = [False, [], {'schema': True}, {'schema': 2}, {'schema': 1, 'gain': [1]*4}]
        for field, value in [('channel_delay_samples', [0, 0, 0]),
                             ('channel_delay_samples', np.array(0)),
                             ('channel_delay_samples', [0, 0, 0, True]),
                             ('channel_delay_samples', [0, 0, 0, float('nan')]),
                             ('channel_delay_samples', [2]*4),
                             ('channel_gain', [1, 1, 1, 0]),
                             ('channel_gain', [1, 1, 1, -1]),
                             ('channel_gain', [1, 1, 1, 9]),
                             ('channel_gain', [1, 1, 1, float('inf')]),
                             ('channel_gain', [1, 1, 1, 10**400]),
                             ('channel_gain', [1, 1, 1, '2'])]:
            invalid.append({'schema': 1, field: value})
        for cfg in invalid:
            with self.subTest(config=cfg), self.assertRaises(ValueError):
                TetraDAS(config(), calibration=cfg)

    def test_calibration_copies_caller_arrays(self):
        gains = np.array((0.5, 1, 1, 1), dtype=float)
        delays = np.zeros(4)
        das = TetraDAS(config(), calibration={'schema': 1, 'channel_gain': gains,
                                             'channel_delay_samples': delays})
        gains[:] = float('nan')
        delays[:] = 1000
        self.assertEqual(das.calibration.delays(das.geometry, (0, 0, 1)),
                         das.geometry.delays((0, 0, 1)))
        pcm = np.full((4, 10), 10, dtype=np.int32)
        y = das.push(pcm, start_sample=0, final=True)
        np.testing.assert_array_equal(y[8:], np.full(10, 5))

    def test_gain_overflow_rejected_atomically_and_retry(self):
        cal = {'schema': 1, 'channel_gain': [1, 2, 1, 1]}
        das = TetraDAS(config(), calibration=cal)
        das.steer((1, 0, 0), valid_through=1000)
        before = copy.deepcopy(das._core.__dict__)
        pcm = np.zeros((4, 10), dtype=np.int32)
        pcm[1, -1] = 2**23-1
        with self.assertRaisesRegex(ValueError, 'calibrated PCM exceeds S24'):
            das.push(pcm, start_sample=0)
        self.assertEqual(das._core.__dict__, before)
        pcm[1, -1] = 1000
        a = das.push(pcm, start_sample=0, final=True)
        reference = TetraDAS(config(), calibration=cal)
        reference.steer((1, 0, 0), valid_through=1000)
        np.testing.assert_array_equal(a, reference.push(pcm, start_sample=0, final=True))


def benchmark():
    """Relative desktop measurements, not an ARM real-time acceptance test."""
    old_type = legacy_core()
    pcm = np.random.default_rng(2026).integers(-2**20, 2**20, (4, 48000), dtype=np.int32)
    factories = [('released_trace', old_type, None), ('optimized_trace', DynamicDAS, True),
                 ('optimized_no_trace', DynamicDAS, False)]

    def consume(cls, trace, count, block):
        core = cls(480)
        core.control(state='LOCKED', delays=(0, 5033, -10371, 19420), valid_through=count+7)
        kwargs = {} if trace is None else {'trace': trace}
        for start in range(0, count, block):
            end = min(start+block, count)
            core.push(pcm[:, start:end], final=end == count, **kwargs)

    print('PC_ONLY_BENCHMARK Python=' + sys.version.split()[0] + ' NumPy=' + np.__version__)
    for name, cls, trace in factories:
        consume(cls, trace, 1024, 1024)
        times = []
        for _ in range(3):
            start = time.perf_counter()
            consume(cls, trace, 48000, 1024)
            times.append(time.perf_counter()-start)
        peaks = {}
        for block in (1024, 8192):
            core = cls(480)
            core.control(state='LOCKED', delays=(0, 5033, -10371, 19420), valid_through=block+7)
            kw = {} if trace is None else {'trace': trace}
            tracemalloc.start()
            audio, diag = core.push(pcm[:, :block], **kw)
            peaks[str(block)] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            assert len(audio) == block
            if trace is False:
                assert diag == []
        print(json.dumps({'variant': name, 'samples': 48000, 'block_samples': 1024,
                          'median_seconds': statistics.median(times),
                          'peak_traced_bytes_by_block': peaks}, sort_keys=True))


if __name__ == '__main__':
    if sys.argv[1:] == ['--benchmark']:
        benchmark()
    else:
        unittest.main(verbosity=2)
