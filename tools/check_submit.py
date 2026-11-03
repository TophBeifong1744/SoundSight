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


def relative_path(value):
    """Validate manifest paths before indexing files or restoring a workspace."""
    if not isinstance(value, str):
        raise ValueError('Relative path must be text')
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or '..' in path.parts or
            chr(92) in value or ':' in value or path.as_posix() != value):
        raise ValueError('Unsafe relative path: '+value)
    return value


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
    assert manifest.get('schema')==2, 'Source-preserving submission manifest required'
    forbidden=('software/stm32/', 'software/vitis/', 'research/six-mic/', 'models/', 'document/posters/', 'software/tetra3d/das/', 'data/fixtures/h3_portable/', 'data/fixtures/h1/')
    seen={field:set() for field in ('source_path','submit_path','restore_path')}
    for item in manifest['files']:
        for field in seen:
            value=relative_path(item[field])
            assert value.casefold() not in seen[field], 'Duplicate '+field+': '+value
            seen[field].add(value.casefold())
        assert not item['source_path'].startswith(forbidden),item['source_path']
        if item['source_path'].startswith('release/output/'):
            assert (item['source_path'].startswith('release/output/screen_s2/') or
                    item['source_path']=='release/output/soundsight_screen_product_p1.zip'),item['source_path']
        assert hashlib.sha256(files[item['submit_path']].read_bytes()).hexdigest()==item['submit_sha256'],item['submit_path']
        original=files[item['restore_path']].read_bytes()
        assert hashlib.sha256(original).hexdigest()==item['restore_sha256'],item['restore_path']
        assert item['restore_sha256']==item['source_sha256'],item['source_path']
        if item['transform']=='documentation_links_only':
            assert item['source_path'].endswith(('.md','.html')),item['source_path']
            assert item['restore_path']=='build/restore/'+item['submit_path']+'.bin',item['restore_path']
        else:
            assert item['transform']=='none',item['transform']
            assert item['restore_path']==item['submit_path'],item['restore_path']
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
    result={'scope':'SUBMISSION_PACKAGING_ONLY','files':len(files),'category_files':{c:sum(n.startswith(c+'/') for n in files) for c in sorted(categories)},'manifest_files':len(manifest['files']),'relative_links':links,'broken_links':0,'filename_check':'PASS','raw_sources_and_results':'PASS','display_and_restore_integrity':'PASS','original_document_copies':sum(x['transform']=='documentation_links_only' for x in manifest['files']),'eda':'NOT_RUN','hardware':'NOT_RUN','tests':[]}
    # ZIP extraction is the only input used below. No checkout files are used by the child process.
    # Keep the generated S2 path within Vivado's 78-byte limit on Windows.
    with tempfile.TemporaryDirectory(prefix='ss check ',dir=args.work_parent.resolve()) as temp:
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
            restored=(work/item['source_path']).read_bytes()
            assert restored==(isolated/item['restore_path']).read_bytes(),item['source_path']
            assert hashlib.sha256(restored).hexdigest()==item['source_sha256'],item['source_path']
        for pattern in ('test_current_runtime.py','test_volume_gate.py'):
            run=call([sys.executable,'-B','-m','unittest','discover','-s','software/tests','-p',pattern],work)
            result['tests'].append({'pattern':pattern,'exit':run.returncode,'output':run.stdout})
            assert run.returncode==0,run.stdout
        if (work/'tools/prepare_screen_s2.py').is_file():
            # ASCII short output is a vendor path requirement, not a source-tree dependency.
            s2=base/'s2'
            run=call([sys.executable,'-B','tools/prepare_screen_s2.py','--output',str(s2)],work)
            assert run.returncode==0,run.stdout
            recipe=json.loads((work/'project/screen_s2/source-map.json').read_text('utf-8'))
            for item in recipe['files']:
                assert hashlib.sha256((s2/item['destination']).read_bytes()).hexdigest()==item['sha256']
            assert 'D:\\AMD' not in (s2/'build.bat').read_text()
            again=call([sys.executable,'-B','tools/prepare_screen_s2.py','--output',str(s2)],work)
            assert again.returncode!=0 and 'Refusing to overwrite' in again.stdout
            result['s2_recipe']={'files':len(recipe['files']),'payload_hashes':'PASS','overwrite_rejected':True,'eda':'NOT_RUN'}
        if (work/'tools/check_current_software.py').is_file():
            run=call([sys.executable,'-B','tools/check_current_software.py','--output',str(base/'host-check')],work)
            assert run.returncode==0,run.stdout
            result['current_software']=json.loads((base/'host-check/result.json').read_text('utf-8'))
        if (work/'tools/package_product.py').is_file():
            # Rebuild the public P1 update without Git or the outer checkout.
            package=base/'product.zip'
            run=call([sys.executable,'-B','tools/package_product.py','--output',str(package)],work)
            assert run.returncode==0,run.stdout
            with zipfile.ZipFile(package) as z:
                assert z.testzip() is None
                result['product_update']={'standalone_rebuild':'PASS','files':len(z.namelist()),
                                          'hardware':'NOT_RUN','board_validation':'PENDING'}
            delivered=work/'release/output/soundsight_screen_product_p1.zip'
            assert delivered.is_file(), 'Missing current installable P1 update'
            assert delivered.read_bytes()==package.read_bytes(), 'P1 ZIP differs from included source'
            result['product_update']['delivered_matches_rebuilt']='PASS'
        reject=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(work)],isolated)
        assert reject.returncode!=0 and 'Refusing to overwrite' in reject.stdout
        # Check missing input and attempted traversal before any files can be emitted.
        tracked=isolated/manifest['files'][0]['submit_path'];original=tracked.read_bytes();tracked.unlink()
        missing=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'missing')],isolated)
        assert missing.returncode!=0 and not (base/'missing').exists()
        tracked.parent.mkdir(parents=True,exist_ok=True);tracked.write_bytes(original)
        # Display copies and original restore bytes are independently required.
        rewritten=next((x for x in manifest['files'] if x['transform']=='documentation_links_only'),None)
        if rewritten:
            restore=isolated/rewritten['restore_path'];raw=restore.read_bytes();restore.unlink()
            missing_restore=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'missing-restore')],isolated)
            assert missing_restore.returncode!=0 and not (base/'missing-restore').exists()
            restore.write_bytes(raw+b'corruption')
            corrupt_restore=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'corrupt-restore')],isolated)
            assert corrupt_restore.returncode!=0 and not (base/'corrupt-restore').exists()
            restore.write_bytes(raw)
        map_path=isolated/'build/file-map.json';bad=json.loads(map_path.read_text('utf-8'));bad['files'][0]['source_path']='../escape.txt';map_path.write_text(json.dumps(bad),encoding='utf-8')
        traversal=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'invalid')],isolated)
        assert traversal.returncode!=0 and not (base/'escape.txt').exists()
        bad=json.loads(json.dumps(manifest));bad['files'][0]['restore_path']='../escape.txt';map_path.write_text(json.dumps(bad),encoding='utf-8')
        restore_traversal=call([sys.executable,'-B','build/prepare_workspace.py','--output',str(base/'invalid-restore')],isolated)
        assert restore_traversal.returncode!=0 and not (base/'invalid-restore').exists()
        result['isolation']={'zip_crc':'PASS','workspace_restore_files':len(manifest['files']),'outside_repository':'PASS','overwrite_rejected':True,'missing_input_rejected':True,'path_traversal_rejected':True,'restore_traversal_rejected':True,'missing_and_corrupt_original_rejected':bool(rewritten)}
    args.result.parent.mkdir(parents=True,exist_ok=True)
    args.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
