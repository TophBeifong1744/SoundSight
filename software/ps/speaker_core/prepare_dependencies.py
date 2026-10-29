"""Prepare pinned ORT build archives on the Linux build host; never on PYNQ.

Pass an existing checkout of the exact ORT revision. Only its cmake/deps.txt
download locations are updated, with an exclusive original backup. No installs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--cache',type=Path,required=True)
    ap.add_argument('--verify-only',action='store_true')
    args=ap.parse_args()
    source=args.source.resolve();cache=args.cache.resolve()
    lock=json.loads(Path(__file__).with_name('build-lock.json').read_text())
    revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if revision!=lock['onnxruntime']['commit']:raise RuntimeError('ORT_SOURCE_VERSION_MISMATCH')
    checked=subprocess.run(['git','-c','core.safecrlf=false','-C',str(source),'diff','--name-only','HEAD'],
                           text=True,capture_output=True,check=True)
    changed=checked.stdout.splitlines()
    if any(p!='cmake/deps.txt' for p in changed):raise RuntimeError('ORT_IMPLEMENTATION_HAS_LOCAL_CHANGES')
    cache.mkdir(parents=True,exist_ok=True)

    def fetch(row):
        path=cache/(row['name']+'.zip')
        if not path.exists():
            if args.verify_only:raise RuntimeError('MISSING_ARCHIVE: '+row['name'])
            with urllib.request.urlopen(row['upstream'],timeout=90) as response:
                data=response.read()
            if hashlib.sha256(data).hexdigest()!=row['sha256']:raise RuntimeError('DOWNLOAD_HASH_MISMATCH: '+row['name'])
            with path.open('xb') as f:f.write(data)
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256'] or hashlib.sha1(data).hexdigest()!=row['sha1']:
            raise RuntimeError('CACHE_HASH_MISMATCH: '+row['name'])
        return row['name']

    with ThreadPoolExecutor(max_workers=8) as pool:
        for name in pool.map(fetch,lock['dependencies']):print('VERIFIED',name,flush=True)
    if args.verify_only:return
    path=source/'cmake/deps.txt';backup=source/'cmake/deps.upstream.txt'
    if not backup.exists():
        with backup.open('xb') as f:f.write(path.read_bytes())
    mapping={r['name']:r for r in lock['dependencies']};lines=[];used=set()
    for line in backup.read_text().splitlines():
        parts=line.split(';')
        if parts[0] in mapping:
            row=mapping[parts[0]];used.add(parts[0])
            if parts[1]!=row['upstream']:raise RuntimeError('DEPENDENCY_URL_CHANGED: '+parts[0])
            parts[1]=(cache/(parts[0]+'.zip')).as_posix();parts[2]=row['sha1'];line=';'.join(parts)
        lines.append(line)
    if used!=set(mapping):raise RuntimeError('DEPENDENCY_SET_MISMATCH')
    path.write_text('\n'.join(lines)+'\n')
    print('DEPENDENCIES_READY=1')


if __name__=='__main__':main()
