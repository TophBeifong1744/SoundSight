"""Build the private complete S2/S3/CF1A application, explicitly without DAS.

Only fixed voice-model/native assets come from the old private ZIP. Every
program source and the S2 hardware pair comes from this checkout, never from
the user's old external Vivado project. Paths in metadata are package-relative.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from install_current_runtime import PREFIX, REVISION, load_package

ROOT = Path(__file__).resolve().parents[1]
CORE = 'software/ps/speaker_core/'
ASSETS = ('pipeline_backend', 'lib/libonnxruntime.so.1.17.3', 'frontend.f32',
          'models/int8-head.onnx', 'models/silero_vad.onnx', 'models/cp1/fixed98.onnx',
          'models/vf1/vad16_fixed.onnx', 'speaker-template.json', 'live-assets.json')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def collect(private_zip):
    data = {}
    with ZipFile(private_zip) as z:
        for name in ASSETS:
            data[CORE+name] = z.read(PREFIX+CORE+name)
        for name in z.namelist():
            if name.startswith(PREFIX+CORE+'licenses/') and not name.endswith('/'):
                data[name[len(PREFIX):]] = z.read(name)
    # Model binding is unchanged; a private original template is required by
    # the existing enrollment frontend. No selected user is shipped/enabled.
    assets = json.loads(data[CORE+'live-assets.json'])['sha256']
    for name, expected in assets.items():
        if digest(data[CORE+name]) != expected:
            raise ValueError('Private model binding differs: '+name)
    sys.path.insert(0, str(ROOT/'software/ps'))
    from speaker_models import MODELS
    for name, expected in MODELS.items():
        if digest(data[CORE+'models/'+name]) != expected:
            raise ValueError('CP1/VF1 mismatch: '+name)
    native = data[CORE+'pipeline_backend']
    if native[:5] != b'\x7fELF\x01' or int.from_bytes(native[18:20], 'little') != 40:
        raise ValueError('Expected original 32-bit ARM native backend')
    # Use tracked files only: no local profiles, compiled PC libraries or caches.
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    folders = ('software/ps/', 'software/common/', 'software/tetra3d/core/',
               'software/tetra3d/linux/', 'software/tetra3d/tests/',
               'software/screen/')
    suffixes = ('.py', '.c', '.h', '.sh', '.mem', '.dtbo', '.dts')
    for name in tracked:
        if name.startswith(folders) and (name.endswith(suffixes) or name == 'software/tetra3d/core/tetra40-nominal.json'):
            data[name] = (ROOT/name).read_bytes()
    tests = ('test_normal test_volume_gate test_serial_english test_board_tools '
             'test_filter_controls test_manual_servo test_pcm_capture test_online_angle_filter '
             'test_speaker_follow test_speaker_display test_speaker_enrollment '
             'test_speaker_statistics test_latest_result test_screen_product').split()
    for test in tests:
        name = 'software/tests/'+test+'.py'
        data[name] = (ROOT/name).read_bytes()
    for name in ('soundsight.sh', 'soundsight-3d.sh', 'soundsight-panel.sh',
                 'soundsight-screen.sh', 'soundsight-screen-i2c.sh', 'LICENSE', 'THIRD_PARTY.md',
                 'document/pynq-final-runtime.md', 'document/screen-control.md',
                 'document/pynq-speaker-statistics.md', 'document/pynq-speaker-enrollment.md',
                 'tools/check_current_software.py', 'tools/install_current_runtime.py',
                 'tools/install_normal_update.py', 'tools/install_product.py',
                 'software/ps/speaker_core/armv7.cmake',
                 'software/ps/speaker_core/build-lock.json',
                 'software/tests/test_current_runtime.py'):
        data[name] = (ROOT/name).read_bytes()
    for kind in ('bit', 'hwh'):
        data['soundsight.'+kind] = (ROOT/'release/output/screen_s2'/('soundsight.'+kind)).read_bytes()
    with ZipFile(ROOT/'release/output/soundsight_screen_ps_i2c_s2.zip') as z:
        for kind in ('bit', 'hwh'):
            assert data['soundsight.'+kind] == z.read('soundsight.'+kind)
    with ZipFile(ROOT/'release/output/soundsight_three_d_coherent_cf1a.zip') as z:
        for name in z.namelist():
            if name.startswith('software/'):
                assert data[name].replace(b'\r\n', b'\n') == z.read(name).replace(b'\r\n', b'\n'), name
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    data['SOURCE.json'] = (json.dumps(dict(revision=REVISION, source_commit=commit,
        hardware={k: dict(path='soundsight.'+k, sha256=digest(data['soundsight.'+k])) for k in ('bit','hwh')},
        servo_pins=dict(horizontal='M15', vertical='J14'), servo_connector=dict(horizontal='J3 pin 2', vertical='J3 pin 3'),
        screen='S2_PS_I2C0_EMIO+S3', frontend='CF1A', speaker='CP1_VF1',
        permission='score_ttl_v2', das=False, default_axes='off', private=True,
        package_joint_board_test='NOT_RUN', application_parameters='Preserved on upgrade; no invented calibration'), indent=2)+'\n').encode()
    data['README.md'] = data['document/pynq-final-runtime.md']
    for name, raw in list(data.items()):
        if name.endswith(('.py','.sh','.c','.h','.md','.dts','.mem')):
            data[name] = raw.replace(b'\r\n', b'\n')
        if name.endswith('.py'):
            ast.parse(data[name].decode('utf-8-sig'), feature_version=(3,8))
    return data, commit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-assets-from', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    data, commit = collect(a.private_assets_from)
    manifest = dict(revision=REVISION, source_commit=commit, private=True,
        files={n:digest(b) for n,b in sorted(data.items())}, private_assets=[CORE+n for n in ASSETS])
    contents = {PREFIX+n:b for n,b in data.items()}
    contents['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    contents['__main__.py'] = (ROOT/'tools/install_current_runtime.py').read_bytes().replace(b'\r\n',b'\n')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    temp = a.output.with_suffix('.building.zip')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name, raw in sorted(contents.items()):
            info=ZipInfo(name,(2026,11,2,0,0,0)); info.compress_type=ZIP_DEFLATED
            info.create_system=3
            info.external_attr=(0o100755 if name.endswith('.sh') or name.endswith('/pipeline_backend') else 0o100644)<<16
            z.writestr(info,raw)
    load_package(temp)
    with ZipFile(temp) as z:
        assert z.testzip() is None
    temp.replace(a.output)
    print(json.dumps(dict(package=str(a.output),bytes=a.output.stat().st_size,files=len(data),
        revision=REVISION,private=True,das=False,hardware_actions=0)))


if __name__=='__main__':
    main()
