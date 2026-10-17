"""本地目标说话人验证：文件输入、模板管理、开发校准与冻结评价。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import time

PROCESS_STARTED = time.perf_counter()
ROOT = Path(__file__).resolve().parent
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
os.environ["TORCH_HOME"] = str(ROOT / ".cache" / "torch")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import psutil
import soundfile as sf
from scipy.signal import resample_poly

SR = 16000
PREPROCESS = {"version": 1, "sample_rate": SR, "min_speech_seconds": 1.5,
              "max_file_seconds": 60, "max_speech_seconds": 20,
              "chunk_seconds": 4, "vad_threshold": 0.5,
              "max_clip_fraction": 0.01, "silence_rms": 1e-5}
LABELS = {"target": "目标", "non_target": "非目标", "insufficient": "证据不足"}


class InputError(ValueError):
    """可解释的输入拒绝，不强行归为非目标。"""
    def __init__(self, reason, detail=""):
        self.reason, self.detail = reason, detail
        super().__init__(f"{reason}: {detail}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def identity(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise InputError("INVALID_ID", "匿名ID只允许字母、数字、下划线、连字符，最长64位")
    return value


def owned_path(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise InputError("OUTPUT_OUTSIDE_RESEARCH", str(resolved))
    return resolved


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_new(path, value):
    """独占创建，不覆盖旧模板、冻结阈值或运行证据。"""
    path = owned_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def unit(vector):
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if vector.shape != (192,) or not np.isfinite(vector).all() or norm < 1e-8:
        raise InputError("INVALID_EMBEDDING")
    return vector / norm


def read_audio(path, channel=None):
    """检查格式及电平，按明确声道选取，再统一为16kHz；保留原始录音。"""
    path = Path(path)
    if not path.is_file():
        raise InputError("AUDIO_NOT_FOUND", str(path))
    try:
        info = sf.info(path)
        if info.format not in {"WAV", "WAVEX", "FLAC"}:
            raise InputError("UNSUPPORTED_FORMAT", "请提供WAV或FLAC")
        if info.samplerate < 8000 or info.samplerate > 96000:
            raise InputError("UNSUPPORTED_SAMPLE_RATE", str(info.samplerate))
        if not 1 <= info.channels <= 8:
            raise InputError("UNSUPPORTED_CHANNEL_COUNT")
        seconds = info.frames / info.samplerate
        if seconds > PREPROCESS["max_file_seconds"]:
            raise InputError("AUDIO_TOO_LONG", "单文件上限60秒，请提供独立话段")
        if seconds < PREPROCESS["min_speech_seconds"]:
            raise InputError("AUDIO_TOO_SHORT", f"总时长{seconds:.3f}秒")
        if info.channels > 1 and channel is None:
            raise InputError("CHANNEL_REQUIRED", "多声道需用 --channel 指定从0开始的声道")
        selected = 0 if channel is None else channel
        if not 0 <= selected < info.channels:
            raise InputError("INVALID_CHANNEL")
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError) as exc:
        raise InputError("BAD_AUDIO_FILE", str(exc)) from exc
    wave = np.ascontiguousarray(audio[:, selected])
    if not np.isfinite(wave).all():
        raise InputError("NONFINITE_AUDIO")
    if float(np.max(np.abs(wave))) > 1.001:
        raise InputError("AUDIO_OUT_OF_RANGE", "浮点音频幅值必须在[-1,1]")
    clip_fraction = float(np.mean(np.abs(wave) >= 0.999))
    if clip_fraction > PREPROCESS["max_clip_fraction"]:
        raise InputError("EXCESSIVE_CLIPPING", f"{clip_fraction:.3%}")
    wave = wave - wave.mean()
    rms = float(np.sqrt(np.mean(wave ** 2)))
    if rms < PREPROCESS["silence_rms"]:
        raise InputError("SILENCE_OR_TOO_QUIET")
    if rate != SR:
        common = math.gcd(rate, SR)
        wave = resample_poly(wave, SR // common, rate // common).astype(np.float32)
    meta = {"file_sha256": file_hash(path), "audio_sha256": digest(wave.astype("<f4").tobytes()),
            "source_sample_rate": rate, "source_channels": info.channels, "selected_channel": selected,
            "duration_seconds": seconds, "rms_dbfs": 20 * math.log10(rms), "clip_fraction": clip_fraction}
    return wave, meta


class Engine:
    """仅加载本地、固定哈希的官方网络；不调用云端推理。"""
    def __init__(self, threads=4):
        start = time.perf_counter()
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
        import silero_vad
        from speechbrain.lobes.features import Fbank
        from speechbrain.processing.features import InputNormalization
        from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
        self.torch = torch
        torch.set_num_threads(threads)
        torch.set_num_interop_threads(1)
        self.lock = read_json(ROOT / "model-lock.json")
        weight = ROOT / "models" / "ecapa" / "embedding_model.ckpt"
        if file_hash(weight) != self.lock["files"]["embedding_model.ckpt"]["sha256"]:
            raise InputError("MODEL_HASH_MISMATCH")
        self.vad = load_silero_vad(onnx=False)
        # 官方加载器可能调整线程数，恢复本研究的进程内预算。
        torch.set_num_threads(threads)
        self.speech_timestamps = get_speech_timestamps
        self.fbank = Fbank(n_mels=80).eval()
        self.normalize = InputNormalization(norm_type="sentence", std_norm=False).eval()
        self.encoder = ECAPA_TDNN(input_size=80, channels=[1024, 1024, 1024, 1024, 3072],
                                 kernel_sizes=[5, 3, 3, 3, 1], dilations=[1, 2, 3, 4, 1],
                                 attention_channels=128, lin_neurons=192).eval()
        self.encoder.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True), strict=True)
        vad_weight = Path(silero_vad.__file__).parent / "data" / "silero_vad.jit"
        self.model_identity = {"repository": self.lock["repository"], "revision": self.lock["revision"],
                               "embedding_sha256": file_hash(weight), "vad_sha256": file_hash(vad_weight),
                               "packages": {p: importlib.metadata.version(p) for p in ["torch", "torchaudio", "speechbrain", "silero-vad", "numpy", "scipy", "soundfile"]},
                               "preprocess": PREPROCESS}
        self.fingerprint = digest(json.dumps(self.model_identity, sort_keys=True).encode())
        self.load_seconds = time.perf_counter() - start
        self.threads = threads

    def extract(self, path, channel=None):
        start = time.perf_counter()
        wave, meta = read_audio(path, channel)
        torch = self.torch
        with torch.inference_mode():
            spans = self.speech_timestamps(torch.from_numpy(wave), self.vad, sampling_rate=SR,
                                           threshold=PREPROCESS["vad_threshold"], speech_pad_ms=0)
            count = sum(span["end"] - span["start"] for span in spans)
            if count / SR < PREPROCESS["min_speech_seconds"]:
                reason = "NO_VALID_SPEECH" if count == 0 else "INSUFFICIENT_SPEECH"
                raise InputError(reason, f"VAD有效语音{count / SR:.3f}秒，需要至少1.5秒")
            speech = np.concatenate([wave[s["start"]:s["end"]] for s in spans])
            # 对长语音做有界分块，最后短块与前块合并，避免极短特征主导。
            speech = speech[:PREPROCESS["max_speech_seconds"] * SR]
            chunks = list(np.array_split(speech, max(1, math.ceil(len(speech) / (PREPROCESS["chunk_seconds"] * SR)))))
            vectors = []
            for chunk in chunks:
                tensor = torch.from_numpy(np.ascontiguousarray(chunk)).unsqueeze(0)
                lengths = torch.ones(1)
                features = self.normalize(self.fbank(tensor), lengths)
                vector = self.encoder(features, lengths).reshape(-1).cpu().numpy()
                vectors.append(unit(vector))
        result = unit(np.average(vectors, axis=0, weights=[len(c) for c in chunks]))
        meta.update({"speech_seconds": count / SR, "used_speech_seconds": len(speech) / SR,
                     "speech_spans_seconds": [[s["start"] / SR, s["end"] / SR] for s in spans],
                     "speech_truncated": count > len(speech), "chunks": len(chunks),
                     "processing_seconds": time.perf_counter() - start})
        return result, meta


class Templates:
    def __init__(self, directory=None):
        self.directory = owned_path(directory or ROOT / "private" / "templates")

    def path(self, target_id):
        return self.directory / (identity(target_id) + ".json")

    def load(self, target_id, engine):
        data = read_json(self.path(target_id))
        if data.get("schema") != 1 or data.get("target_id") != target_id:
            raise InputError("INVALID_TEMPLATE")
        if data["model_fingerprint"] != engine.fingerprint:
            raise InputError("TEMPLATE_MODEL_MISMATCH", "模型或预处理变化后需重新登记和校准")
        data["embedding"] = unit(data["embedding"]).tolist()
        return data

    def enroll(self, target_id, files, session_id, engine, channel=None):
        identity(target_id)
        identity(session_id)
        if self.path(target_id).exists():
            raise InputError("TEMPLATE_EXISTS", "使用新匿名ID或先显式删除旧模板")
        vectors, recordings = [], []
        for path in files:
            vector, meta = engine.extract(path, channel)
            if any(x["audio_sha256"] == meta["audio_sha256"] or x["file_sha256"] == meta["file_sha256"] for x in recordings):
                raise InputError("DUPLICATE_ENROLLMENT")
            meta.update({"recording_id": identity(Path(path).stem), "session_id": session_id})
            vectors.append(vector)
            recordings.append(meta)
        template = {"schema": 1, "target_id": target_id, "model_fingerprint": engine.fingerprint,
                    "embedding": unit(np.mean(vectors, axis=0)).tolist(), "enrollment": recordings}
        save_new(self.path(target_id), template)
        return {"status": "enrolled", "target_id": target_id, "recordings": len(recordings),
                "speech_seconds": sum(x["speech_seconds"] for x in recordings),
                "template_path": str(self.path(target_id))}

    def delete(self, target_id):
        path = owned_path(self.path(target_id))
        if not path.is_file():
            raise InputError("TEMPLATE_NOT_FOUND")
        path.unlink()
        return {"status": "deleted", "target_id": target_id, "original_audio_deleted": False}


def decide(score, low, high):
    if not (math.isfinite(score) and -1 <= low < high <= 1):
        raise InputError("INVALID_SCORE_OR_THRESHOLDS")
    return "non_target" if score <= low else "target" if score >= high else "insufficient"


def overlap(meta, recordings):
    return any(meta["file_sha256"] == x["file_sha256"] or meta["audio_sha256"] == x["audio_sha256"] for x in recordings)


def load_calibration(path, engine, template, template_path):
    calibration = read_json(path)
    if calibration.get("schema") != 1 or calibration.get("status") != "DEVELOPMENT_CALIBRATED":
        raise InputError("INVALID_CALIBRATION")
    if calibration["model_fingerprint"] != engine.fingerprint or calibration["target_id"] != template["target_id"]:
        raise InputError("CALIBRATION_MODEL_OR_TARGET_MISMATCH")
    if calibration["template_sha256"] != file_hash(template_path):
        raise InputError("CALIBRATION_TEMPLATE_MISMATCH")
    decide(0, calibration["low"], calibration["high"])
    return calibration


def verify(engine, template, path, channel=None, calibration=None, demo_thresholds=None):
    result = {"target_id": template["target_id"], "state": "insufficient", "score": None,
              "score_type": "cosine_similarity_not_probability", "calibrated": calibration is not None,
              "model_fingerprint": engine.fingerprint}
    try:
        vector, meta = engine.extract(path, channel)
        score = float(np.clip(np.dot(unit(template["embedding"]), vector), -1, 1))
        result.update({"score": score, "audio": meta})
        if overlap(meta, template["enrollment"]):
            result["reason"] = "ENROLLMENT_RECORDING_REUSED"
        elif calibration is not None and overlap(meta, calibration["development_recordings"]):
            result["reason"] = "DEVELOPMENT_RECORDING_REUSED"
        elif calibration is None and demo_thresholds is None:
            result["reason"] = "THRESHOLDS_NOT_CALIBRATED"
        else:
            low, high = (calibration["low"], calibration["high"]) if calibration else demo_thresholds
            result.update({"state": decide(score, low, high), "thresholds": {"low": low, "high": high},
                           "reason": "FROZEN_DEVELOPMENT_THRESHOLDS" if calibration else "DEMO_ONLY_UNCALIBRATED",
                           "demo_only": calibration is None})
    except InputError as exc:
        result.update({"reason": exc.reason, "detail": exc.detail})
    result["label"] = LABELS[result["state"]]
    return result


def manifest_items(path, required_split, template, prior_recordings=()):
    manifest_path = Path(path).resolve()
    data = read_json(manifest_path)
    if data.get("split") != required_split or data.get("target_id") != template["target_id"]:
        raise InputError("MANIFEST_SPLIT_OR_TARGET_MISMATCH")
    items = data.get("items", [])
    if not items:
        raise InputError("EMPTY_MANIFEST")
    seen = set()
    # 同一人的同一录制时段不跨集合；依赖真实填写，不能自动发现裁剪或加噪泄漏。
    prior_sessions = {(template["target_id"], r["session_id"]) for r in template["enrollment"]}
    prior_sessions.update((r["speaker_id"], r["session_id"]) for r in prior_recordings)
    prior_ids = {r["recording_id"] for r in [*template["enrollment"], *prior_recordings]}
    for item in items:
        for key in ["recording_id", "speaker_id", "session_id"]:
            identity(item[key])
        if item.get("usage_authorized") is not True:
            raise InputError("RECORDING_PERMISSION_NOT_CONFIRMED", item["recording_id"])
        if item["recording_id"] in seen or item["recording_id"] in prior_ids:
            raise InputError("RECORDING_ID_REUSED", item["recording_id"])
        if (item["speaker_id"], item["session_id"]) in prior_sessions:
            raise InputError("RECORDING_SESSION_REUSED", item["recording_id"])
        seen.add(item["recording_id"])
        item["resolved_path"] = (manifest_path.parent / item["path"]).resolve()
    return items


def score_items(engine, template, items, prior_recordings=()):
    rows, seen = [], []
    seen_files = {r["file_sha256"] for r in [*template["enrollment"], *prior_recordings]}
    for item in items:
        row = {k: item[k] for k in ["recording_id", "speaker_id", "session_id"]}
        row.update({"condition": item.get("condition", "unspecified"),
                    "is_target": item["speaker_id"] == template["target_id"], "score": None})
        if item["resolved_path"].is_file():
            raw_hash = file_hash(item["resolved_path"])
            if raw_hash in seen_files:
                raise InputError("AUDIO_LEAKAGE_OR_DUPLICATE", item["recording_id"])
            seen_files.add(raw_hash)
            row["file_sha256"] = raw_hash
        try:
            vector, meta = engine.extract(item["resolved_path"], item.get("channel"))
            if overlap(meta, [*template["enrollment"], *prior_recordings, *seen]):
                raise InputError("AUDIO_LEAKAGE_OR_DUPLICATE", item["recording_id"])
            row.update(meta)
            row["score"] = float(np.clip(np.dot(unit(template["embedding"]), vector), -1, 1))
            seen.append(meta)
        except InputError as exc:
            if exc.reason == "AUDIO_LEAKAGE_OR_DUPLICATE":
                raise
            row.update({"reason": exc.reason, "detail": exc.detail})
        rows.append(row)
    return rows


def summarize(rows, low, high):
    for row in rows:
        row["state"] = "insufficient" if row["score"] is None else decide(row["score"], low, high)
    targets = [r for r in rows if r["is_target"]]
    others = [r for r in rows if not r["is_target"]]
    fa = sum(r["state"] == "target" for r in others)
    fr = sum(r["state"] == "non_target" for r in targets)
    unknown = sum(r["state"] == "insufficient" for r in rows)
    return {"speakers": len({r["speaker_id"] for r in rows}), "trials": len(rows),
            "target_trials": len(targets), "non_target_trials": len(others),
            "false_accepts": fa, "false_rejects": fr,
            "false_accept_rate_all_non_target": fa / len(others) if others else None,
            "false_reject_rate_all_target": fr / len(targets) if targets else None,
            "insufficient": unknown, "insufficient_rate": unknown / len(rows) if rows else None,
            "insufficient_target": sum(r["state"] == "insufficient" for r in targets),
            "insufficient_non_target": sum(r["state"] == "insufficient" for r in others),
            "claim_scope": "observed sample only; insufficient is reported separately, not correct"}


def fit_thresholds(rows):
    positives = [r["score"] for r in rows if r["is_target"] and r["score"] is not None]
    negatives = [r["score"] for r in rows if not r["is_target"] and r["score"] is not None]
    if min(len(positives), len(negatives)) < 3:
        raise InputError("INSUFFICIENT_DEVELOPMENT_TRIALS", "至少3条有效目标及3条有效非目标独立录音")
    # 两类重叠时留出拒判带；仅约束开发集经验错误，不宣称泛化误差上限。
    pmin, nmax = min(positives), max(negatives)
    if pmin > nmax:
        low, high = nmax + (pmin - nmax) * 0.4, nmax + (pmin - nmax) * 0.6
    else:
        low, high = pmin - 1e-6, nmax + 1e-6
    if not -1 <= low < high <= 1:
        raise InputError("NO_USABLE_THRESHOLDS", "开发分数无可用间隔，保留原始分数后检查输入")
    return low, high


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--threads", type=int, default=4, choices=range(1, 9))
    sub = p.add_subparsers(dest="command", required=True)
    enroll = sub.add_parser("enroll", help="登记匿名目标模板，不覆盖已有模板")
    enroll.add_argument("--id", required=True)
    enroll.add_argument("--session", required=True)
    enroll.add_argument("--channel", type=int)
    enroll.add_argument("files", nargs="+")
    verify_cmd = sub.add_parser("verify", help="验证一个独立话段；无校准默认拒判")
    verify_cmd.add_argument("--id", required=True)
    verify_cmd.add_argument("--channel", type=int)
    group = verify_cmd.add_mutually_exclusive_group()
    group.add_argument("--calibration")
    group.add_argument("--demo-thresholds", nargs=2, type=float, metavar=("LOW", "HIGH"), help="仅演示，明确标记未校准")
    verify_cmd.add_argument("--output")
    verify_cmd.add_argument("file")
    sub.add_parser("list", help="列出本地匿名模板")
    delete = sub.add_parser("delete", help="仅删除指定模板，不删录音")
    delete.add_argument("--id", required=True)
    delete.add_argument("--yes", action="store_true", required=True)
    sub.add_parser("info", help="校验并加载模型，输出版本与资源")
    for action in ["calibrate", "evaluate"]:
        cmd = sub.add_parser(action)
        cmd.add_argument("--id", required=True)
        cmd.add_argument("--manifest", required=True)
        cmd.add_argument("--output", required=True)
        if action == "evaluate":
            cmd.add_argument("--calibration", required=True)
    return p


def main():
    args = parser().parse_args()
    store = Templates()
    engine = None
    try:
        if args.command == "list":
            result = {"templates": [p.stem for p in sorted(store.directory.glob("*.json"))]}
        elif args.command == "delete":
            result = store.delete(args.id)
        else:
            engine = Engine(args.threads)
            if args.command == "info":
                result = {"status": "loaded", "model": engine.model_identity, "model_fingerprint": engine.fingerprint}
            elif args.command == "enroll":
                result = store.enroll(args.id, args.files, args.session, engine, args.channel)
            else:
                template = store.load(args.id, engine)
                cal_path = getattr(args, "calibration", None)
                calibration = load_calibration(cal_path, engine, template, store.path(args.id)) if cal_path else None
                if args.command == "verify":
                    if args.demo_thresholds:
                        decide(0, *args.demo_thresholds)
                    result = verify(engine, template, args.file, args.channel, calibration, args.demo_thresholds)
                else:
                    prior = calibration["development_recordings"] if calibration else []
                    items = manifest_items(args.manifest, "test" if calibration else "dev", template, prior)
                    rows = score_items(engine, template, items, prior)
                    low, high = (calibration["low"], calibration["high"]) if calibration else fit_thresholds(rows)
                    result = {"schema": 1, "status": "TEST_EVALUATED" if calibration else "DEVELOPMENT_CALIBRATED",
                              "target_id": args.id, "model_fingerprint": engine.fingerprint,
                              "template_sha256": file_hash(store.path(args.id)),
                              "manifest_sha256": file_hash(args.manifest), "low": low, "high": high,
                              "summary": summarize(rows, low, high), "trials": rows}
                    if calibration:
                        result["calibration_sha256"] = file_hash(cal_path)
                    else:
                        if any(r["score"] is None for r in rows):
                            raise InputError("INVALID_DEVELOPMENT_AUDIO", "校准录音有拒收项，先用verify逐条检查，不静默丢弃")
                        result["method"] = "development extrema with abstention band; no generalization guarantee"
                        result["development_recordings"] = [{k: r[k] for k in ["recording_id", "speaker_id", "session_id", "file_sha256", "audio_sha256"]} for r in rows]
        proc = psutil.Process()
        memory = proc.memory_info()
        result["runtime"] = {"process_seconds_so_far": time.perf_counter() - PROCESS_STARTED,
                             "model_load_seconds": engine.load_seconds if engine else None,
                             "rss_mib": memory.rss / 2**20,
                             "process_peak_rss_mib": getattr(memory, "peak_wset", memory.rss) / 2**20,
                             "cpu_threads": args.threads if engine else None}
        if getattr(args, "output", None):
            save_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (InputError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "reason": getattr(exc, "reason", type(exc).__name__),
                          "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
