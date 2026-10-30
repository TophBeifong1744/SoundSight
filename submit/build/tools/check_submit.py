"""Check a submit folder without EDA, hardware or the development tree."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--submit',type=Path,required=True)
    ap.add_argument('--work-parent',type=Path,required=True)
    ap.add_argument('--result',type=Path,required=True)
    args=ap.parse_args(); root=args.submit.resolve()
    categories={'src','sim','build','board','data','skill','report'}
    assert {p.name for p in root.iterdir()} == categories|{'README.md'}
    files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    assert not any(p.is_symlink() for p in root.rglob('*'))
    for name in files:
        assert all(c=='README.md' or re.fullmatch(r'[a-z0-9_.-]+',c) for c in name.split('/')),name
    for cat in categories:
        assert sum(n.startswith(cat+'/') for n in files)>2,cat
    manifest=json.loads((root/'build/file-map.json').read_text('utf-8'))
    for item in manifest['files']:
        assert hashlib.sha256(files[item['submit_path']].read_bytes()).hexdigest()==item['submit_sha256'],item['submit_path']
        if not item['source_path'].endswith(('.md','.html')):
            assert item['source_sha256']==item['submit_sha256'],item['source_path']
    universe=set(files)|{'.'}
    for f in files: universe.update(str(p) for p in PurePosixPath(f).parents)
    broken=[];links=0
    for name,path in files.items():
        if not name.endswith(('.md','.html')):continue
        text=path.read_text('utf-8-sig')
        text=re.sub(r'```.*?```','',text,flags=re.S)
        targets=re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)',text) if name.endswith('.md') else [m[1] for m in re.findall(r'(?:href|src)=(\x22|\x27)(.*?)\1',text)]
        for target in targets:
            target=target.strip().strip('<>')
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:|^#',target):continue
            target=unquote(target.split('#',1)[0].split('?',1)[0])
            dest=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
            links+=1
            if dest not in universe:broken.append({'document':name,'target':target,'resolved':dest})
    if broken:
        print(json.dumps({'broken_links':broken},ensure_ascii=True,indent=2));raise SystemExit(1)
    args.work_parent.mkdir(parents=True,exist_ok=True)
    result={'scope':'SUBMISSION_PACKAGING_ONLY','files':len(files),'category_files':{c:sum(n.startswith(c+'/') for n in files) for c in sorted(categories)},'manifest_files':len(manifest['files']),'relative_links':links,'broken_links':0,'filename_check':'PASS','raw_sources_and_results':'PASS','eda':'NOT_RUN','hardware':'NOT_RUN','tests':[]}
    # ZIP extraction is the only input used below. No checkout files are used by the child process.
    with tempfile.TemporaryDirectory(prefix='submit isolation ',dir=args.work_parent.resolve()) as temp:
        base=Path(temp);zpath=base/'submission.zip'
        with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
            for name,path in files.items():z.write(path,'submit/'+name)
        with zipfile.ZipFile(zpath) as z:
            assert z.testzip() is None
            z.extractall(base/'unpacked')
        isolated=base/'unpacked/submit';work=base/'workspace'
        env=os.environ.copy()
        for key in ('PYTHONPATH','PYTHONHOME','PYTHONUSERBASE'):env.pop(key,None)
        def call(argv,cwd):
            return subprocess.run(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=120)
        prep=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(work)],isolated)
        assert prep.returncode==0,prep.stdout
        for item in manifest['files']:
            assert (work/item['source_path']).read_bytes()==(isolated/item['submit_path']).read_bytes(),item['source_path']
        for pattern in ('test_vivado_portable.py','test_volume_gate.py'):
            run=call([sys.executable,'-B','-m','unittest','discover','-s','software/tests','-p',pattern],work)
            result['tests'].append({'pattern':pattern,'exit':run.returncode,'output':run.stdout})
            assert run.returncode==0,run.stdout
        reject=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(work)],isolated)
        assert reject.returncode!=0 and 'Refusing to overwrite' in reject.stdout
        # Check missing input and attempted traversal before any files can be emitted.
        tracked=isolated/manifest['files'][0]['submit_path'];original=tracked.read_bytes();tracked.unlink()
        missing=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'missing')],isolated)
        assert missing.returncode!=0 and not (base/'missing').exists()
        tracked.parent.mkdir(parents=True,exist_ok=True);tracked.write_bytes(original)
        map_path=isolated/'build/file-map.json';bad=json.loads(map_path.read_text('utf-8'));bad['files'][0]['source_path']='../escape.txt';map_path.write_text(json.dumps(bad),encoding='utf-8')
        traversal=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'invalid')],isolated)
        assert traversal.returncode!=0 and not (base/'escape.txt').exists()
        result['isolation']={'zip_crc':'PASS','workspace_restore_files':len(manifest['files']),'outside_repository':'PASS','overwrite_rejected':True,'missing_input_rejected':True,'path_traversal_rejected':True}
    args.result.parent.mkdir(parents=True,exist_ok=True)
    args.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
