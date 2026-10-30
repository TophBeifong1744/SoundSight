"""Private P02 enrollment and score-only target selection. Python 3.8 stdlib.

No PYNQ or hardware access. Original P01 assets are never replaced.
"""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import wave

PROFILE = 'speaker-profiles/P02-v1/profile.json'
SELECTOR = 'speaker-target.local.json'
ENROLL = ['P02_C%02d' % n for n in (1, 2, 3)]
POSITIVE = ['P02_T%02d' % n for n in (1, 2, 3)]
NEGATIVE = ['P01_C%02d' % n for n in (1, 2, 3)]


def target_name(value):
    """Simple portable IDs; never interpret a target name as a user-supplied path."""
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', value):
        raise ValueError('TARGET_ID: use 1..32 ASCII letters/digits/_/-; start with a letter')
    if value.upper() in ('CON', 'PRN', 'AUX', 'NUL') or re.fullmatch(r'(COM|LPT)[0-9]', value.upper()):
        raise ValueError('RESERVED_TARGET_ID')
    return value


def profile_path(root, target):
    target_name(target)
    return Path(root)/(PROFILE if target == 'P02' else 'speaker-profiles/'+target+'/profile.json')


def load_profile(root, target, assets):
    path = profile_path(root, target)
    if path.stat().st_size > 65536:
        raise ValueError('PROFILE_TOO_LARGE')
    profile = json.loads(path.read_text(encoding='utf-8'))
    if target == 'P02':
        return validate_profile(profile, assets)
    from speaker_models import MODELS
    if (profile.get('schema') != 2 or profile.get('target_id') != target or
            profile.get('assets') != assets or profile.get('candidate_models') != MODELS or
            profile.get('score_only') is not True or profile.get('recognition_qualified') is not False or
            profile.get('low') is not None or profile.get('high') is not None):
        raise ValueError('PROFILE_SCHEMA_OR_MODEL_MISMATCH')
    normalize(profile['template'])
    if abs(sum(v*v for v in profile['template'])-1) > 1e-4:
        raise ValueError('PROFILE_NORM')
    return profile


def list_targets(root):
    """List valid profiles and explicitly report broken ones, without changing selection."""
    from speaker_settings import verify_assets
    root = Path(root); core = root/'software/ps/speaker_core'
    verify_assets(core, use_selected=False)
    assets = json.loads((core/'live-assets.json').read_text())['sha256']
    active = json.loads((root/SELECTOR).read_text()).get('target_id') if (root/SELECTOR).exists() else None
    rows = [dict(target_id='P01', selected=active == 'P01', source='original', valid=True)]
    for path in sorted((root/'speaker-profiles').glob('*/profile.json')):
        target = 'P02' if path.parent.name == 'P02-v1' else path.parent.name
        try:
            cfg = load_profile(root, target, assets)
            rows.append(dict(target_id=target, selected=target == active, valid=True,
                             source=cfg.get('enrollment_method', 'legacy_P02')))
        except (ValueError, KeyError, OSError) as exc:
            rows.append(dict(target_id=target, selected=target == active, valid=False, error=str(exc)))
    return dict(active_target=active, targets=rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.target-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def normalize(vector):
    if len(vector) != 192 or not all(type(v) in (int, float) and math.isfinite(v) for v in vector):
        raise ValueError('INVALID_EMBEDDING')
    norm = math.sqrt(sum(v*v for v in vector))
    if norm < 1e-8:
        raise ValueError('ZERO_EMBEDDING')
    return [v/norm for v in vector]


def centroid(vectors):
    if len(vectors) != 3:
        raise ValueError('THREE_ENROLLMENT_RECORDINGS_REQUIRED')
    vectors = [normalize(v) for v in vectors]
    return normalize([sum(v[j] for v in vectors)/3 for j in range(192)])


def cosine(a, b):
    return max(-1., min(1., sum(x*y for x, y in zip(a, b))))


def validate_profile(profile, assets):
    if profile.get('schema') != 1 or profile.get('target_id') != 'P02':
        raise ValueError('PROFILE_ID_OR_SCHEMA')
    if profile.get('assets') != assets:
        raise ValueError('PROFILE_MODEL_OR_FRONTEND_MISMATCH')
    # V1 intentionally has no threshold enabling identity decisions.
    if profile.get('score_only') is not True or profile.get('recognition_qualified') is not False:
        raise ValueError('P02_REQUIRES_SCORE_ONLY')
    if profile.get('low') is not None or profile.get('high') is not None:
        raise ValueError('P02_THRESHOLDS_NOT_CALIBRATED')
    vector = profile['template']
    normalize(vector)
    if abs(sum(v*v for v in vector)-1) > 1e-4:
        raise ValueError('PROFILE_NORM')
    if profile.get('enrollment_ids') != ENROLL:
        raise ValueError('PROFILE_ENROLLMENT_SPLIT')
    return profile


def load_p02(core, assets):
    path = Path(core).resolve().parents[2]/PROFILE
    if path.stat().st_size > 65536:
        raise ValueError('PROFILE_TOO_LARGE')
    return validate_profile(json.loads(path.read_text(encoding='utf-8')), assets)


def selected_config(core, original, assets):
    root = Path(core).resolve().parents[2]
    selector = root/SELECTOR
    if not selector.exists():
        return dict(original, target_id='P01', score_only=False)
    if selector.stat().st_size > 4096:
        raise ValueError('SELECTOR_TOO_LARGE')
    cfg = json.loads(selector.read_text(encoding='utf-8'))
    if cfg == {'schema': 1, 'target_id': 'P01'}:
        return dict(original, target_id='P01', score_only=False)
    if set(cfg) != {'schema', 'target_id', 'profile_sha256'} or cfg['schema'] != 1:
        raise ValueError('INVALID_TARGET_SELECTOR')
    if digest(profile_path(root, cfg['target_id'])) != cfg['profile_sha256']:
        raise ValueError('PROFILE_HASH_MISMATCH')
    return load_profile(root, cfg['target_id'], assets)


def select(root, target):
    from speaker_settings import verify_assets
    root = Path(root)
    target_name(target)
    core = root/'software/ps/speaker_core'
    verify_assets(core, use_selected=False)
    cfg = {'schema': 1, 'target_id': target}
    if target != 'P01':
        assets = json.loads((core/'live-assets.json').read_text())['sha256']
        load_profile(root, target, assets)
        cfg['profile_sha256'] = digest(profile_path(root, target))
    # Caller holds the owner lock. Clear permission BEFORE changing the target;
    # a storage failure can disable the old target, never enable a new one with
    # somebody else's threshold. No in-flight session may survive this change.
    from speaker_follow_setup import configure
    configure(root, disable=True)
    atomic_json(root/SELECTOR, cfg)
    return cfg


def decision(score, config):
    if config.get('score_only', False):
        return 'insufficient'
    return 'target' if score >= config['high'] else 'non_target' if score <= config['low'] else 'insufficient'


def checked_wav(path):
    with wave.open(str(path), 'rb') as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getcomptype()) != (48000, 4, 3, 'NONE'):
            raise ValueError('REQUIRED_WAV_PCM24_48K_4CH')
        if not 96000 <= f.getnframes() <= 2880000:
            raise ValueError('WAV_DURATION_REQUIRES_2_TO_60_SECONDS')


class NativeExtractor:
    """Use the shipped ARM executable; never approximate its frontend in Python."""
    def __init__(self, core, original):
        sys.path.insert(0, str(core))
        from pipeline_bench import Backend
        self.backend = Backend(core)
        self.original = original

    def full(self, path):
        from pipeline_bench import extract
        from short_bench import fast_decoder
        trace = {}
        b = self.backend
        row = extract(b, path, self.original['template'], self.original['low'], self.original['high'],
                      trace=trace, decoder=lambda p: fast_decoder(b, p))
        if 'vector' not in trace:
            raise ValueError('INSUFFICIENT_USABLE_SPEECH: '+str(path))
        return trace['vector'], dict(speech_seconds=row['speech_seconds'], chunks=row['chunks'])

    def short(self, path, template):
        from stream_bench import Cache, reset, HOP
        from live_opt_bench import raw_packets
        b = self.backend
        raw = raw_packets(path)
        reset(b); cache = Cache()
        candidates = {w: [] for w in (1., 1.5, 2.)}
        due = {w: int(w*16000) for w in candidates}
        for pos in range(0, len(raw)-1536*16+1, 1536*16):
            cache.push(b.run_pcm32(raw[pos:pos+1536*16]))
            for w in candidates:
                if cache.samples >= due[w]:
                    job = cache.snapshot(w); due[w] += HOP
                    if job['active'] and job['coverage'] >= .5:
                        candidates[w].append(job)
        result = []
        for w, jobs in candidates.items():
            # Deterministic spread across eligible windows; not score-based selection.
            indices = sorted(set((0, (len(jobs)-1)//2, len(jobs)-1))) if jobs else []
            rows = []
            for i in indices:
                job = jobs[i]
                vector = normalize(b.run('J', job['features']))
                rows.append(dict(start_sample16=job['start_sample16'], end_sample16=job['end_sample16'],
                                 coverage=job['coverage'], score=cosine(vector, template)))
            result.append(dict(window_seconds=w, eligible_windows=len(jobs), sampled=rows))
        return result

    def close(self, failed=False):
        self.backend.close(force=failed)


def enroll(root, factory=NativeExtractor, emit=print):
    from speaker_settings import verify_assets
    root = Path(root); core = root/'software/ps/speaker_core'
    original = verify_assets(core, use_selected=False)
    assets = json.loads((core/'live-assets.json').read_text())['sha256']
    destination = (root/PROFILE).parent
    if destination.exists():
        raise ValueError('P02_PROFILE_EXISTS_PRESERVED')
    data = root/'speaker-target-data'
    manifest = json.loads((data/'sources.json').read_text())
    ids = ENROLL+POSITIVE+NEGATIVE
    if set(manifest) != set(ids):
        raise ValueError('SOURCE_SPLIT_MISMATCH')
    for name in ids:
        path = data/(name+'.wav'); checked_wav(path)
        if digest(path) != manifest[name]:
            raise ValueError('SOURCE_HASH: '+name)
    extractor = factory(core, original)
    failed = True
    try:
        vectors, training = [], []
        for name in ENROLL:
            emit('ENROLL_RECORDING='+name, flush=True)
            vec, info = extractor.full(data/(name+'.wav'))
            vectors.append(vec); training.append(dict(recording=name, **info))
        template = centroid(vectors)
        profile = dict(schema=1, target_id='P02', template=template, low=None, high=None,
                       score_only=True, recognition_qualified=False, assets=assets,
                       enrollment_ids=ENROLL, enrollment_sha256={n: manifest[n] for n in ENROLL},
                       aggregation='equal_weight_per_recording_then_L2', threshold_status='NOT_CALIBRATED')
        checks = []
        for name in POSITIVE+NEGATIVE:
            emit('DEVELOPMENT_CHECK='+name, flush=True)
            path = data/(name+'.wav')
            vec, info = extractor.full(path)
            checks.append(dict(recording=name, role='same_speaker' if name in POSITIVE else 'other_speaker',
                               sha256=manifest[name], full_speech_score=cosine(normalize(vec), template),
                               short_windows=extractor.short(path, template), **info))
        report = dict(scope='REUSED_HISTORICAL_RECORDINGS_DEVELOPMENT_ONLY', enrollment=training,
                      evaluation=checks, independent_accuracy_measured=False,
                      latency_or_expiry_fixed=False, recognition_qualified=False, motion_commands=0,
                      target_activated=False, short_mode='UNPACED_OFFLINE_J_NOT_LIVE_TIMING')
        failed = False
    finally:
        extractor.close(failed)
    # No files or selector are changed until every extraction succeeds.
    destination.parent.mkdir(exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.p02-', dir=str(destination.parent)))
    try:
        validate_profile(profile, assets)
        atomic_json(pending/'profile.json', profile)
        atomic_json(pending/'evaluation.json', report)
        pending.rename(destination)
    finally:
        if pending.exists():
            shutil.rmtree(pending)
    emit('P02_ENROLLED=1 ACTIVE_TARGET_UNCHANGED=1 SCORE_ONLY=1', flush=True)
    emit('REPORT='+str(destination/'evaluation.json'), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'enroll', 'select'))
    parser.add_argument('target', nargs='?')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    if (args.command == 'select') != (args.target is not None):
        parser.error('Only select requires a target')
    # Diagnostic tracing would distort offline timing and can exhaust trace buffers.
    for key in ('SS_ORT_PROFILE_DIR', 'SS_SPEAKER_DETAIL_PROFILE'):
        os.environ.pop(key, None)
    if args.command == 'enroll':
        enroll(root)
    elif args.command == 'select':
        from run_capture import single_owner
        with single_owner('/tmp/soundsight-ps-owner.lock'):
            print(json.dumps(select(root, args.target)), flush=True)
        print('APPLIES_TO_NEXT_SESSION=1 MOTION_COMMANDS=0', flush=True)
    else:
        from speaker_settings import verify_assets
        cfg = verify_assets(root/'software/ps/speaker_core')
        print(json.dumps({k: cfg.get(k) for k in ('target_id', 'score_only', 'low', 'high', 'recognition_qualified')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
