"""Install transaction tests using synthetic files; no hardware or private assets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import install_current_runtime as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root/'board'
        self.zip = self.root/'runtime.zip'
        self.files = {n:b'payload:'+n.encode() for n in installer.HARDWARE+installer.SCREEN+
                      ('soundsight-3d.sh','soundsight-panel.sh','SOURCE.json','software/ps/example.py')}
        self.manifest = dict(revision=installer.REVISION,source_commit='test',private_assets=[],
            files={n:installer.digest(b) for n,b in self.files.items()})
        self.pack()

    def pack(self):
        with ZipFile(self.zip,'w') as z:
            z.writestr('__main__.py','')
            z.writestr('manifest.json',json.dumps(self.manifest))
            for n,b in self.files.items():z.writestr(installer.PREFIX+n,b)

    def install(self,boot='real-test-boot'):
        return installer.install(self.zip,self.target,boot)

    def test_fresh_and_idempotent_receipt(self):
        a=self.install()
        self.assertTrue(a['reboot_required'])
        b=self.install('next-boot')
        self.assertFalse(b['reboot_required'])
        self.assertEqual(b['changed_files'],0)
        self.assertEqual(json.loads((self.target/'SCREEN-INSTALL.json').read_text())['installed_boot_id'],'real-test-boot')

    def test_settings_profiles_logs_preserved(self):
        self.install()
        for n in ('speaker-target.local.json','speaker-follow.local.json','servo3d.local.json',
                  'settings.local.json','speaker-profiles/toph/profile.json','logs/previous.json'):
            p=self.target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'personal')
        self.files['software/ps/example.py']=b'changed'
        self.manifest['files']['software/ps/example.py']=installer.digest(b'changed');self.pack()
        a=self.install('new-boot')
        self.assertEqual((Path(a['backup'])/'software/ps/example.py').read_bytes(),b'payload:software/ps/example.py')
        for n in ('speaker-target.local.json','speaker-profiles/toph/profile.json','logs/previous.json'):
            self.assertEqual((self.target/n).read_bytes(),b'personal')

    def test_wrong_hardware_no_writes(self):
        self.install();(self.target/'soundsight.bit').write_bytes(b'NEW_B_HARDWARE')
        before={p.relative_to(self.target):p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'HARDWARE_MISMATCH'):self.install()
        self.assertEqual(before,{p.relative_to(self.target):p.read_bytes() for p in self.target.rglob('*') if p.is_file()})

    def test_product_receipt_tracks_upgrade_without_enabling_service(self):
        self.manifest['product_files'] = ['software/ps/example.py']
        self.pack(); self.install()
        self.files['software/ps/example.py'] = b'updated product source'
        self.manifest['files']['software/ps/example.py'] = installer.digest(self.files['software/ps/example.py'])
        self.pack(); self.install('next-boot')
        receipt = json.loads((self.target/'PRODUCT-INSTALL.json').read_text())
        self.assertEqual(receipt['revision'], 'SCREEN_PRODUCT_P1')
        self.assertEqual(receipt['files']['software/ps/example.py'], installer.digest(self.files['software/ps/example.py']))
        self.assertEqual(self.install('next-boot')['changed_files'], 0)

    def test_invalid_product_dependency_rejected_before_writes(self):
        self.manifest['product_files'] = ['missing.py']; self.pack()
        with self.assertRaisesRegex(ValueError, 'Invalid product'): self.install()
        self.assertFalse(self.target.exists())

    def test_private_asset_change_rejected(self):
        self.install();self.manifest['private_assets']=['software/ps/example.py'];self.pack()
        (self.target/'software/ps/example.py').write_bytes(b'private-independent')
        with self.assertRaisesRegex(ValueError,'PRIVATE_ASSET_DIFFERS'):self.install()

    def test_corruption_and_missing_payload_rejected(self):
        self.manifest['files']['soundsight.bit']='0'*64;self.pack()
        with self.assertRaisesRegex(ValueError,'Corrupt'):self.install()
        self.assertFalse(self.target.exists())

    def test_protected_and_traversal_names_rejected(self):
        for name in ('../escape','/absolute','C:/escape','settings.local.json','speaker-profiles/toph/profile.json',
                     'software/tetra3d/das/das_3d.py','SCREEN-INSTALL.json'):
            self.files[name]=b'x';self.manifest['files'][name]=installer.digest(b'x');self.pack()
            with self.assertRaises(ValueError):self.install()
            del self.files[name];del self.manifest['files'][name]
        self.assertFalse(self.target.exists())

    def test_rollback_on_replace_failure(self):
        self.install();path=self.target/'software/ps/example.py';path.write_bytes(b'old')
        real=installer.os.replace;calls=[]
        def fail(src,dst):
            calls.append(str(dst))
            if len(calls)==2:raise OSError('injected disk failure')
            return real(src,dst)
        (self.target/'SOURCE.json').write_bytes(b'old metadata')
        with patch.object(installer.os,'replace',side_effect=fail):
            with self.assertRaisesRegex(OSError,'injected'):self.install()
        self.assertEqual(path.read_bytes(),b'old')
        self.assertEqual((self.target/'SOURCE.json').read_bytes(),b'old metadata')

    def test_empty_boot_id_rejected(self):
        with self.assertRaises(ValueError):self.install('')
        self.assertFalse(self.target.exists())

    def test_fresh_failure_can_retry_without_deleting_evidence(self):
        real=installer.os.replace; count=[0]
        def fail(src,dst):
            count[0]+=1
            if count[0]==2:raise OSError('fresh install failure')
            return real(src,dst)
        with patch.object(installer.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):self.install()
        self.assertTrue((self.target/'RUNTIME-INCOMPLETE.json').exists())
        self.assertTrue(self.install()['reboot_required'])
        self.assertFalse((self.target/'RUNTIME-INCOMPLETE.json').exists())
        self.assertEqual(len(list(self.target.glob('backup_runtime_*'))),2)


if __name__=='__main__':unittest.main(verbosity=2)
