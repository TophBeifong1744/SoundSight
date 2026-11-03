"""Build a small P1 software/autostart update; no private assets or hardware writes."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from install_product import REVISION, PAYLOAD, load_package

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def variants(raw, text=True):
    values = {sha(raw)}
    if text:
        lf = raw.replace(b'\r\n', b'\n')
        values.update((sha(lf), sha(lf.replace(b'\n', b'\r\n'))))
    return sorted(values)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    data = {n:(ROOT/n).read_bytes().replace(b'\r\n', b'\n') for n in PAYLOAD}
    for n,v in data.items():
        if n.endswith('.py'): ast.parse(v.decode('utf-8'), feature_version=(3,8))
    baseline = json.loads((ROOT/'software/screen/product-baseline.json').read_text('utf-8'))
    # Explicit baseline metadata makes packaging work from an exported workspace
    # without Git history, and rejects silent retargeting to unrelated hardware.
    for n, accepted in baseline['requires'].items():
        path = ROOT/'release/output/screen_s2'/n if n in ('soundsight.bit', 'soundsight.hwh') else ROOT/n
        if n not in data and sha(path.read_bytes()) not in accepted:
            raise ValueError('Packaging baseline differs: '+n)
    m = dict(revision=REVISION, baseline=baseline['baseline'], files={n:sha(v) for n,v in data.items()},
             previous=baseline['previous'], requires=baseline['requires'], hardware_actions=0, board_validation='PENDING')
    content = {'payload/'+n:v for n,v in data.items()}
    content['manifest.json'] = (json.dumps(m, indent=2)+'\n').encode()
    content['__main__.py'] = data['tools/install_product.py']
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(a.output, 'w', ZIP_DEFLATED) as z:
        for n,v in sorted(content.items()):
            info = ZipInfo(n, (2026,11,3,0,0,0)); info.compress_type = ZIP_DEFLATED
            info.create_system = 3; info.external_attr = (0o100755 if n.endswith('.sh') else 0o100644)<<16
            z.writestr(info, v)
    load_package(a.output)
    print(json.dumps(dict(output=str(a.output.resolve()), files=len(content),
                         bytes=a.output.stat().st_size, hardware_actions=0, board_validation='PENDING')))


if __name__ == '__main__':
    main()
