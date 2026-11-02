"""Package a reviewed S2 candidate. Does not alter build or board inputs."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
HW = ROOT.parent if (ROOT.parent/'payload').is_dir() else ROOT.parent/'ss-screen-ps-i2c-s2'
UI = HW/'screen-ui' if (HW/'screen-ui').is_dir() else ROOT.parent/'ss-screen-ps-i2c-ui-s2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def zip_checked(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(files)
        for name, data in files.items():
            assert sha(z.read(name)) == sha(data)
    return dict(path=path.name, bytes=path.stat().st_size, sha256=sha(path.read_bytes()))


def main():
    review = json.loads((ROOT/'acceptance.json').read_text(encoding='utf-8'))
    if review.get('release_scope') != 'AXES_OFF_SCREEN_TOUCH_BOARD_CANDIDATE':
        raise RuntimeError('Missing limited board-candidate review')
    if not review.get('hardware_review_complete') or not review.get('software_review_complete'):
        raise RuntimeError('Independent review incomplete')
    inputs = json.loads((ROOT/'package_inputs.json').read_text(encoding='utf-8'))
    files = {n: (HW/'output'/n).read_bytes() for n in ('soundsight.bit', 'soundsight.hwh')}
    for name in inputs['ui_files']:
        files[name] = (UI/name).read_bytes()
    files['SCREEN-README.md'] = (UI/'SCREEN-README.md').read_bytes()
    expected = review['reviewed_payload_sha256']
    if {n: sha(d) for n, d in files.items()} != expected:
        raise RuntimeError('Payload differs from reviewed candidate')
    manifest = dict(revision='SCREEN_PS_I2C_S2', date='2026-10-31',
                    accepted_hardware=inputs['accepted_hardware'],
                    accepted_files=inputs['accepted_files'],
                    files=expected, validation=review)
    files['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    installer = (ROOT/'install_update.py').read_bytes()
    if sha(installer) != review['installer_sha256']:
        raise RuntimeError('Installer differs from reviewed candidate')
    files['__main__.py'] = installer
    out = ROOT/'delivery'
    out.mkdir(exist_ok=True)
    receipts = [zip_checked(out/'soundsight_screen_ps_i2c_s2.zip', files)]

    source_manifest = json.loads((HW/'reports/screen-source-manifest.json').read_text(encoding='utf-8'))
    sources = {}
    for name, digest in source_manifest.items():
        relative = name.replace('\\', '/')
        data = (HW/relative).read_bytes()
        if sha(data) != digest:
            raise RuntimeError('Build source changed since manifest: '+name)
        sources[relative] = data
    for path in HW.glob('*.tcl'):
        sources[path.name] = path.read_bytes()
    for name in ('build.bat', 'source_files.txt', 'README.md'):
        if (HW/name).is_file():
            sources[name] = (HW/name).read_bytes()
    for folder in ('reports', 'output'):
        for path in (HW/folder).rglob('*'):
            if path.is_file() and path.suffix not in ('.dcp', '.jou', '.log'):
                sources[path.relative_to(HW).as_posix()] = path.read_bytes()
    for path in UI.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.log'):
            sources['screen-ui/'+path.relative_to(UI).as_posix()] = path.read_bytes()
    for path in ROOT.iterdir():
        if path.is_file() and path.suffix in ('.py', '.md', '.json', '.dts', '.dtbo'):
            sources['release-tools/'+path.name] = path.read_bytes()
    for path in (ROOT/'relocation').rglob('*'):
        if path.is_file():
            sources['release-tools/'+path.relative_to(ROOT).as_posix()] = path.read_bytes()
    verification = ROOT.parent/'ss-screen-ps-i2c-verification-s2'
    if verification.is_dir():
        for path in verification.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                sources['verification/'+path.relative_to(verification).as_posix()] = path.read_bytes()
    receipts.append(zip_checked(out/'soundsight_screen_ps_i2c_s2_source.zip', sources))
    (out/'receipt.json').write_text(json.dumps(receipts, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipts, indent=2))


if __name__ == '__main__':
    main()
