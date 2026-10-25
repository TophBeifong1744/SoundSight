"""Additive solver options/cached-context regression; synthetic PC evidence only."""
import copy
import ctypes as C
import gc
import weakref
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'software/tetra3d/linux'))
from solver_3d import Solver3D, INFO, VALUES, PAIR, OPTION_DEFAULTS, read_json
from test_solver_3d_migration import synthetic, wire, cases, PAIRS


def change_tau(case, index, shift):
    p = case['pairs'][index]
    # Existing synthetic parabolic peak exactly represents Q12 tau.
    tau = p[0]*4096 + (p[3]-p[2])//4 + round(shift*4096)
    lag = round(tau/4096)
    delta = tau-lag*4096
    p[:4] = [lag, 100000, 95904-2*delta, 95904+2*delta]


def angular_error(result, az=45, el=30):
    ar, er = math.radians(az), math.radians(el)
    truth = (math.cos(er)*math.cos(ar), math.cos(er)*math.sin(ar), math.sin(er))
    vec = [result[k] for k in ('ux', 'uy', 'uz')]
    norm = math.sqrt(sum(v*v for v in vec))
    return math.degrees(math.acos(max(-1, min(1, sum(v*u for v, u in zip(vec, truth))/norm))))


class SolverOptionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which(os.environ.get('CC', 'gcc'))
        if not cc:
            raise RuntimeError('C99 compiler required')
        build = ROOT/'software/build/tetra3d-options'
        build.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='test-', dir=build)
        cls.library = Path(cls.temp.name)/('solver.dll' if os.name == 'nt' else 'solver.so')
        common, core = ROOT/'software/common', ROOT/'software/tetra3d/core'
        command = [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Wshadow', '-Werror', '-pedantic', '-shared']
        command += ['-I'+str(p) for p in (common, common/'s1', core)]
        if os.name != 'nt':
            command.append('-fPIC')
        command += [str(p) for p in (common/'s1/doa_solver.c', core/'doa_solver_3d.c',
                                     core/'doa_geometry.c', ROOT/'software/tetra3d/linux/ss_solver_3d_bridge.c')]
        command += ['-lm', '-o', str(cls.library)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        cls.geometry = read_json((core/'tetra40-nominal.json').read_text())
        cls.instances = []

    @classmethod
    def tearDownClass(cls):
        for obj in cls.instances:
            obj.close()
        if os.name == 'nt':
            import _ctypes
            for obj in cls.instances:
                _ctypes.FreeLibrary(obj.lib._handle)
        cls.temp.cleanup()

    def make(self, options=None, geometry=None):
        obj = Solver3D(self.library, geometry or self.geometry, options)
        self.instances.append(obj)
        return obj

    def legacy(self, solver, frame):
        info, values, pairs = (C.c_int32*14)(), (C.c_float*8)(), (C.c_int64*30)()
        rc = solver.call(frame['sequence'], frame['status'], (C.c_uint32*30)(*frame['words']),
                         solver._geo, solver._meta, solver._source, info, values, pairs)
        result = dict(zip(INFO, info))
        result.update(zip(VALUES, values))
        result.update(bridge_status=rc, pairs=[dict(zip(PAIR, pairs[i*5:i*5+5])) for i in range(6)])
        return result

    def test_default_legacy_exact_equivalence(self):
        solver = self.make()
        for case in cases():
            frame = wire(case)
            actual, expected = solver.solve(frame), self.legacy(solver, frame)
            for key, value in expected.items():
                self.assertEqual(actual[key], value, (case['name'], key))

    def test_all_64_pair_masks_and_no_stale_cache(self):
        solver = self.make()
        for mask in list(range(64))+list(reversed(range(64))):
            case = synthetic(45, 30)
            for i in range(6):
                if not mask & (1 << i):
                    case['pairs'][i][5] = 0
            frame = wire(case)
            actual, expected = solver.solve(frame), self.legacy(solver, frame)
            for key, value in expected.items():
                self.assertEqual(actual[key], value, (mask, key))
            self.assertEqual(actual['valid_pair_mask'], mask)
            if bin(mask).count('1') < 4:
                self.assertFalse(actual['direction_valid'])

    def test_known_channel_bias_correction_and_raw_tau_retained(self):
        bias = [0.35, -0.2, 0.1, -0.1]
        raw, calibrated = self.make(), self.make({'channel_delay_samples': bias})
        for az, el in [(45, 30), (-45, -30), (90, 0), (0, 90), (0, -90)]:
            case = synthetic(az, el)
            for i, (aa, bb) in enumerate(PAIRS):
                change_tau(case, i, bias[aa]-bias[bb])
            f = wire(case)
            before, after = raw.solve(f), calibrated.solve(f)
            self.assertTrue(after['direction_valid'])
            self.assertLess(angular_error(after, az, el), 0.02)
            self.assertGreater(angular_error(before, az, el), 0.3)
            self.assertEqual([p['tau_q12'] for p in before['pairs']],
                             [p['tau_q12'] for p in after['pairs']])

    def test_calibration_is_indexed_by_channel_not_geometry_row(self):
        g = copy.deepcopy(self.geometry)
        g['microphones'].reverse()
        options = {'channel_delay_samples': [0.3, -0.1, 0.05, -0.2]}
        a, b = self.make(options), self.make(options, g)
        self.assertEqual(a.solve(wire(synthetic(45, 30))), b.solve(wire(synthetic(45, 30))))

    def test_low_quality_bad_pair_weight_improves_synthetic_direction(self):
        case = synthetic(45, 30)
        change_tau(case, 0, 0.8)
        case['pairs'][0][4] = 95000
        frame = wire(case)
        a = self.make().solve(frame)
        b = self.make({'quality_weighting': True}).solve(frame)
        self.assertTrue(a['direction_valid'] and b['direction_valid'])
        self.assertLess(angular_error(b), 0.65*angular_error(a))
        self.assertEqual(a['valid_pair_mask'], b['valid_pair_mask'])
        self.assertEqual(a['pairs'], b['pairs'])
        # Residual remains all-pair, unweighted: no suppression of bad evidence.
        positions = [m['xyz_mm'] for m in self.geometry['microphones']]
        vec = [b[k] for k in ('ux', 'uy', 'uz')]
        residuals = []
        for i, (aa, bb) in enumerate(PAIRS):
            pred = sum((positions[bb][j]-positions[aa][j])*48/343*vec[j] for j in range(3))
            residuals.append(pred-b['pairs'][i]['tau_q12']/4096)
        self.assertAlmostEqual(b['residual_rms_samples'], math.sqrt(sum(r*r for r in residuals)/6), places=5)

    def test_weighted_result_does_not_reuse_other_frame_matrix(self):
        solver = self.make({'quality_weighting': True})
        base = synthetic(45, 30)
        change_tau(base, 0, 0.8)
        low = copy.deepcopy(base)
        low['pairs'][0][4] = 95000
        first = solver.solve(wire(low))
        middle = solver.solve(wire(base))
        last = solver.solve(wire(low))
        self.assertEqual(first, last)
        self.assertGreater(angular_error(middle), angular_error(first))

    def test_strict_residual_and_source_guards_remain(self):
        s = self.make({'quality_weighting': True, 'max_residual_rms_samples': 0.1})
        case = synthetic(45, 30)
        change_tau(case, 0, 0.8)
        case['pairs'][0][4] = 99999
        result = s.solve(wire(case))
        self.assertEqual(result['reason'], 3)
        self.assertFalse(result['direction_valid'])
        source = synthetic(45, 30)
        source['flags'] |= 0x01000000
        result = s.solve(wire(source))
        self.assertFalse(result['direction_valid'])
        self.assertEqual(result['first_error'], 1)
        source['flags'] = 0x100010
        self.assertFalse(s.solve(wire(source))['direction_valid'])

    def test_options_reject_invalid_values(self):
        bad = [{'schema': 2}, {'schema': True}, {'unknown': 0}, {'quality_weighting': 1},
               {'quality_weight_floor': 0}, {'quality_weight_floor': float('nan')},
               {'channel_delay_samples': [0, 0, 0]}, {'channel_delay_samples': [0, 0, 0, 1.1]},
               {'channel_delay_samples': [False, 0, 0, 0]}, {'channel_delay_samples': [0, 0, 0, float('inf')]},
               {'min_pairs': 3}, {'min_pairs': True}, {'norm_min': 0}, {'norm_max': 0.9},
               {'max_residual_rms_samples': 2.1}, {'tau_slack_samples': 0.6}, {'max_normal_condition': 0}]
        for options in bad:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.make(options)

    def test_direct_c_options_validation(self):
        solver = self.make()
        create = solver.lib.ss3d_context_create
        base = [100, .5, .85, 1.15, .125, .25, 0, 0, 0, 0]
        candidates = [([2, 0, 4], base), ([1, 2, 4], base), ([1, 0, 3], base)]
        for idx, val in [(0, float('nan')), (1, 3), (2, 0), (3, 0), (4, .75), (5, .01), (6, 1.1), (9, float('inf'))]:
            values = base[:]
            values[idx] = val
            candidates.append(([1, 0, 4], values))
        for meta, values in candidates:
            info, handle = (C.c_int32*14)(), C.c_void_p()
            rc = create(solver._geo, solver._meta, solver._source,
                        (C.c_uint32*3)(*meta), (C.c_float*10)(*values), info, C.byref(handle))
            self.assertEqual(rc, -6)
            self.assertFalse(handle.value)

    def test_option_copy_context_close_and_schema_unchanged(self):
        options = {'channel_delay_samples': [0, 0, 0, 0]}
        solver = self.make(options)
        frame = wire(synthetic(45, 30))
        keys = set(solver.solve(frame))
        options['channel_delay_samples'][0] = 0.5
        saved = solver.options
        saved['channel_delay_samples'][1] = 0.5
        self.assertEqual(solver.options, OPTION_DEFAULTS)
        self.assertNotIn('solver_options', keys)
        with solver as entered:
            self.assertIs(entered, solver)
            self.assertTrue(solver.solve(frame)['direction_valid'])
        solver.close()
        with self.assertRaises(RuntimeError):
            solver.solve(frame)

    def test_closed_configuration_endpoints(self):
        # norm_min=0.01 rounds down as float32; the C endpoint must use the
        # same representation as its float config field rather than double .01.
        for options in (
                dict(norm_min=0.01, norm_max=1, max_normal_condition=1,
                     max_residual_rms_samples=0, tau_slack_samples=0,
                     quality_weight_floor=0.05, min_pairs=4,
                     channel_delay_samples=[-1, 1, -1, 1]),
                dict(norm_min=1, norm_max=2, max_normal_condition=10000,
                     max_residual_rms_samples=2, tau_slack_samples=0.5,
                     quality_weight_floor=1, min_pairs=6)):
            solver = self.make(options)
            self.assertFalse(solver._closed)
            solver.close()

    def test_gc_finalizes_context_without_explicit_close(self):
        solver = Solver3D(self.library, self.geometry)
        library, finalizer = solver.lib, solver._finalizer
        reference = weakref.ref(solver)
        self.assertTrue(finalizer.alive)
        del solver
        gc.collect()
        self.assertIsNone(reference())
        self.assertFalse(finalizer.alive)
        # Finalizer invocation after GC is harmless and cannot double-free.
        finalizer()
        if os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(library._handle)

    def test_close_then_gc_finalizes_exactly_once(self):
        solver = Solver3D(self.library, self.geometry)
        library, finalizer = solver.lib, solver._finalizer
        solver.close()
        solver.close()
        self.assertFalse(finalizer.alive)
        reference = weakref.ref(solver)
        del solver
        gc.collect()
        self.assertIsNone(reference())
        finalizer()
        if os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(library._handle)

    def test_min_pairs_option(self):
        case = synthetic(45, 30)
        case['pairs'][0][5] = 0
        result = self.make({'min_pairs': 6}).solve(wire(case))
        self.assertEqual(result['valid_pairs'], 5)
        self.assertEqual(result['reason'], 1)
        self.assertFalse(result['direction_valid'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
