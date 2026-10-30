"""Enrollment/selection failure tests. Fake capture and vectors, no hardware."""
import contextlib
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
for folder in ('software/ps', 'software/ps/speaker_core', 'software/tetra3d/linux'):
    sys.path.insert(0, str(ROOT/folder))
import speaker_enrollment as enroll
import speaker_targets as targets
import speaker_settings
import speaker_models
from speaker_follow_setup import configure, import_profile
from speaker_permission import load_settings


def fixture(root):
    core = root/'software/ps/speaker_core'
    (core/'models').mkdir(parents=True)
    for name in ('pipeline_backend', 'models/int8-head.onnx', 'models/silero_vad.onnx', 'frontend.f32'):
        (core/name).write_bytes(b'fake asset for unit tests')
    (core/'speaker-template.json').write_text(json.dumps(dict(template=[1.]+[0.]*191, low=.3, high=.7)))
    hashes = {name: targets.digest(core/name) for name in ('pipeline_backend', 'models/int8-head.onnx',
              'models/silero_vad.onnx', 'frontend.f32', 'speaker-template.json')}
    (core/'live-assets.json').write_text(json.dumps(dict(sha256=hashes)))
    return core, hashes


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.core, self.assets = fixture(self.root)
        self.recording = self.root/'logs/pcm-test'
        self.recording.mkdir(parents=True)
        self.record = Mock(return_value=self.recording)
        self.extract = Mock(return_value=dict(vector=[0., 1.]+[0.]*190, quality=dict(eligible_windows=1)))
        self.models = patch.object(speaker_models, 'verify_candidates', return_value={})
        self.models.start(); self.addCleanup(self.models.stop)

    def enroll(self, name='alice'):
        return enroll.enroll_locked(self.root, name, record=self.record, extract=self.extract,
                                    emit=Mock(), sleep=Mock())

    def test_one_three_second_clip_saved_not_activated(self):
        result = self.enroll()
        self.record.assert_called_once_with(self.root, 3.)
        self.extract.assert_called_once()
        self.assertFalse(result['selected'])
        self.assertEqual(result['motion_commands'], 0)
        self.assertFalse((self.root/targets.SELECTOR).exists())
        cfg = targets.load_profile(self.root, 'alice', self.assets)
        self.assertEqual(cfg['template'][1], 1.)
        self.assertEqual(len(cfg['clips']), 1)
        self.assertTrue(cfg['score_only'])

    def test_select_clear_old_permission_and_runtime_load_new_template(self):
        self.enroll()
        configure(self.root, .65, 2.)
        targets.select(self.root, 'alice')
        self.assertIsNone(load_settings(self.root)['threshold'])
        self.assertEqual(load_settings(self.root)['permit_seconds'], 2.)
        active = speaker_settings.verify_assets(self.core)
        self.assertEqual(active['target_id'], 'alice')
        self.assertEqual(active['template'][1], 1.)
        self.assertEqual(targets.list_targets(self.root)['active_target'], 'alice')
        targets.select(self.root, 'P01')
        self.assertEqual(speaker_settings.verify_assets(self.core)['template'][0], 1.)

    def test_two_people_coexist_and_switch(self):
        self.enroll('alice'); self.enroll('bob')
        targets.select(self.root, 'alice'); targets.select(self.root, 'bob')
        self.assertEqual({r['target_id'] for r in targets.list_targets(self.root)['targets']}, {'P01', 'alice', 'bob'})

    def test_failed_capture_does_not_publish_or_call_model(self):
        self.record.side_effect = RuntimeError('DMA fault')
        with self.assertRaises(RuntimeError): self.enroll()
        self.extract.assert_not_called()
        self.assertFalse(targets.profile_path(self.root, 'alice').exists())

    def test_cancel_or_silence_preserves_old_selected_profile_and_recording(self):
        self.enroll('old'); targets.select(self.root, 'old')
        previous = (self.root/targets.SELECTOR).read_bytes()
        for error in (ValueError('NOT_ENOUGH_SPEECH'), KeyboardInterrupt()):
            self.extract.side_effect = error
            with self.assertRaises(type(error)): self.enroll('new')
            self.assertEqual((self.root/targets.SELECTOR).read_bytes(), previous)
            self.assertFalse(targets.profile_path(self.root, 'new').exists())
            self.assertTrue(self.recording.is_dir())

    def test_existing_profile_never_overwritten(self):
        self.enroll()
        old = targets.profile_path(self.root, 'alice').read_bytes()
        for name in ('alice', 'ALICE'):
            with self.assertRaises(ValueError): self.enroll(name)
        self.assertEqual(targets.profile_path(self.root, 'alice').read_bytes(), old)
        self.assertEqual(self.record.call_count, 1)

    def test_names_and_duration_fail_before_capture(self):
        for name in ('../x', '/tmp/x', '', 'a/b', 'P01', 'P02', 'p02-v1', 'CON', 'alice.json'):
            with self.assertRaises(ValueError): self.enroll(name)
        for seconds in (1., 10.1, float('nan'), True):
            with self.assertRaises(ValueError): enroll.validate_request(self.root, 'alice', seconds)
        enroll.validate_request(self.root, 'alice', 2.)
        self.record.assert_not_called()

    def test_unknown_target_does_not_disable_current_settings(self):
        configure(self.root, .7)
        with self.assertRaises(FileNotFoundError): targets.select(self.root, 'missing')
        self.assertEqual(load_settings(self.root)['threshold'], .7)

    def test_selector_write_failure_leaves_gate_disabled(self):
        self.enroll(); configure(self.root, .7)
        with patch.object(targets, 'atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): targets.select(self.root, 'alice')
        self.assertIsNone(load_settings(self.root)['threshold'])
        self.assertFalse((self.root/targets.SELECTOR).exists())

    def test_corrupted_or_different_model_profile_refused(self):
        self.enroll(); targets.select(self.root, 'alice')
        path = targets.profile_path(self.root, 'alice')
        cfg = json.loads(path.read_text()); cfg['candidate_models'] = {}
        path.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError): speaker_settings.verify_assets(self.core)
        with self.assertRaises(ValueError): targets.select(self.root, 'alice')

    def test_legacy_p02_unchanged_compatibility(self):
        path = self.root/targets.PROFILE
        path.parent.mkdir(parents=True)
        cfg = dict(schema=1, target_id='P02', assets=self.assets, template=[1.]+[0.]*191,
                   score_only=True, recognition_qualified=False, low=None, high=None, enrollment_ids=targets.ENROLL)
        path.write_text(json.dumps(cfg)); old = path.read_bytes()
        targets.select(self.root, 'P02')
        self.assertEqual(speaker_settings.verify_assets(self.core)['target_id'], 'P02')
        self.assertEqual(path.read_bytes(), old)

    def test_custom_profile_import(self):
        self.enroll(); targets.select(self.root, 'alice')
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp); fixture(dest)
            configure(dest, .65)
            import_profile(dest, self.root)
            self.assertEqual(speaker_settings.verify_assets(dest/'software/ps/speaker_core')['target_id'], 'alice')
            self.assertIsNone(load_settings(dest)['threshold'])

    def test_runtime_reads_target_and_threshold_only_inside_owner_lock(self):
        import speaker_runtime_3d as runtime
        from types import SimpleNamespace
        locked = []
        @contextlib.contextmanager
        def owner(_):
            locked.append(True)
            try: yield
            finally: locked.pop()
        def checked(value):
            def read(*a, **k):
                self.assertEqual(locked, [True], 'target/threshold read before owner lock')
                return value
            return read
        args = SimpleNamespace(lock_file='unused', min_level=1, window_frames=20, min_valid=12,
                               axes='off', frames=1, seconds=1, geometry={}, calibration={})
        with patch.object(runtime, 'single_owner', owner), \
             patch.object(runtime, 'CaptureScheduling', return_value=contextlib.nullcontext()), \
             patch.object(runtime, 'check_speaker', side_effect=checked({})), \
             patch.object(runtime, 'verify_assets', side_effect=checked(dict(target_id='alice'))), \
             patch.object(runtime, 'verify_candidates', side_effect=checked({})), \
             patch.object(runtime, 'load_settings', side_effect=checked(dict(threshold=None))), \
             patch.object(runtime, 'audio_hwh', return_value={}), \
             patch.object(runtime, 'check_hwh', return_value=(0, 0)), \
             patch.object(runtime.board_tools, 'load_api', side_effect=RuntimeError('mock stops before hardware')):
            self.assertEqual(runtime.run(args, self.root), 1)

    def test_axes_revoke_only_and_drain_failure_aborts(self):
        import motion_3d
        ip = Mock(); axes = Mock()
        with patch.object(motion_3d, 'DualAxis', return_value=axes):
            enroll.disable_axes(ip)
            self.assertEqual([c[0] for c in axes.mock_calls], ['identify', 'revoke', 'wait_drained'])
            axes.wait_drained.side_effect = TimeoutError('still active')
            with self.assertRaises(TimeoutError): enroll.disable_axes(ip)
        ip.write.assert_not_called()  # Only the tested DualAxis.revoke path may write.

    def test_capture_failure_and_guard_wiring(self):
        import run_pcm
        def fake(**kw):
            self.assertIs(kw['capture_guard'], enroll.disable_axes)
            self.assertIsInstance(kw['owner_context'], contextlib.nullcontext)
            self.assertEqual(kw['blocks'], 282)
            kw['recording_callback'](self.recording, dict(result='PASS', dma_halted=True))
            return 0
        with patch.object(run_pcm, 'main', side_effect=fake):
            self.assertEqual(enroll.record_clip(self.root, 3.), self.recording)
        with patch.object(run_pcm, 'main', return_value=1):
            with self.assertRaises(RuntimeError): enroll.record_clip(self.root, 3.)

    def test_entry_owner_lock_conflict_no_recording(self):
        import board_3d, run_capture
        with patch.object(board_3d, 'check_hwh'), patch.object(run_capture, 'single_owner', side_effect=RuntimeError('busy')):
            with patch.object(enroll, 'enroll_locked') as work:
                with self.assertRaises(RuntimeError): enroll.run(self.root, 'alice')
                work.assert_not_called()

    def test_cli_defaults_and_no_axes_option(self):
        import board_3d
        args = board_3d.parser().parse_args(['speaker-enroll', 'alice'])
        self.assertEqual(args.seconds, 3.)
        with contextlib.redirect_stderr(__import__('io').StringIO()):
            with self.assertRaises(SystemExit): board_3d.parser().parse_args(['speaker-enroll', 'alice', '--axes', 'both'])


class ModelWindowTests(unittest.TestCase):
    def test_uniform_windows_and_silence_rejection(self):
        # Exercise parsing/VAD-window selection with independent deterministic native replies.
        from pcm_capture import PACKET_BYTES
        class Front:
            def __init__(self, *a, **k): self.samples = 0
            def close(self, **k): pass
            def run_pcm32(self, raw):
                self.samples += 512
                return []
        class Cache:
            active = True
            def __init__(self): self.samples = 0
            def push(self, p): self.samples += 512
            def snapshot(self, n): return dict(active=Cache.active, coverage=1., start_sample16=self.samples-16000)
        import stream_bench
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'result.json').write_text(json.dumps(dict(result='PASS', dma_halted=True, epoch=1)))
            with (p/'packets.bin').open('wb') as f:
                for i in range(282):
                    f.write(struct.pack('<8I', 0x43505353, 0x00200001, 1, i, i*512, 0, 512, 8192)+bytes(8192))
            with patch.object(stream_bench, 'Cache', Cache), patch.object(stream_bench, 'reset'):
                jobs, quality = enroll.eligible_jobs(p, p, Front)
                self.assertGreaterEqual(len(jobs), 1)
                self.assertEqual(quality['channel'], 0)
                Cache.active = False
                with self.assertRaisesRegex(ValueError, 'NOT_ENOUGH_SPEECH'): enroll.eligible_jobs(p, p, Front)
            # Corrupted sequence must be rejected, not converted into a template.
            raw = bytearray((p/'packets.bin').read_bytes()); raw[12:16] = struct.pack('<I', 5)
            (p/'packets.bin').write_bytes(raw)
            with patch.object(stream_bench, 'reset'):
                with self.assertRaises(ValueError): enroll.eligible_jobs(p, p, Front)


if __name__ == '__main__':
    unittest.main()
