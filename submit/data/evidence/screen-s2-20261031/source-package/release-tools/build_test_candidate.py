"""Internal review fixture using actual outputs; never a release approval."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent
hw = root.parent if (root.parent/'payload').is_dir() else root.parent/'ss-screen-ps-i2c-s2'
ui = hw/'screen-ui' if (hw/'screen-ui').is_dir() else root.parent/'ss-screen-ps-i2c-ui-s2'
inputs = json.loads((root/'package_inputs.json').read_text(encoding='utf-8'))
files = {n: (hw/'output'/n).read_bytes() for n in ('soundsight.bit', 'soundsight.hwh')}
files.update({n: (ui/n).read_bytes() for n in inputs['ui_files']})
files['SCREEN-README.md'] = (ui/'SCREEN-README.md').read_bytes()
hashes = {n: hashlib.sha256(data).hexdigest() for n, data in files.items()}
manifest = dict(revision='SCREEN_PS_I2C_S2', validation={'status': 'INTERNAL_REVIEW_ONLY'},
                accepted_hardware=inputs['accepted_hardware'], accepted_files=inputs['accepted_files'], files=hashes)
files['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
files['__main__.py'] = (root/'install_update.py').read_bytes()
with zipfile.ZipFile(root/'test-candidate.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in sorted(files.items()):
        z.writestr(name, data)
with zipfile.ZipFile(root/'test-candidate.zip') as z:
    assert z.testzip() is None
(root/'candidate-payload-hashes.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
print('INTERNAL_REVIEW_CANDIDATE_READY')
