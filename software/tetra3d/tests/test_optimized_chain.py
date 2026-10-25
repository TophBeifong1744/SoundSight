"""Cross-module PC integration; synthetic calibration is NOT board calibration."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent/'linux'))
sys.path.insert(0, str(HERE.parent/'das'))
from solver_3d import Solver3D
from das_3d import TetraDAS
from spatial_runtime import DirectionFilter3D, DirectionFilterConfig, DualAxisTracker, DualAxisConfig
from test_solver_3d_migration import synthetic, wire, PAIRS, close_lib


class OptimizedChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ss3d-chain-')
        cls.library = Path(cls.temp.name)/('solver.dll' if os.name == 'nt' else 'solver.so')
        common, core = ROOT/'software/common', HERE.parent/'core'
        cmd = [os.environ.get('CC', 'gcc'), '-std=c99', '-O2', '-Wall', '-Wextra',
               '-Wconversion', '-Wshadow', '-Werror', '-pedantic', '-shared']
        if os.name != 'nt': cmd.append('-fPIC')
        cmd += ['-I'+str(p) for p in (common, common/'s1', core)]
        cmd += [str(HERE.parent/'linux/ss_solver_3d_bridge.c'), str(common/'s1/doa_solver.c')]
        cmd += [str(core/n) for n in ('doa_solver_3d.c', 'doa_geometry.c', 'doa_target_3d.c')]
        cmd += ['-lm', '-o', str(cls.library)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except BaseException:
            cls.temp.cleanup()
            raise
        cls.geometry = json.loads((core/'tetra40-nominal.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def calibrated_case(self, az, el, biases):
        case = synthetic(az, el)
        for pair, (aa, bb) in zip(case['pairs'], PAIRS):
            tau_q12 = pair[0]*4096 + (pair[3]-pair[2])//4
            tau_q12 += round((biases[aa]-biases[bb])*4096)
            lag = round(tau_q12/4096)
            delta = tau_q12-lag*4096
            pair[:4] = [lag, 100000, 95904-2*delta, 95904+2*delta]
        return wire(case)

    def test_calibrated_solver_filter_das_and_pointing(self):
        bias = [0.125, -0.25, 0.375, -0.125]
        gains = [1.25, 0.8, 1.0, 1.5]
        options = dict(schema=1, channel_delay_samples=bias)
        calibration = dict(schema=1, channel_delay_samples=bias, channel_gain=gains)
        solver = Solver3D(self.library, self.geometry, options=options)
        try:
            for az, el in [(45, 30), (-45, -30), (0, 90), (0, -90), (0, 0), (90, 0)]:
                with self.subTest(az=az, el=el):
                    raw = solver.solve(self.calibrated_case(az, el, bias))
                    self.assertEqual(raw['direction_valid'], 1)
                    tracker = DirectionFilter3D(DirectionFilterConfig(confirm_frames=1))
                    filtered = tracker.update(raw, timestamp_s=0., now_s=0., sequence=100,
                                              session_id='synthetic-session', target_id='synthetic-target')['filtered_direction']
                    self.assertTrue(filtered['valid'])
                    self.assertEqual(raw['servo_cmd_valid'], 0)
                    beam = TetraDAS(self.geometry, fade_samples=1, calibration=calibration)
                    beam.steer(filtered['vector'], valid_through=11999)
                    ar, er = math.radians(az), math.radians(el)
                    u = np.array([math.cos(er)*math.cos(ar), math.cos(er)*math.sin(ar), math.sin(er)])
                    pos = np.array([r['xyz_mm'] for r in self.geometry['microphones']])/1000
                    advance = (pos-pos[0]) @ u / 343 * 48000
                    n = np.arange(4096)
                    pcm = np.rint(1000000*np.sin(2*np.pi*1000*(n[None, :]+advance[:, None]-np.array(bias)[:, None])/48000)/np.array(gains)[:, None]).astype(np.int32)
                    y = np.concatenate([beam.push(pcm[:, :701], start_sample=0),
                                        beam.push(pcm[:, 701:], start_sample=701, final=True)])
                    expected = 1000000*np.sin(2*np.pi*1000*(n-bias[0])/48000)
                    rms = np.sqrt(np.mean((y[40:4000]-expected[32:3992])**2))/1000000
                    self.assertLess(rms, .002)
                    # Synthetic known initial pose: pure software, no hardware command.
                    cfg = DualAxisConfig(rotation=((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
                                         yaw_limits_deg=(-180., 180.), pitch_limits_deg=(-90., 90.),
                                         max_yaw_rate_deg_s=60., max_pitch_rate_deg_s=60.)
                    axes = DualAxisTracker(cfg, initial_yaw_deg=az, initial_pitch_deg=el, initial_time_s=0.)
                    command = axes.update(filtered, now_s=.01, enable=True)
                    self.assertTrue(command['command_valid'])
                    self.assertLessEqual(abs(command['pitch_deg']-el), .05)
                    expired = tracker.poll(now_s=1.)
                    self.assertFalse(expired['valid'])
                    self.assertIsNone(expired['vector'])
                    self.assertFalse(axes.update(expired, now_s=1., enable=True)['command_valid'])
        finally:
            solver.close()
            close_lib(solver.lib)


if __name__ == '__main__':
    unittest.main(verbosity=2)
