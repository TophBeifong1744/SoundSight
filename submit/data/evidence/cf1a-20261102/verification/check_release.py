"""Bind the ZIP to final sources, tested product candidate and exact CF1 base."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()
package = ROOT/'delivery/soundsight_three_d_coherent_cf1a.zip'
prior = ROOT.parent/'ss-three-d-coherent-cf1/delivery/soundsight_three_d_coherent_cf1.zip'
with zipfile.ZipFile(package) as z, zipfile.ZipFile(prior) as old:
    assert z.testzip() is None
    manifest = json.loads(z.read('manifest.json'))
    assert set(z.namelist()) == set(manifest['files']) | {'__main__.py','manifest.json'}
    assert z.read('__main__.py') == (ROOT/'install_update.py').read_bytes()
    for name, checksum in manifest['files'].items():
        data = z.read(name)
        assert sha(data) == checksum
        assert data == (ROOT/'runtime'/name).read_bytes()
        assert sha(old.read(name)) == manifest['before'][name]
        if name.endswith('.py'):
            ast.parse(data.decode(), filename=name, feature_version=(3,8))
            assert data == (ROOT/'verification/runtime'/name).read_bytes()
    ast.parse(z.read('__main__.py').decode(), feature_version=(3,8))
    receipt = (json.dumps(dict(revision='THREE_D_COHERENT_CF1', files=json.loads(old.read('manifest.json'))['files'],
                              hardware_unchanged=True, board_joint_test='NOT_RUN'), indent=2)+'\n').encode()
    assert sha(receipt) == manifest['dependencies']['THREE-D-CF1-INSTALL.json']
    with zipfile.ZipFile(ROOT.parent/'ss-c-board-test-20261031/delivery/soundsight_c_three_tests_20261031_v2_private.zip') as base:
        for name, checksum in manifest['dependencies'].items():
            if name != 'THREE-D-CF1-INSTALL.json':
                assert sha(base.read('code/SoundSight_PYNQ_3D_Speaker/'+name)) == checksum
report = dict(status='PASS', package=package.name, bytes=package.stat().st_size, sha256=sha(package.read_bytes()),
              payload_files=len(manifest['files']), dependencies=len(manifest['dependencies']),
              python38_syntax=True, tested_python_sources_equal=True, crc=True,
              board_test='NOT_RUN', hardware_actions=0)
(ROOT/'verification/release-integrity.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
