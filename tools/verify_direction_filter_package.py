"""Offline upgrade/rollback checks against exact runtime and previous patch files."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_product as installer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'previous', 'update'):
        p.add_argument('--'+name, required=True, type=Path)
    args = p.parse_args()
    manifest, payload = installer.load_package(args.update)
    def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='ss-direction-package-') as tmp:
        root = Path(tmp)/'application'; root.mkdir()
        unit = Path(tmp)/'service.unit'
        with ZipFile(args.previous) as old, ZipFile(args.runtime) as full:
            old_manifest = json.loads(old.read('manifest.json'))
            for name in set(manifest['requires']) | set(old_manifest['files']):
                raw = old.read('payload/'+name) if name in old_manifest['files'] else full.read('SoundSight_PYNQ_3D_Speaker/'+name)
                target = root/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        for name, raw in (('settings.local.json', b'{"min_level":12000}'),
                          ('speaker-profiles/P02/profile.json', b'PRIVATE_PROFILE')):
            target=root/name; target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        original_bit=(root/'soundsight.bit').read_bytes()
        receipt=dict(revision='SCREEN_PS_I2C_S2', touch_transport='PS_I2C0_EMIO_LINUX',
            installed_boot_id='original-boot', hardware={'soundsight.bit':digest(root/'soundsight.bit')},
            software={name:digest(root/name) for name in old_manifest['files']})
        (root/'SCREEN-INSTALL.json').write_text(json.dumps(receipt),encoding='utf-8')
        calls=[]
        def ctl(*args):
            calls.append(args)
            value={'is-active':'inactive','show':'loaded','is-enabled':'enabled'}.get(args[0],'')
            return SimpleNamespace(stdout=value, stderr='', returncode=0)
        options=dict(ctl=ctl, unit_root='/home/xilinx/SoundSight_PYNQ_3D_Speaker')
        first=installer.install(args.update,root,unit,**options)
        assert first['filter_policy']=='CF1_PCM_GAPS_V1'
        assert all(digest(root/n)==sha for n,sha in manifest['files'].items())
        assert (root/'settings.local.json').read_bytes()==b'{"min_level":12000}'
        assert (root/'speaker-profiles/P02/profile.json').read_bytes()==b'PRIVATE_PROFILE'
        assert (root/'soundsight.bit').read_bytes()==original_bit
        assert all(c[0] not in ('start','restart','reboot') for c in calls)
        updated=json.loads((root/'SCREEN-INSTALL.json').read_text())
        assert all(digest(root/n)==sha for n,sha in updated['software'].items())
        installer.install(args.update,root,unit,**options)
        target=root/'software/tetra3d/linux/filter_3d.py';target.write_bytes(b'unknown local edit')
        before={n:(root/n).read_bytes() for n in manifest['files']}
        try:
            installer.install(args.update,root,unit,**options)
        except ValueError as exc:
            assert 'BASELINE_MISMATCH' in str(exc) or 'LOCAL_CHANGE_PRESERVED' in str(exc)
        else: raise AssertionError('Unknown local changes overwritten')
        assert all((root/n).read_bytes()==raw for n,raw in before.items())
        print('REAL_PACKAGE_UPGRADE=PASS IDEMPOTENT=PASS PRIVATE_DATA_PRESERVED=PASS LOCAL_EDIT_REFUSED=PASS HARDWARE_ACTIONS=0')


if __name__ == '__main__': main()
