"""Exercise actual archive installer, fault rollback and explicit restoration."""
import importlib.util,json,os
from pathlib import Path
import tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'delivery/soundsight_three_d_coherent_cf1a.zip'
BASE=ROOT.parent/'ss-c-board-test-20261031/delivery/soundsight_c_three_tests_20261031_v2_private.zip'
with zipfile.ZipFile(PACKAGE) as z:
    CODE=z.read('__main__.py');MANIFEST=json.loads(z.read('manifest.json'))
spec=importlib.util.spec_from_loader('cf1_installer',loader=None)
m=importlib.util.module_from_spec(spec);exec(compile(CODE,'PACKAGE/__main__.py','exec'),m.__dict__)

class InstallerTests(unittest.TestCase):
    def fixture(self,root):
        with zipfile.ZipFile(BASE) as z:
            for name in set(MANIFEST['dependencies'])|set(MANIFEST['files']):
                entry='code/SoundSight_PYNQ_3D_Speaker/'+name
                if entry in z.namelist():
                    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(entry))
        receipt=dict(revision='SCREEN_PS_I2C_S2',touch_transport='PS_I2C0_EMIO_LINUX',control_revision='SCREEN_CONTROL_S3',
                     installed_boot_id='KEEP_REAL_BOOT_ID',software={'software/screen/ui.py':MANIFEST['dependencies']['software/screen/ui.py']},
                     hardware={k:MANIFEST['dependencies'][k] for k in ('soundsight.bit','soundsight.hwh')})
        (root/'SCREEN-INSTALL.json').write_text(json.dumps(receipt))
        with zipfile.ZipFile(ROOT.parent/'ss-three-d-coherent-cf1/delivery/soundsight_three_d_coherent_cf1.zip') as prior:
            old_manifest = json.loads(prior.read('manifest.json'))
            for name in old_manifest['files']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(prior.read(name))
            old_receipt = dict(revision='THREE_D_COHERENT_CF1',files=old_manifest['files'],hardware_unchanged=True,board_joint_test='NOT_RUN')
            (root/'THREE-D-CF1-INSTALL.json').write_bytes((json.dumps(old_receipt,indent=2)+'\n').encode())
            receipt['software'].update(old_manifest['files'])
            receipt['direction_revision']='THREE_D_COHERENT_CF1'
            (root/'SCREEN-INSTALL.json').write_text(json.dumps(receipt))
        for name in ('servo3d.local.json','horizontal.local.json','settings.local.json','speaker-follow.local.json','speaker-profiles/P02-v1/profile.json'):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'PRIVATE_SENTINEL')
        return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def unchanged(self,root,original):
        for name,data in original.items():self.assertEqual((root/name).read_bytes(),data,name)
        for name,before in MANIFEST['before'].items():
            if before is None:self.assertFalse((root/name).exists(),name)
        self.assertFalse((root/'THREE-D-CF1A-INSTALL.json').exists())

    def test_install_repeat_restore_and_private_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'verification') as temp:
            root=Path(temp);original=self.fixture(root)
            backup=m.install(PACKAGE,root)
            self.assertIsNone(m.install(PACKAGE,root))
            for name,data in original.items():
                if 'local.json' in name or 'P02' in name or name == 'THREE-D-CF1-INSTALL.json':self.assertEqual((root/name).read_bytes(),data)
            receipt=json.loads((root/'SCREEN-INSTALL.json').read_text())
            self.assertEqual(receipt['installed_boot_id'],'KEEP_REAL_BOOT_ID')
            m.restore(root,backup);self.unchanged(root,original)

    def test_every_install_replace_failure_rolls_back(self):
        for fail_at in range(1,len(MANIFEST['files'])+3):
            with self.subTest(fail_at=fail_at),tempfile.TemporaryDirectory(dir=ROOT/'verification') as temp:
                root=Path(temp);original=self.fixture(root);replace=os.replace;calls=[0]
                def injected(a,b):
                    calls[0]+=1
                    if calls[0]==fail_at:raise OSError('injected replace failure')
                    return replace(a,b)
                with patch.object(m.os,'replace',side_effect=injected),self.assertRaises(OSError):m.install(PACKAGE,root)
                self.unchanged(root,original)

    def test_unknown_local_edit_and_wrong_dependency_rejected(self):
        for name in ('software/tetra3d/linux/board_3d.py','soundsight.bit'):
            with tempfile.TemporaryDirectory(dir=ROOT/'verification') as temp:
                root=Path(temp);self.fixture(root);(root/name).write_bytes(b'USER_EDIT')
                with self.assertRaises(RuntimeError):m.install(PACKAGE,root)
                self.assertEqual((root/name).read_bytes(),b'USER_EDIT')
                self.assertFalse(list(root.glob('backup_three_d_cf1a_*')))

    def test_restore_refuses_changed_current_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'verification') as temp:
            root=Path(temp);self.fixture(root);backup=m.install(PACKAGE,root)
            file=root/'software/tetra3d/linux/board_3d.py';file.write_bytes(b'NEXT_EDIT')
            with self.assertRaises(RuntimeError):m.restore(root,backup)
            self.assertEqual(file.read_bytes(),b'NEXT_EDIT')

if __name__=='__main__':unittest.main(verbosity=2)
