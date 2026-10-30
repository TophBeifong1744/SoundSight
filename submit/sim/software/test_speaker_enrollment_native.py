"""Actual CP1/VF1 native replay; historical private PCM, no board or motion.

Run on Linux using the existing host backend. Inputs stay in ignored build/;
only aggregate numeric checks go to the evidence directory, never templates.
"""
import contextlib
import functools
import io
import json
from pathlib import Path
import struct
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'software/build/enrollment-validation'
APP = WORK/'application'
CORE = APP/'software/ps/speaker_core'
for p in (ROOT/'software/ps', ROOT/'software/ps/speaker_core'):
    sys.path.insert(0, str(p))
import speaker_enrollment as enrollment
from speaker_targets import normalize, cosine, select
from speaker_settings import verify_assets
from speaker_follow_setup import configure
from speaker_permission import load_settings
from pipeline_bench import Backend
from speaker_models import backend_options


def recording(name, raw):
    path = APP/'logs'/name
    path.mkdir(parents=True, exist_ok=False)
    count = len(raw)//8192
    (path/'result.json').write_text(json.dumps(dict(result='PASS', dma_halted=True, epoch=7)))
    with (path/'packets.bin').open('wb') as out:
        for i in range(count):
            out.write(struct.pack('<8I', 0x43505353, 0x00200001, 7, i, i*512, 0, 512, 8192))
            out.write(raw[i*8192:(i+1)*8192])
    return path


def main():
    if WORK.exists():
        raise RuntimeError('Existing native test artifacts preserved; use a fresh test workspace')
    CORE.mkdir(parents=True)
    with ZipFile(ROOT/'release/output/soundsight_pynq_3d_speaker.zip') as archive:
        prefix = 'SoundSight_PYNQ_3D_Speaker/software/ps/speaker_core/'
        for name in archive.namelist():
            if name.startswith(prefix) and not name.endswith('/'):
                dest = CORE/name[len(prefix):]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(name))
    with ZipFile(ROOT/'release/output/soundsight_pynq_speaker_full_profile.zip') as archive:
        raw = archive.read('SoundSight_PYNQ_Speaker_Live/software/ps/speaker_core/profile/epoch26.pcm32')
    factory = functools.partial(Backend, executable=ROOT/'software/build/speaker-live-validation/native/pipeline_backend')
    first = recording('historic-first3s', raw[:282*8192])
    second = recording('historic-next3s', raw[282*8192:564*8192])
    quiet = recording('zero-3s', bytes(282*8192))
    value = enrollment.extract_clip(APP, first, factory)
    # Independent construction of the normalized centroid from the selected
    # production frontend feature windows and actual CP1 network output.
    jobs, _ = enrollment.eligible_jobs(CORE, first, factory)
    native = factory(CORE, role='embed', **backend_options('embed'))
    try:
        vectors = [normalize(native.run('J', j['features'])) for j in jobs]
    finally:
        native.close(force=True)
    expected = normalize([sum(v[i] for v in vectors) for i in range(192)])
    error = max(abs(a-b) for a,b in zip(value['vector'], expected))
    assert error < 1e-6, error
    other = enrollment.extract_clip(APP, second, factory)
    try:
        enrollment.extract_clip(APP, quiet, factory)
    except ValueError as exc:
        assert 'NOT_ENOUGH_SPEECH' in str(exc), str(exc)
    else:
        raise AssertionError('Silence accepted as an enrollment template')
    with contextlib.redirect_stdout(io.StringIO()):
        enrollment.enroll_locked(APP, 'offline_fixture', record=lambda *a: first,
            extract=lambda *a: value, sleep=lambda *a: None)
    configure(APP, .65)
    select(APP, 'offline_fixture')
    loaded = verify_assets(CORE)
    assert max(abs(a-b) for a,b in zip(loaded['template'], value['vector'])) < 1e-12
    assert load_settings(APP)['threshold'] is None
    result = dict(result='PASS', scope='HOST_ACTUAL_MODELS_HISTORICAL_PCM_NOT_ARM_OR_REAL_ENROLLMENT',
        first_quality=value['quality'], second_quality=other['quality'],
        centroid_max_abs_error=error, next_clip_cosine=cosine(value['vector'], other['vector']),
        zero_audio_rejected=True, persisted_template_reloaded=True,
        old_threshold_cleared=True, hardware_actions=0, recognition_accuracy='NOT_MEASURED')
    evidence = ROOT/'document/evidence/speaker-enrollment-20261029'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence/'native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
