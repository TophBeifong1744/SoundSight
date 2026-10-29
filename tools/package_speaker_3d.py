"""Package current 3-D hardware/software and explicit B CP1/VF1 models.

The archive is private (contains the original enrollment template). No target
selector, P02 template, recording or local servo/threshold settings are shipped.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from package_three_d_board import payload, EVIDENCE

ROOT = Path(__file__).resolve().parents[1]
NAME = 'SoundSight_PYNQ_3D_Speaker'
CORE = 'software/ps/speaker_core/'


def contents(b_package):
    files = {n: p.read_bytes() for n, p in payload().items()}
    source = json.loads((EVIDENCE/'user-build-receipt.json').read_text('utf-8'))
    review = json.loads((EVIDENCE/'hardware-review.json').read_text('utf-8'))
    if review['result'] != 'SCOPED_PASS':
        raise ValueError('Hardware report checks did not pass')
    for kind in ('bit', 'hwh'):
        record = source['artifacts'][kind]
        raw = Path(record['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Hardware changed: '+kind)
        files['soundsight.'+kind] = raw
    for name in ('hardware-review.json', 'user-build-receipt.json'):
        files['reports/'+name] = (EVIDENCE/name).read_bytes()
    files['reports/audit_status.txt'] = (EVIDENCE/'supplemental/audit_status.txt').read_bytes()
    # Existing original ARM backend/models/frontend retain their manifests and
    # template binding. Do not take stale Python sources from the old ZIP.
    base = ROOT/'release/output/soundsight_pynq_speaker_full_profile.zip'
    fixed = ('pipeline_backend', 'lib/libonnxruntime.so.1.17.3', 'frontend.f32',
             'models/int8-head.onnx', 'models/silero_vad.onnx', 'live-assets.json',
             'speaker-template.json', 'model-lock.json', 'build-lock.json')
    with ZipFile(base) as archive:
        prefix = 'SoundSight_PYNQ_Speaker_Live/'+CORE
        for n in archive.namelist():
            if n.startswith(prefix) and (n[len(prefix):] in fixed or n[len(prefix):].startswith('licenses/')):
                files[CORE+n[len(prefix):]] = archive.read(n)
    with ZipFile(b_package) as archive:
        for model in ('cp1/fixed98.onnx', 'vf1/vad16_fixed.onnx'):
            files[CORE+'models/'+model] = archive.read('SoundSight_A_Speaker_CP1_VF1/models/'+model)
    modules = ('live_speaker live_speaker_follow speaker_models speaker_permission speaker_follow_setup '
               'speaker_process speaker_scheduling speaker_settings speaker_targets speaker_enrollment live_cpu_profile').split()
    for name in modules:
        files['software/ps/'+name+'.py'] = (ROOT/'software/ps'/(name+'.py')).read_bytes()
    for name in ('pipeline_bench', 'stream_bench', 'short_bench', 'cpu_profile_bench'):
        files[CORE+name+'.py'] = (ROOT/CORE/(name+'.py')).read_bytes()
    for name in ('pipeline_backend.c', 'stream_frontend.h', 'detail_profile.h', 'core_bench.c'):
        files[CORE+'source/'+name] = (ROOT/CORE/name).read_bytes()
    for n in ('software/tests/test_speaker_follow.py', 'software/tests/test_speaker_enrollment.py',
              'document/pynq-speaker-enrollment.md', 'document/pynq-speaker-3d.md',
              'document/evidence/speaker-enrollment-20261029/board-result.md',
              'document/pynq-w16-update.md',
              'document/b-speaker-3d-interface.md'):
        files[n] = (ROOT/n).read_bytes()
    files['README.md'] = files['document/pynq-speaker-3d.md']
    files['speaker-follow.example.json'] = (json.dumps(dict(schema=1, threshold=.65, permit_seconds=3.,
        policy='delayed_permission_v1', recognition_qualified=False), indent=2)+'\n').encode()
    files['SOURCE.json'] = (json.dumps(dict(hardware=source['artifacts'], model_selection='cp1_vf1',
        policy='delayed_permission_v1', default_motion=False, threshold_configured=False,
        private=True, board_joint_test='SPEAKER_GATED_DUAL_AXIS_NOT_VERIFIED', recognition_qualified=False,
        servo_pins={'horizontal': 'T15', 'vertical': 'W16'},
        enrollment='speaker-enroll ID: one short private CP1/VF1 clip; preserve existing P01/P02 and user settings',
        board_enrollment_test='USER_REPORTED_SINGLE_5S_AND_SELF_SCORE_ONLY'), indent=2)+'\n').encode()
    for n, raw in files.items():
        if n.endswith('.py'):
            ast.parse(raw.decode('utf-8-sig'), feature_version=(3, 8))
        if n.endswith('.sh') and b'\r' in raw:
            raise ValueError('Shell script needs LF: '+n)
    return files


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--b-package', type=Path, required=True)
    p.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_pynq_3d_speaker.zip')
    a = p.parse_args()
    files = contents(a.b_package)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(a.output, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(NAME+'/'+name, (2026, 10, 29, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') or name.endswith('/pipeline_backend') else 0o100644) << 16
            archive.writestr(info, data)
    with ZipFile(a.output) as archive:
        assert archive.testzip() is None
        for name, data in files.items():
            assert archive.read(NAME+'/'+name) == data, name
    print(json.dumps(dict(package=str(a.output), bytes=a.output.stat().st_size,
                         files=len(files), hardware_actions=0, private=True)))


if __name__ == '__main__':
    main()
