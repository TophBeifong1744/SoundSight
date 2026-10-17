"""校准/评价合同测试；分数为显式合成夹具，不代替参与者录音。"""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import speaker_verify as sv

RUN = Path(tempfile.mkdtemp(prefix="calibration-contract-", dir=sv.ROOT / "runs"))


class CalibrationContractTests(unittest.TestCase):
    def setUp(self):
        self.template_path = RUN / "template.json"
        self.template = {"schema": 1, "target_id": "P01", "model_fingerprint": "test-only",
                         "embedding": [1.0] + [0.0]*191,
                         "enrollment": [{"recording_id": "enroll1", "session_id": "S1", "file_sha256": "enroll-file", "audio_sha256": "enroll-pcm"}]}
        self.template_path.write_text(json.dumps(self.template), encoding="utf-8")
        self.calibration = {"schema": 1, "status": "DEVELOPMENT_CALIBRATED", "target_id": "P01",
                            "model_fingerprint": "test-only", "template_sha256": sv.file_hash(self.template_path),
                            "low": .2, "high": .5, "development_recordings": []}
        self.engine = types.SimpleNamespace(fingerprint="test-only")
        self.cal_path = RUN / "calibration.json"

    def test_calibration_identity_and_template_binding(self):
        self.cal_path.write_text(json.dumps(self.calibration), encoding="utf-8")
        loaded = sv.load_calibration(self.cal_path, self.engine, self.template, self.template_path)
        self.assertEqual((loaded["low"], loaded["high"]), (.2, .5))
        self.template_path.write_text(json.dumps({**self.template, "extra": "changed"}), encoding="utf-8")
        with self.assertRaisesRegex(sv.InputError, "CALIBRATION_TEMPLATE_MISMATCH"):
            sv.load_calibration(self.cal_path, self.engine, self.template, self.template_path)

    def test_invalid_threshold_and_nan_rejected(self):
        for low, high in [(float("nan"), .5), (.6, .2)]:
            self.calibration.update(low=low, high=high)
            self.cal_path.write_text(json.dumps(self.calibration), encoding="utf-8")
            with self.assertRaises(sv.InputError):
                sv.load_calibration(self.cal_path, self.engine, self.template, self.template_path)

    def test_final_split_cannot_reuse_development_session(self):
        data = {"split": "test", "target_id": "P01", "items": [
            {"recording_id": "test01", "session_id": "S2", "speaker_id": "P02", "usage_authorized": True, "path": "x.wav"}]}
        path = RUN / "test-manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(sv.InputError, "SESSION_REUSED"):
            sv.manifest_items(path, "test", self.template, [{"recording_id": "dev01", "speaker_id": "P02", "session_id": "S2"}])

    def test_repeated_invalid_audio_is_still_duplicate(self):
        path = RUN / "silence.wav"
        sf.write(path, np.zeros(48000), 16000)
        items = [{"recording_id": "silence"+str(i), "speaker_id": "P02", "session_id": "S3", "resolved_path": path} for i in range(2)]
        engine = types.SimpleNamespace(extract=lambda *a: sv.read_audio(path))
        with self.assertRaisesRegex(sv.InputError, "AUDIO_LEAKAGE_OR_DUPLICATE"):
            sv.score_items(engine, self.template, items)

    def test_evaluation_summary_does_not_change_thresholds(self):
        before = json.dumps(self.calibration, sort_keys=True)
        rows = [{"speaker_id": "P01", "score": .7, "is_target": True},
                {"speaker_id": "P02", "score": .8, "is_target": False}]
        result = sv.summarize(rows, self.calibration["low"], self.calibration["high"])
        self.assertEqual(result["false_accepts"], 1)
        self.assertEqual(json.dumps(self.calibration, sort_keys=True), before)

    def test_no_overwrite_of_frozen_output(self):
        path = RUN / "frozen.json"
        if path.exists():
            before = path.read_bytes()
        else:
            sv.save_new(path, self.calibration)
            before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            sv.save_new(path, {"low": .9})
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    print(f"Evidence directory: {RUN}", flush=True)
    unittest.main(verbosity=2)
