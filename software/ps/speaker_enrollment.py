"""One bounded board recording -> private CP1/VF1 profile, never motion.

The board owner lock spans recording and extraction. Capture uses the
existing STOP/drain/DMA-buffer lifetime rules. Inference starts only after DMA
has halted, and uses exactly the deployed one-second frontend/embedding model.
"""
import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time

from speaker_targets import (target_name, profile_path, atomic_json, normalize,
                             cosine, load_profile)


def validate_request(root, target, seconds):
    target_name(target)
    if target.upper() in ('P01', 'P02', 'P02-V1'):
        raise ValueError('LEGACY_PROFILE_PRESERVED: choose a new name')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 2 <= seconds <= 10:
        raise ValueError('RECORD_SECONDS: choose 2..10 seconds')
    # Case-insensitive uniqueness also makes backups portable to Windows.
    directory = Path(root)/'speaker-profiles'
    if directory.exists() and any(p.name.casefold() == target.casefold() for p in directory.iterdir()):
        raise ValueError('TARGET_EXISTS_PRESERVED: use a new name for re-enrollment')


def disable_axes(ip):
    """Only revoke; no configure, ARM, COMMIT or angle write is used in enrollment."""
    from motion_3d import DualAxis
    axes = DualAxis(ip)
    axes.identify()
    axes.revoke()
    axes.wait_drained()


def record_clip(root, seconds):
    import run_pcm
    completed = []
    code = run_pcm.main(root=root, blocks=math.ceil(seconds*48000/512),
                        owner_context=contextlib.nullcontext(), capture_guard=disable_axes,
                        recording_callback=lambda path, report: completed.append((path, report)))
    if code or len(completed) != 1:
        raise RuntimeError('ENROLL_CAPTURE_FAILED: preserve logs/pcm-*; no profile changed')
    path, report = completed[0]
    if report['result'] != 'PASS' or not report['dma_halted'] or report.get('cleanup_errors'):
        raise RuntimeError('ENROLL_CAPTURE_NOT_HALTED_OR_VALID')
    return path


def eligible_jobs(core, recording, backend_factory=None):
    """Use non-overlapping one-second windows, never choose by speaker score."""
    sys.path.insert(0, str(core))
    from pipeline_bench import Backend
    from stream_bench import Cache, reset
    from speaker_models import backend_options
    from pcm_capture import PACKET_BYTES
    backend_factory = backend_factory or Backend
    report = json.loads((recording/'result.json').read_text())
    if report['result'] != 'PASS' or not report['dma_halted']:
        raise ValueError('INVALID_CAPTURE_REPORT')
    size = (recording/'packets.bin').stat().st_size
    if size % PACKET_BYTES or not 188 <= size//PACKET_BYTES <= 1032:
        raise ValueError('ENROLL_RECORDING_SIZE')
    front = backend_factory(core, role='front', **backend_options('front'))
    jobs, samples, clipped = [], 0, 0
    pending = bytearray(); cache = Cache(); due = 16000
    try:
        reset(front)
        with (recording/'packets.bin').open('rb') as f:
            for index in range(size//PACKET_BYTES):
                packet = f.read(PACKET_BYTES)
                # Validate saved data again before deriving a persistent template.
                from pcm_capture import decode_packet
                decode_packet(packet, report['epoch'], index)
                raw = packet[32:]
                # Voice model uses CH0, matching the live path; other channels
                # remain in the saved recording for array/debug use.
                for offset in range(0, len(raw), 16):
                    value = struct.unpack_from('<i', raw, offset)[0]
                    clipped += int(abs(value) >= 8388607)
                    samples += 1
                pending.extend(raw)
                if len(pending) >= 1536*16:
                    cache.push(front.run_pcm32(bytes(pending[:1536*16])))
                    del pending[:1536*16]
                    if cache.samples >= due:
                        job = cache.snapshot(1.)
                        due = cache.samples + 16000
                        if job is not None and job['active'] and job['coverage'] >= .8:
                            jobs.append(job)
    finally:
        front.close(force=True)
    if clipped > samples*.01:
        raise ValueError('CLIPPED_AUDIO: move farther away or reduce input level')
    if not jobs:
        raise ValueError('NOT_ENOUGH_SPEECH: speak continuously; need one voiced one-second window')
    indices = sorted(set((0, (len(jobs)-1)//2, len(jobs)-1)))
    return [jobs[i] for i in indices], dict(eligible_windows=len(jobs),
        selected_windows=[jobs[i]['start_sample16'] for i in indices],
        coverage=[jobs[i]['coverage'] for i in indices], clipped_samples=clipped,
        channel=0, sample_count=samples)


def extract_clip(root, recording, backend_factory=None):
    from speaker_models import verify_candidates, backend_options
    core = Path(root)/'software/ps/speaker_core'
    verify_candidates(core)
    jobs, quality = eligible_jobs(core, Path(recording), backend_factory)
    from pipeline_bench import Backend
    embed = (backend_factory or Backend)(core, role='embed', **backend_options('embed'))
    try:
        vectors = [normalize(embed.run('J', job['features'])) for job in jobs]
    finally:
        embed.close(force=True)
    vector = normalize([sum(v[j] for v in vectors)/len(vectors) for j in range(192)])
    quality['within_clip_cosines'] = [cosine(v, vector) for v in vectors]
    return dict(vector=vector, quality=quality)


def extract_bounded(root, recording):
    """Kill the entire CPU-only worker group on timeout/cancel, including native children."""
    if os.name != 'posix':
        raise RuntimeError('Board enrollment extraction requires Linux')
    output = Path(recording)/'enrollment-vector.json'
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--extract',
               str(root), str(recording), str(output)]
    process = subprocess.Popen(command, start_new_session=True)
    try:
        if process.wait(timeout=180) != 0:
            raise RuntimeError('ENROLL_EXTRACTION_FAILED: see recording directory; no target changed')
        return json.loads(output.read_text())
    finally:
        # Workers may fail after spawning the backend. Reap the complete group
        # even if the direct worker has exited already. No hardware is in it.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def enroll_locked(root, target, seconds=3., record=record_clip, extract=extract_bounded,
                  emit=print, sleep=time.sleep):
    """Caller owns PS lock. Failures preserve recordings and previous profiles/selector."""
    from speaker_settings import verify_assets
    from speaker_models import verify_candidates, MODELS
    root = Path(root)
    validate_request(root, target, seconds)
    core = root/'software/ps/speaker_core'
    verify_assets(core, use_selected=False)
    verify_candidates(core)
    if os.name == 'posix':
        os.chmod(core/'pipeline_backend', 0o755)
    assets = json.loads((core/'live-assets.json').read_text())['sha256']
    emit('ENROLL_CLIP=1/1 SECONDS=%s SERVO=OFF SPEAK_AFTER_RECORD_NOW' % seconds, flush=True)
    for n in (3, 2, 1):
        emit('READY_IN=%d' % n, flush=True); sleep(1)
    emit('RECORD_NOW: speak naturally and continuously; only the target person speaks', flush=True)
    path = record(root, seconds)
    emit('RECORDING_DONE PROCESSING=1 SERVO=OFF', flush=True)
    result = extract(root, path)
    template = normalize(result['vector'])
    clips = [dict(recording=str(Path(path).relative_to(root)), quality=result['quality'])]
    profile = dict(schema=2, target_id=target, template=template, low=None, high=None,
        score_only=True, recognition_qualified=False, assets=assets, candidate_models=dict(MODELS),
        enrollment_method='board_single_clip_cp1_vf1_1s',
        aggregation='up_to_three_uniform_voiced_windows_equal_weight_L2', clips=clips)
    destination = profile_path(root, target).parent
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.enroll-', dir=str(destination.parent)))
    # A single atomic directory rename publishes only a complete profile. The
    # selector and gate remain untouched; recording alone never grants motion.
    try:
        atomic_json(pending/'profile.json', profile)
        if destination.exists():
            raise ValueError('TARGET_EXISTS_PRESERVED')
        pending.rename(destination)
    finally:
        if pending.exists():
            # Only the known temporary profile file made by this invocation.
            (pending/'profile.json').unlink(missing_ok=True)
            pending.rmdir()
    load_profile(root, target, assets)
    emit('ENROLLED='+target+' ACTIVE_TARGET_UNCHANGED=1 THRESHOLD_NOT_CALIBRATED=1 SERVO=OFF', flush=True)
    return dict(target_id=target, profile=str(destination/'profile.json'), clips=clips,
                selected=False, motion_commands=0, recognition_qualified=False)


def run(root, target, seconds=3.):
    from run_capture import single_owner
    from board_3d import LOCK, check_hwh
    validate_request(root, target, seconds)
    check_hwh(Path(root)/'soundsight.hwh')
    with single_owner(LOCK):
        return enroll_locked(root, target, seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Internal CPU-only enrollment extractor')
    parser.add_argument('--extract', nargs=3, required=True, metavar=('ROOT', 'RECORDING', 'OUTPUT'))
    a = parser.parse_args()
    root, recording, output = map(Path, a.extract)
    atomic_json(output, extract_clip(root, recording))
