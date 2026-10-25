"""Deterministic offline checks. Run: python software/tetra3d/das/test_das_3d.py"""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

from das_3d import Geometry, TetraDAS

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / 'core' / 'tetra40-nominal.json'


def config():
    return json.loads(CONFIG.read_text())


def result(vector=(0, 0, 0.75), valid=1):
    return dict(profile='TETRA40_3D', geometry_source=config()['source_id'],
                geometry_revision=1, bridge_status=0, api_status=0,
                direction_valid=valid, ux=vector[0], uy=vector[1], uz=vector[2],
                norm=math.hypot(*vector), azimuth_valid=0, elevation_valid=1)


def plane_wave(direction, count=4096, frequency=1000):
    """Independent analytic microphone arrival model (no Q12 delay helper)."""
    p = np.array([r['xyz_mm'] for r in config()['microphones']]) / 1000
    u = np.array(direction, dtype=float)
    u /= np.linalg.norm(u)
    advance = ((p-p[0]) @ u) / 343.0
    t = np.arange(count) / 48000.0
    return np.rint(1000000*np.sin(2*np.pi*frequency*(t[None, :] + advance[:, None]))).astype(np.int32)


class Tests(unittest.TestCase):
    def test_nominal_capacity_and_vertical_polarity(self):
        geo = Geometry(config())
        self.assertAlmostEqual(geo.max_delay_samples, 5.59766763848, places=8)
        up = geo.delays((0, 0, 1))
        self.assertEqual(up[:3], (0, 0, 0))
        self.assertGreater(up[3], 0)
        self.assertEqual(geo.delays((0, 0, -1)), tuple(-v for v in up))
        self.assertEqual(geo.delays((0, 0, 0.75)), up)

    def test_channel_order_and_translation(self):
        original = Geometry(config()).delays((1, 2, 3))
        cfg = config()
        for row in cfg['microphones']:
            row['xyz_mm'] = [v+100 for v in row['xyz_mm']]
        cfg['microphones'].reverse()
        self.assertEqual(Geometry(cfg).delays((1, 2, 3)), original)

    def test_geometry_rejections(self):
        cases = []
        for key, value in [('sample_rate_hz', 192000), ('sound_speed_m_s', 0),
                           ('sample_rate_hz', True), ('sample_rate_hz', float('nan')),
                           ('revision', 0), ('schema', True), ('provenance', 'UNKNOWN')]:
            c = config(); c[key] = value; cases.append(c)
        c = config(); c['microphones'][3]['channel'] = 0; cases.append(c)
        c = config(); c['microphones'][0]['channel'] = False; cases.append(c)
        c = config(); c['microphones'][2]['xyz_mm'][0] = float('inf'); cases.append(c)
        c = config()
        for row in c['microphones']:
            row['xyz_mm'][2] = 0
        cases.append(c)
        for c in cases:
            with self.subTest(c=c), self.assertRaises(ValueError):
                Geometry(c)

    def test_vector_rejections(self):
        for v in [(0, 0, 0), (1, 0), (1, 0, float('nan')), (1, False, 0), ('1', 0, 0)]:
            with self.subTest(v=v), self.assertRaises(ValueError):
                Geometry(config()).delays(v)

    def test_sphere_against_analytic_audio(self):
        # Axes, poles and seeded oblique directions; no DOA/ROM used as oracle.
        directions = list(np.eye(3)) + list(-np.eye(3))
        directions += list(np.random.default_rng(123).normal(size=(64, 3)))
        worst = 0
        for u in directions:
            pcm = plane_wave(u)
            das = TetraDAS(config(), fade_samples=1)
            das.steer(u, valid_through=5000)
            y = das.push(pcm, start_sample=0, final=True)
            expected = 1000000*np.sin(2*np.pi*1000*np.arange(4096)/48000)
            error = np.sqrt(np.mean((y[40:4000]-expected[32:3992])**2))/1000000
            worst = max(worst, error)
            self.assertLess(error, 0.002, str(u))
        print('ANALYTIC_70_DIRECTIONS_MAX_RMS_OVER_PEAK=%.8f' % worst)

    def test_wrong_vertical_steer_is_detectable(self):
        pcm = plane_wave((0, 0, 1), frequency=3000)
        outputs = []
        for u in [(0, 0, 1), (0, 0, -1)]:
            das = TetraDAS(config(), fade_samples=1)
            das.steer(u, valid_through=5000)
            outputs.append(das.push(pcm, start_sample=0))
        expected = pcm[0, 32:3992]
        good = np.mean((outputs[0][40:4000]-expected)**2)
        wrong = np.mean((outputs[1][40:4000]-expected)**2)
        self.assertGreater(wrong, good*100)

    def test_independent_noise_reduction(self):
        rng = np.random.default_rng(37)
        pcm = plane_wave((1, 2, 3), count=16000)
        noise = np.rint(rng.normal(0, 100000, size=pcm.shape)).astype(np.int32)
        das = TetraDAS(config(), fade_samples=1)
        das.steer((1, 2, 3), valid_through=17000)
        y = das.push(pcm+noise, start_sample=0)
        ideal = 1000000*np.sin(2*np.pi*1000*np.arange(16000)/48000)
        out_error = np.mean((y[40:15900]-ideal[32:15892])**2)
        gain = 10*math.log10(np.mean(noise[0, 32:15892].astype(float)**2)/out_error)
        self.assertGreater(gain, 5.0)
        print('SYNTHETIC_INDEPENDENT_NOISE_GAIN_DB=%.4f (not acoustic acceptance)' % gain)

    def test_chunk_equivalence_and_dynamic_fallback(self):
        pcm = np.random.default_rng(52).integers(-2**23, 2**23, (4, 500), dtype=np.int32)
        def run(split):
            das = TetraDAS(config(), fade_samples=13)
            outputs = []
            for lo, hi, action in [(0, 100, 'up'), (100, 200, 'down'),
                                    (200, 300, 'hold'), (300, 500, 'fallback')]:
                if action == 'up': das.steer((0, 0, 1), valid_through=160)
                if action == 'down': das.steer((0, 0, -1), valid_through=230)
                if action == 'hold': das.hold()
                if action == 'fallback': das.fallback()
                for start in range(lo, hi, split):
                    end = min(start+split, hi)
                    outputs.append(das.push(pcm[:, start:end], start_sample=start, final=end == 500))
            return np.concatenate(outputs)
        a = run(500)
        np.testing.assert_array_equal(a, run(7))
        # Expired at 231; smooth fallback is completed well before sample 280.
        np.testing.assert_array_equal(a[280:490], pcm[0, 272:482])

    def test_invalid_solver_clears_target(self):
        das = TetraDAS(config(), fade_samples=1)
        das.from_solver(result(), valid_through=1000)
        das.push(np.ones((4, 20), dtype=np.int32), start_sample=0)
        self.assertIsNone(das.from_solver(result(valid=0), valid_through=1000))
        pcm = np.tile(np.arange(30, dtype=np.int32), (4, 1))
        y = das.push(pcm, start_sample=20)
        np.testing.assert_array_equal(y[10:], pcm[0, 2:22])

    def test_solver_pole_and_fitted_vector(self):
        a = TetraDAS(config())
        delays = a.from_solver(result(), valid_through=1000)
        self.assertEqual(delays, Geometry(config()).delays((0, 0, 1)))

    @unittest.skipUnless(shutil.which(os.environ.get('CC', 'gcc')), 'C99 compiler needed for actual solver integration')
    def test_actual_c_solver_to_das(self):
        root = HERE.parents[2]
        sys.path.insert(0, str(HERE.parent/'tests'))
        from test_solver_3d_migration import Solver3D, synthetic, wire, close_lib
        common, core = root/'software/common', HERE.parent/'core'
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory)/('solver.dll' if os.name == 'nt' else 'solver.so')
            cmd = [os.environ.get('CC', 'gcc'), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-shared']
            if os.name != 'nt': cmd += ['-fPIC']
            cmd += ['-I'+str(p) for p in (common, common/'s1', core)]
            cmd += [str(HERE.parent/'linux/ss_solver_3d_bridge.c'), str(common/'s1/doa_solver.c')]
            cmd += [str(core/n) for n in ('doa_solver_3d.c', 'doa_geometry.c', 'doa_target_3d.c')]
            cmd += ['-lm', '-o', str(library)]
            build = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            solver = Solver3D(library, config())
            try:
                for az, el in [(0, 0), (90, 0), (180, 0), (-90, 0), (0, 90), (0, -90), (45, 30), (-45, -30)]:
                    with self.subTest(az=az, el=el):
                        solved = solver.solve(wire(synthetic(az, el)))
                        self.assertEqual(solved['direction_valid'], 1)
                        das = TetraDAS(config(), fade_samples=1)
                        actual = das.from_solver(solved, valid_through=5000)
                        a, e = math.radians(az), math.radians(el)
                        vector = (math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e))
                        expected = Geometry(config()).delays(vector)
                        self.assertLessEqual(max(abs(x-y) for x, y in zip(actual, expected)), 2)
                        pcm = plane_wave(vector)
                        y = das.push(pcm, start_sample=0)
                        self.assertLess(np.sqrt(np.mean((y[40:4000]-pcm[0, 32:3992])**2))/1000000, 0.002)
            finally:
                solver.close()
                close_lib(solver.lib)

    def test_solver_mismatch(self):
        for key, value in [('geometry_source', 'wrong'), ('geometry_revision', 2),
                           ('profile', 'PLANAR'), ('norm', 0.3), ('ux', float('nan')),
                           ('direction_valid', True), ('bridge_status', None)]:
            r = result(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                TetraDAS(config()).from_solver(r, valid_through=100)

    def test_expired_and_duplicate_control(self):
        das = TetraDAS(config())
        with self.assertRaises(ValueError): das.steer((1, 0, 0), valid_through=-1)
        das.steer((1, 0, 0), valid_through=20)
        with self.assertRaises(ValueError): das.steer((0, 1, 0), valid_through=30)

    def test_gap_reorder_and_pcm_range(self):
        das = TetraDAS(config())
        for pcm, start in [(np.zeros((4, 2), dtype=np.int32), 1),
                           (np.zeros((4, 2), dtype=float), 0),
                           (np.full((4, 2), 2**23, dtype=np.int32), 0),
                           (np.zeros((2, 4), dtype=np.int32), 0)]:
            with self.subTest(start=start), self.assertRaises(ValueError):
                das.push(pcm, start_sample=start)
            self.assertEqual(das.next_sample, 0)

    def test_full_scale_and_end_of_stream(self):
        for value in [-2**23, 2**23-1]:
            das = TetraDAS(config(), fade_samples=1)
            das.steer((1, 1, 1), valid_through=300)
            y = das.push(np.full((4, 100), value, dtype=np.int32), start_sample=0, final=True)
            self.assertEqual(len(y), 108)
            np.testing.assert_array_equal(y[30:90], np.full(60, value))
            with self.assertRaises(ValueError): das.push(np.zeros((4, 1), dtype=np.int32), start_sample=108)

    def test_cli_wav_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source, dest = folder/'pcm.npy', folder/'beam.wav'
            pcm = plane_wave((0, 0, 1), count=2048)
            np.save(source, pcm)
            cmd = [sys.executable, str(HERE/'das_3d.py'), '--geometry', str(CONFIG),
                   '--input', str(source), '--output', str(dest), '--direction', '0', '0', '1', '--chunk', '117']
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            with wave.open(str(dest), 'rb') as wav:
                self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()), (1, 3, 48000, 2056))
                raw = np.frombuffer(wav.readframes(2056), dtype=np.uint8).reshape(-1, 3).astype(np.int64)
                decoded = raw[:, 0] | (raw[:, 1]<<8) | (raw[:, 2]<<16)
                decoded = (decoded ^ (1<<23))-(1<<23)
            das = TetraDAS(config()); das.steer((0, 0, 1), valid_through=2055)
            np.testing.assert_array_equal(decoded, das.push(pcm, start_sample=0, final=True))
            previous = dest.read_bytes()
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(dest.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main(verbosity=2)
