"""Actual C solver, synthetic source-time stream, and integrated failure tests."""
import copy
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
from pipeline_3d import TetraPipeline, normalize_pipeline_config, solver_options_from_config
from test_solver_3d_migration import synthetic, wire, PAIRS, close_lib


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ss3d-pipeline-')
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

    def app(self, config=None):
        app = TetraPipeline(self.library, self.geometry, config,
                            session_id='synthetic-source', target_id='target-1')
        def dispose():
            app.close()
            close_lib(app._solver.lib)
        self.addCleanup(dispose)
        return app

    @staticmethod
    def frame(az=45, el=30, seq=1, bias=None):
        case = synthetic(az, el)
        case['sequence'] = seq
        if bias is not None:
            for pair, (aa, bb) in zip(case['pairs'], PAIRS):
                tau = pair[0]*4096+(pair[3]-pair[2])//4
                tau += round((bias[aa]-bias[bb])*4096)
                lag = round(tau/4096)
                delta = tau-lag*4096
                pair[:4] = [lag, 100000, 95904-2*delta, 95904+2*delta]
        return wire(case)

    def test_default_solver_filter_and_independent_raw_records(self):
        app = self.app()
        frame = self.frame()
        baseline = app._solver.solve(frame)
        first = app.process_frame(frame, capture_sample=0, now_sample=0)
        self.assertEqual(first['result'], baseline)
        self.assertFalse(first['filtered_direction']['valid'])
        self.assertFalse(first['axis_setpoint']['command_valid'])
        self.assertFalse(first['motion_requested'])
        app.process_frame(self.frame(seq=2), capture_sample=480, now_sample=480)
        third = app.process_frame(self.frame(seq=3), capture_sample=960, now_sample=960)
        self.assertTrue(third['filtered_direction']['valid'])
        self.assertAlmostEqual(sum(x*x for x in third['filtered_direction']['vector']), 1.)
        third['frame']['words'][0] = 0
        third['filtered_direction']['vector'] = [0, 0, 0]
        self.assertNotEqual(app.poll(now_sample=1000)['filtered_direction']['vector'], [0, 0, 0])

    def test_shared_calibration_c_solver_to_continuous_das(self):
        bias, gains = [0.125, -0.25, 0.375, -0.125], [1.25, .8, 1., 1.5]
        cfg = dict(direction_filter={'confirm_frames': 1}, das={'enabled': True, 'fade_samples': 1},
                   calibration={'schema': 1, 'channel_delay_samples': bias, 'channel_gain': gains},
                   calibration_source='SYNTHETIC_TEST_ONLY')
        app = self.app(cfg)
        record = app.process_frame(self.frame(bias=bias), capture_sample=0, now_sample=0)
        self.assertEqual(record['result']['direction_valid'], 1)
        self.assertEqual(app.metadata()['solver_options']['channel_delay_samples'], bias)
        self.assertEqual(list(app._beam.calibration.channel_delay_samples), bias)
        ar, er = math.radians(45), math.radians(30)
        unit = np.array([math.cos(er)*math.cos(ar), math.cos(er)*math.sin(ar), math.sin(er)])
        pos = np.array([r['xyz_mm'] for r in self.geometry['microphones']])/1000
        advance = (pos-pos[0]) @ unit / 343 * 48000
        n = np.arange(4096)
        pcm = np.rint(1e6*np.sin(2*np.pi*1000*(n[None, :]+advance[:, None]-np.array(bias)[:, None])/48000)/np.array(gains)[:, None]).astype(np.int32)
        output = np.concatenate([app.push_pcm(pcm[:, :701], start_sample=0),
                                 app.push_pcm(pcm[:, 701:], start_sample=701, final=True)])
        expected = 1e6*np.sin(2*np.pi*1000*(n-bias[0])/48000)
        self.assertEqual(len(output), len(n)+8)
        self.assertLess(np.sqrt(np.mean((output[40:4000]-expected[32:3992])**2))/1e6, .002)
        self.assertTrue(app.closed)
        self.assertIsNone(app._solver._context)

    def test_ttl_expires_inside_block_without_feature_or_poll(self):
        app = self.app(dict(direction_filter={'confirm_frames': 1, 'hold_s': .002,
                                              'max_age_s': .001},
                            das={'enabled': True, 'fade_samples': 1}))
        app.process_frame(self.frame(), capture_sample=0, now_sample=0)
        pcm = np.zeros((4, 200), dtype=np.int32)
        pcm[0] = 100000
        output = app.push_pcm(pcm, start_sample=0)
        self.assertLess(int(output[80]), 90000)  # Beam active before sample 96.
        self.assertEqual(int(output[110]), 100000)  # Already faded to CH0.
        self.assertFalse(app.poll(now_sample=200)['filtered_direction']['valid'])
        self.assertIsNone(app._beam._core.desired)

    def test_fault_bist_cancel_and_stop_remove_old_direction(self):
        mutations = [{'fault': 1}, {'fault': 0x40}, {'status': 0x19},
                     {'status': 0x100011}, {'status': 0x8011}, {'stopped': True},
                     {'drain': True}, {'status': 0x1000011}]
        for change in mutations:
            with self.subTest(change=change):
                app = self.app({'direction_filter': {'confirm_frames': 1}})
                self.assertTrue(app.process_frame(self.frame(), capture_sample=0,
                    now_sample=0)['filtered_direction']['valid'])
                frame = self.frame(seq=2)
                frame.update(change)
                raw = app._solver.solve(frame)
                result = app.process_frame(frame, capture_sample=480, now_sample=480)
                self.assertEqual(result['result'], raw)
                self.assertFalse(result['filtered_direction']['valid'])
                self.assertFalse(app.poll(now_sample=481)['filtered_direction']['valid'])

        for flag in (0x4000, 0x8000):
            with self.subTest(pair_error_flag=flag):
                app = self.app({'direction_filter': {'confirm_frames': 1}})
                app.process_frame(self.frame(), capture_sample=0, now_sample=0)
                frame = self.frame(seq=2)
                frame['words'][0] |= flag
                result = app.process_frame(frame, capture_sample=480, now_sample=480)
                self.assertIn(result['result']['reason'], (6, 7))
                self.assertFalse(result['filtered_direction']['valid'])
                self.assertFalse(app.poll(now_sample=481)['filtered_direction']['valid'])

    def test_stale_frame_cannot_restore_old_hold_on_poll_or_push(self):
        app = self.app({'direction_filter': {'confirm_frames': 1},
                        'das': {'enabled': True, 'fade_samples': 1}})
        app.process_frame(self.frame(), capture_sample=0, now_sample=0)
        app.push_pcm(np.zeros((4, 9600), dtype=np.int32), start_sample=0)
        stale = app.process_frame(self.frame(seq=2), capture_sample=480, now_sample=9600)
        self.assertFalse(stale['filtered_direction']['valid'])
        self.assertEqual(stale['filtered_direction']['reason'], 'stale_input')
        self.assertFalse(app.poll(now_sample=9600)['filtered_direction']['valid'])
        app.push_pcm(np.zeros((4, 20), dtype=np.int32), start_sample=9600)
        self.assertIsNone(app._beam._core.desired)
        self.assertFalse(app.poll(now_sample=9620)['filtered_direction']['valid'])

    def test_duplicate_or_reordered_features_latch_session(self):
        cases = [(0, 1, 1), (1, 1, 1), (1, -1, 2), (2, 1, 2), (True, 1, 2)]
        for capture, now, seq in cases:
            with self.subTest(capture=capture, now=now, seq=seq):
                app = self.app()
                app.process_frame(self.frame(), capture_sample=0, now_sample=0)
                with self.assertRaises(ValueError):
                    app.process_frame(self.frame(seq=seq), capture_sample=capture, now_sample=now)
                self.assertTrue(app.faulted)
                with self.assertRaises(RuntimeError): app.poll(now_sample=10)

    def test_pcm_gap_and_future_control_latch_session(self):
        app = self.app({'das': {'enabled': True}})
        with self.assertRaises(ValueError):
            app.push_pcm(np.zeros((4, 5), dtype=np.int32), start_sample=1)
        self.assertTrue(app.faulted)
        self.assertEqual(app.next_sample, 0)
        app2 = self.app({'das': {'enabled': True}})
        with self.assertRaises(ValueError):
            app2.process_frame(self.frame(), capture_sample=1, now_sample=1)
        self.assertTrue(app2.faulted)

    def test_gain_overflow_rejects_entire_block_before_any_control(self):
        app = self.app({'das': {'enabled': True}, 'calibration': {'schema': 1,
                        'channel_gain': [2, 1, 1, 1]}})
        pcm = np.zeros((4, 50), dtype=np.int32)
        pcm[0, -1] = 2**23-1
        with self.assertRaises(ValueError): app.push_pcm(pcm, start_sample=0)
        self.assertTrue(app.faulted)
        self.assertEqual(app.next_sample, 0)
        self.assertIsNone(app._beam._core.control_at)

    def test_zero_final_closes_and_releases_context(self):
        app = self.app({'das': {'enabled': True}})
        out = app.push_pcm(np.empty((4, 0), dtype=np.int32), start_sample=0, final=True)
        self.assertEqual(out.tolist(), [0]*8)
        self.assertTrue(app.closed)
        self.assertFalse(app.faulted)
        self.assertIsNone(app._solver._context)
        with self.assertRaises(RuntimeError): app.push_pcm(np.empty((4, 0), dtype=np.int32), start_sample=8, final=True)
        app.close()

    def test_software_axes_explicit_only(self):
        axes = dict(config=dict(rotation=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    yaw_limits_deg=[-180, 180], pitch_limits_deg=[-90, 90],
                    max_yaw_rate_deg_s=60, max_pitch_rate_deg_s=60),
                    initial_yaw_deg=0, initial_pitch_deg=0, initial_time_s=0)
        app = self.app({'axes': axes, 'direction_filter': {'confirm_frames': 1}})
        result = app.process_frame(self.frame(), capture_sample=480, now_sample=480)
        self.assertTrue(result['axis_setpoint']['command_valid'])
        self.assertTrue(result['axis_setpoint']['software_only'])
        self.assertLessEqual(result['axis_setpoint']['yaw_deg'], .6)
        self.assertFalse(result['motion_requested'])
        self.assertEqual(result['result']['servo_cmd_valid'], 0)

    def test_configuration_is_strict_idempotent_and_defensively_copied(self):
        cfg = normalize_pipeline_config({'calibration': {'schema': 1,
                                         'channel_delay_samples': [.1, 0, 0, 0]}})
        self.assertEqual(cfg, normalize_pipeline_config(cfg))
        self.assertEqual(solver_options_from_config(cfg)['channel_delay_samples'], [.1, 0, 0, 0])
        for wrong in ({'unknown': 1}, {'solver_options': {'channel_delay_samples': [0]*4}},
                      {'calibration_source': ' '}, {'das': {'enabled': 1}},
                      {'calibration': {'schema': 1, 'channel_gain': [0]*4}}):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                normalize_pipeline_config(wrong)
        app = self.app(cfg)
        cfg['calibration']['channel_delay_samples'][0] = .9
        meta = app.metadata()
        json.dumps(meta)
        self.assertEqual(meta['solver_options']['channel_delay_samples'][0], .1)
        meta['geometry']['microphones'][0]['xyz_mm'][0] = 0
        self.assertNotEqual(app.metadata()['geometry']['microphones'][0]['xyz_mm'][0], 0)
        for attr in ('session_id', 'target_id', 'sample_rate_hz'):
            with self.assertRaises(AttributeError): setattr(app, attr, 'changed')

    def test_disabled_das_has_no_numpy_import_and_namespace_import_works(self):
        code = ("import sys; from software.tetra3d.linux.pipeline_3d import normalize_pipeline_config; "
                "assert normalize_pipeline_config()['das']['enabled'] is False; "
                "assert 'numpy' not in sys.modules; print('NO_NUMPY_IMPORT')")
        proc = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                              check=True, capture_output=True, text=True)
        self.assertIn('NO_NUMPY_IMPORT', proc.stdout)

    def test_delayed_source_expires_from_capture_not_delivery(self):
        app = self.app({'direction_filter': {'confirm_frames': 1}})
        record = app.process_frame(self.frame(), capture_sample=0, now_sample=4800)
        self.assertTrue(record['filtered_direction']['valid'])
        self.assertEqual(record['filtered_direction']['valid_until_s'], .25)
        self.assertFalse(app.poll(now_sample=12000)['filtered_direction']['valid'])
        with self.assertRaises(ValueError): app.poll(now_sample=11999)
        self.assertTrue(app.faulted)


if __name__ == '__main__':
    unittest.main(verbosity=2)
