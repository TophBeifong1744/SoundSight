"""Build the P1 capture update from explicit original archives; no hardware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--p1', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--previous-update', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('installer', root/'tools/install_product.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    def hashes(raw):
        # Existing packages may preserve Windows checkout line endings.
        variants = [raw]
        if b'\0' not in raw:
            lf = raw.replace(b'\r\n', b'\n')
            variants += [lf, lf.replace(b'\n', b'\r\n')]
        return sorted({hashlib.sha256(v).hexdigest() for v in variants})
    with ZipFile(a.previous_update) as old:
        if old.testzip():
            raise ValueError('Previous update CRC failure')
        old_manifest = json.loads(old.read('manifest.json'))
        if (old_manifest.get('revision') != 'SCREEN_PRODUCT_P1' or
                old_manifest.get('capture_revision') != 'CAPTURE_COOPERATIVE_V1'):
            raise ValueError('Expected cooperative capture update baseline')
        old_data = {n:old.read('payload/'+n) for n in old_manifest['files']}
        if any(hashlib.sha256(raw).hexdigest() != old_manifest['files'][n] for n,raw in old_data.items()):
            raise ValueError('Previous update manifest mismatch')
    with ZipFile(a.p1) as p1, ZipFile(a.runtime) as runtime:
        if p1.testzip() or runtime.testzip():
            raise ValueError('Original archive CRC failure')
        original = json.loads(p1.read('manifest.json'))
        if original['revision'] != 'SCREEN_PRODUCT_P1':
            raise ValueError('Expected original P1 baseline')
        data = {name:(root/name).read_bytes() for name in installer.PAYLOAD}
        files = {n:hashlib.sha256(raw).hexdigest() for n,raw in data.items()}
        previous = {}
        requires = dict(original['requires'])
        for n in data:
            accepted = list(original['previous'].get(n, []))
            accepted += old_manifest['previous'].get(n, [])
            if n in old_data:
                accepted += hashes(old_data[n])
            if 'payload/'+n in p1.namelist():
                raw = p1.read('payload/'+n)
                if hashlib.sha256(raw).hexdigest() != original['files'][n]:
                    raise ValueError('Original P1 manifest mismatch: '+n)
                accepted += hashes(raw)
            full = 'SoundSight_PYNQ_3D_Speaker/'+n
            if full in runtime.namelist():
                accepted += hashes(runtime.read(full))
            previous[n] = sorted(set(accepted))
            if accepted:
                requires[n] = sorted(set(requires.get(n, [])+accepted))
        # Pin unchanged capture/identity protocol dependencies, not private models.
        for n in ('software/ps/pcm_capture.py','software/ps/speaker_scheduling.py',
                  'software/ps/speaker_process.py','software/ps/speaker_permission.py'):
            raw = runtime.read('SoundSight_PYNQ_3D_Speaker/'+n)
            if (root/n).read_bytes().replace(b'\r\n', b'\n') != raw.replace(b'\r\n', b'\n'):
                raise ValueError('Untested dependency: '+n)
            requires[n] = hashes(raw)
        manifest = dict(revision=installer.REVISION, capture_revision='CAPTURE_COOPERATIVE_V1',
            filter_policy='CF1_PCM_GAPS_V1', screen_rotation_default=180, files=files, previous=previous, requires=requires, hardware_actions=0,
            board_validation='PENDING', original_archives={
                'previous_update_sha256':hashlib.sha256(a.previous_update.read_bytes()).hexdigest(),
                'p1_sha256':hashlib.sha256(a.p1.read_bytes()).hexdigest(),
                'runtime_sha256':hashlib.sha256(a.runtime.read_bytes()).hexdigest()})
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(a.output, 'w', ZIP_DEFLATED) as out:
            out.writestr('__main__.py', data['tools/install_product.py'])
            out.writestr('manifest.json', json.dumps(manifest, indent=2))
            for n,raw in data.items():out.writestr('payload/'+n, raw)
    installer.load_package(a.output)
    print('PACKAGE_OK='+str(a.output)+' FILES='+str(len(data)))


if __name__ == '__main__':main()
