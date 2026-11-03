"""Prepare an independent working copy from this submit folder only."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def safe(base, relative):
    if not isinstance(relative, str):
        raise ValueError('Relative path must be text')
    p = PurePosixPath(relative)
    if p.as_posix() != relative:
        raise ValueError('Noncanonical relative path: '+relative)
    if p.is_absolute() or not p.parts or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe relative path: '+relative)
    target = base.joinpath(*p.parts).resolve()
    try: target.relative_to(base.resolve())
    except ValueError: raise ValueError('Path escapes its root: '+relative)
    return target

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True, help='New empty workspace, outside submit')
    args = ap.parse_args()
    output = args.output.resolve()
    try: output.relative_to(ROOT)
    except ValueError: pass
    else: raise ValueError('Workspace must be outside submit')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Refusing to overwrite existing work')
    manifest = json.loads((ROOT/'build/file-map.json').read_text('utf-8'))
    if manifest.get('schema') != 2:
        raise ValueError('Source-preserving submission manifest required')
    inputs=[]; seen=set()
    for entry in manifest['files']:
        display = safe(ROOT, entry['submit_path'])
        source = safe(ROOT, entry['restore_path'])
        target = safe(output, entry['source_path'])
        if str(target).casefold() in seen: raise ValueError('Duplicate output path')
        seen.add(str(target).casefold())
        if hashlib.sha256(display.read_bytes()).hexdigest() != entry['submit_sha256']:
            raise ValueError('Submission file differs from manifest: '+entry['submit_path'])
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry['restore_sha256'] or digest != entry['source_sha256']:
            raise ValueError('Original source differs from manifest: '+entry['restore_path'])
        inputs.append((target,data,entry['mode']))
    output.mkdir(parents=True,exist_ok=True)
    for target,data,mode in inputs:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        if mode == '100755': target.chmod(0o755)
    (output/'README.md').write_text('Generated working copy. Read the original submit/README.md for reproduction steps.\n',encoding='utf-8')
    print('WORKSPACE_READY files='+str(len(inputs))+' EDA_STARTED=0 HARDWARE_ACCESSED=0')
    print(str(output))

if __name__ == '__main__': main()
