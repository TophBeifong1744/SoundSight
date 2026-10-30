"""有界功能验证；官方音频和合成夹具均不是参与者效果评价。"""
import copy
import json
from pathlib import Path
import socket
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

import speaker_verify as sv

RUN = Path(tempfile.mkdtemp(prefix="selftest-", dir=sv.ROOT / "runs"))
SAMPLE = sv.ROOT / "private" / "official-smoke" / "example1.wav"


class AudioInputTests(unittest.TestCase):
    def audio(self, name, data, rate=16000, subtype="PCM_16"):
        path = RUN / name
        sf.write(path, data, rate, subtype=subtype)
        return path

    def reject(self, path, reason, **kwargs):
        with self.assertRaises(sv.InputError) as context:
            sv.read_audio(path, **kwargs)
        self.assertEqual(context.exception.reason, reason)

    def test_silence_and_short_are_not_non_target(self):
        self.reject(self.audio("silence.wav", np.zeros(48000)), "SILENCE_OR_TOO_QUIET")
        self.reject(self.audio("short.wav", np.zeros(1600)), "AUDIO_TOO_SHORT")

    def test_broken_and_missing(self):
        broken = RUN / "broken.wav"
        broken.write_bytes(b"not an audio file")
        self.reject(broken, "BAD_AUDIO_FILE")
        self.reject(RUN / "missing.wav", "AUDIO_NOT_FOUND")

    def test_clipped_and_nonfinite(self):
        clipped = np.tile(np.array([-1.0, 1.0]), 24000)
        self.reject(self.audio("clipped.wav", clipped), "EXCESSIVE_CLIPPING")
        self.reject(self.audio("nan.wav", np.full(48000, np.nan), subtype="FLOAT"), "NONFINITE_AUDIO")

    def test_stereo_requires_explicit_channel(self):
        t = np.arange(48000) / 16000
        path = self.audio("stereo.wav", np.stack([np.sin(2*np.pi*440*t)*.1, np.zeros(48000)], axis=1))
        self.reject(path, "CHANNEL_REQUIRED")
        wave, meta = sv.read_audio(path, channel=0)
        self.assertEqual(meta["selected_channel"], 0)
        self.assertEqual(len(wave), 48000)
        self.reject(path, "INVALID_CHANNEL", channel=2)

    def test_resample_preserves_duration(self):
        rate = 44100
        wave = np.sin(2*np.pi*440*np.arange(rate*2)/rate)*.1
        converted, meta = sv.read_audio(self.audio("resample.wav", wave, rate))
        self.assertEqual(len(converted), 32000)
        self.assertEqual(meta["source_sample_rate"], rate)

    def test_long_and_unsupported_rate(self):
        self.reject(self.audio("long.wav", np.zeros(16000*61)), "AUDIO_TOO_LONG")
        self.reject(self.audio("rate.wav", np.zeros(12000), 4000), "UNSUPPORTED_SAMPLE_RATE")


class DecisionAndSeparationTests(unittest.TestCase):
    def test_threshold_boundaries_and_nan(self):
        self.assertEqual(sv.decide(.2, .2, .5), "non_target")
        self.assertEqual(sv.decide(.5, .2, .5), "target")
        self.assertEqual(sv.decide(.35, .2, .5), "insufficient")
        for score, low, high in [(float("nan"), .2, .5), (.4, .5, .2)]:
            with self.assertRaises(sv.InputError):
                sv.decide(score, low, high)

    def test_calibration_keeps_overlap_as_abstention(self):
        rows = [{"score": x, "is_target": True} for x in [.3, .6, .7]]
        rows += [{"score": x, "is_target": False} for x in [.1, .2, .4]]
        low, high = sv.fit_thresholds(rows)
        self.assertEqual(sv.decide(.3, low, high), "insufficient")
        self.assertEqual(sv.decide(.4, low, high), "insufficient")
        self.assertEqual(sv.decide(.7, low, high), "target")
        self.assertEqual(sv.decide(.1, low, high), "non_target")

    def test_error_rates_use_separate_denominators(self):
        rows = [{"score": .8, "is_target": True, "speaker_id": "P01"},
                {"score": None, "is_target": True, "speaker_id": "P01"},
                {"score": .8, "is_target": False, "speaker_id": "P02"},
                {"score": .1, "is_target": False, "speaker_id": "P03"}]
        report = sv.summarize(rows, .2, .5)
        self.assertEqual(report["false_accept_rate_all_non_target"], .5)
        self.assertEqual(report["false_reject_rate_all_target"], 0)
        self.assertEqual(report["insufficient_rate"], .25)

    def test_session_leakage_and_permission_rejected(self):
        template = {"target_id": "P01", "enrollment": [{"session_id": "S1", "recording_id": "enroll01"}]}
        data = {"split": "dev", "target_id": "P01", "items": [
            {"path": "absent.wav", "recording_id": "dev01", "speaker_id": "P01", "session_id": "S1", "usage_authorized": True}]}
        path = RUN / "manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(sv.InputError, "SESSION_REUSED"):
            sv.manifest_items(path, "dev", template)
        data["items"][0].update(session_id="S2", usage_authorized=False)
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(sv.InputError, "PERMISSION"):
            sv.manifest_items(path, "dev", template)

    def test_output_and_template_path_confinement(self):
        with self.assertRaises(sv.InputError):
            sv.Templates(sv.ROOT.parent / "outside")
        with self.assertRaises(sv.InputError):
            sv.Templates().path("../escape")


class RealModelSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.no_network = patch.object(socket.socket, "connect", side_effect=AssertionError("offline run attempted network"))
        cls.no_network.start()
        cls.engine = sv.Engine(4)
        cls.store = sv.Templates(RUN / "temporary-templates")
        cls.enroll_result = cls.store.enroll("SMOKE", [SAMPLE], "official_sample", cls.engine)
        cls.template = cls.store.load("SMOKE", cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.no_network.stop()

    def test_embedding_matches_official_encode_batch(self):
        from speechbrain.inference.classifiers import EncoderClassifier
        engine = self.engine
        torch = engine.torch
        wave, _ = sv.read_audio(SAMPLE)
        spans = engine.speech_timestamps(torch.from_numpy(wave), engine.vad, sampling_rate=16000, threshold=.5, speech_pad_ms=0)
        speech = np.concatenate([wave[s["start"]:s["end"]] for s in spans])
        self.assertLessEqual(len(speech), 64000)
        wrapper = types.SimpleNamespace(device="cpu", mods=types.SimpleNamespace(
            compute_features=engine.fbank, mean_var_norm=engine.normalize, embedding_model=engine.encoder))
        with torch.inference_mode():
            reference = EncoderClassifier.encode_batch(wrapper, torch.from_numpy(speech)).reshape(-1).numpy()
        actual, _ = engine.extract(SAMPLE)
        np.testing.assert_allclose(actual, sv.unit(reference), atol=1e-6, rtol=1e-5)

    def test_identical_audio_is_flagged_not_accuracy_evidence(self):
        result = sv.verify(self.engine, self.template, SAMPLE, demo_thresholds=[.2, .5])
        self.assertGreater(result["score"], .9999)
        self.assertEqual(result["state"], "insufficient")
        self.assertEqual(result["reason"], "ENROLLMENT_RECORDING_REUSED")

    def test_uncalibrated_valid_audio_abstains(self):
        sample2 = SAMPLE.parent / "example2.flac"
        result = sv.verify(self.engine, self.template, sample2)
        self.assertEqual(result["state"], "insufficient")
        self.assertEqual(result["reason"], "THRESHOLDS_NOT_CALIBRATED")
        self.assertTrue(np.isfinite(result["score"]))
        (RUN / "second-example-score.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    def test_invalid_input_stays_insufficient(self):
        result = sv.verify(self.engine, self.template, RUN / "missing.wav")
        self.assertEqual(result["state"], "insufficient")
        self.assertEqual(result["reason"], "AUDIO_NOT_FOUND")

    def test_noise_has_no_valid_speech(self):
        path = RUN / "noise.wav"
        sf.write(path, np.random.default_rng(49).normal(0, .025, 48000), 16000)
        result = sv.verify(self.engine, self.template, path)
        self.assertEqual(result["state"], "insufficient")
        self.assertIn(result["reason"], {"NO_VALID_SPEECH", "INSUFFICIENT_SPEECH"})

    def test_template_no_overwrite_and_delete_only_template(self):
        before = sv.file_hash(SAMPLE)
        with self.assertRaisesRegex(sv.InputError, "TEMPLATE_EXISTS"):
            self.store.enroll("SMOKE", [SAMPLE], "again", self.engine)
        path = self.store.path("DELETE_TEST")
        duplicate = copy.deepcopy(self.template)
        duplicate["target_id"] = "DELETE_TEST"
        sv.save_new(path, duplicate)
        self.store.delete("DELETE_TEST")
        self.assertFalse(path.exists())
        self.assertEqual(sv.file_hash(SAMPLE), before)
        self.assertTrue(self.store.path("SMOKE").exists())

    def test_duplicate_enrollment_and_cross_split_audio(self):
        with self.assertRaisesRegex(sv.InputError, "DUPLICATE_ENROLLMENT"):
            self.store.enroll("DUPLICATE", [SAMPLE, SAMPLE], "S1", self.engine)
        items = [{"recording_id": "different_name", "speaker_id": "SMOKE", "session_id": "S2", "resolved_path": SAMPLE}]
        with self.assertRaisesRegex(sv.InputError, "AUDIO_LEAKAGE"):
            sv.score_items(self.engine, self.template, items)

    def test_template_model_mismatch(self):
        mismatched = copy.deepcopy(self.template)
        mismatched.update(target_id="MISMATCH", model_fingerprint="wrong")
        sv.save_new(self.store.path("MISMATCH"), mismatched)
        with self.assertRaisesRegex(sv.InputError, "TEMPLATE_MODEL_MISMATCH"):
            self.store.load("MISMATCH", self.engine)

    def test_steady_state_cost(self):
        results = []
        for _ in range(3):
            _, meta = self.engine.extract(SAMPLE)
            results.append(meta)
        memory = sv.psutil.Process().memory_info()
        report = {"evidence": "official example repeated for throughput only; no identity accuracy claim",
                  "model_load_seconds_in_test_process": self.engine.load_seconds,
                  "cpu_threads": self.engine.threads, "runs": results,
                  "median_processing_seconds": float(np.median([r["processing_seconds"] for r in results])),
                  "peak_rss_mib": getattr(memory, "peak_wset", memory.rss) / 2**20,
                  "model_identity": self.engine.model_identity}
        (RUN / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.assertTrue(all(r["processing_seconds"] > 0 for r in results))


if __name__ == "__main__":
    print(f"Evidence directory: {RUN}", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (RUN / "result.json").write_text(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures),
                                               "errors": len(result.errors), "passed": result.wasSuccessful(),
                                               "claim": "functional self-check, not independent review or real speaker evaluation"}, indent=2), encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
