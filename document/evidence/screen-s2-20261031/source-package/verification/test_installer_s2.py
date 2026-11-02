"""Real S2 candidate installation into disposable copies of actual A+S1 runtime."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RELEASE=ROOT/'ss-screen-ps-i2c-release-s2'
CANDIDATE=RELEASE/'test-candidate.zip'

def sha(data):return hashlib.sha256(data).hexdigest()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
INSTALL=load(RELEASE/'install_update.py','installer_s2_tested')


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir=HERE,prefix='baseline_')
        cls.base=Path(cls.temp.name)
        with zipfile.ZipFile(ROOT/'download/soundsight_pynq_3d_speaker.zip') as z:z.extractall(cls.base)
        cls.template=cls.base/'SoundSight_PYNQ_3D_Speaker'
        with zipfile.ZipFile(ROOT/'ss-screen-release-s1/delivery/soundsight_screen_s1.zip') as z:
            manifest=json.loads(z.read('manifest.json'))
            for name in manifest['files']:
                p=cls.template/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
        cls.sentinels={'servo3d.local.json':b'{"private_calibration":110}',
                       'speaker-target.local.json':b'{"target_id":"private-user"}',
                       'speaker-follow.local.json':b'{"threshold":0.45,"permit_seconds":10}',
                       'speaker-profiles/private-user/profile.json':b'{"private":"retain"}',
                       'speaker-profiles/private-user/embedding.npy':b'private-opaque-vector',
                       'logs/private.log':b'original-board-log'}
        for name,data in cls.sentinels.items():
            p=cls.template/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        with zipfile.ZipFile(CANDIDATE) as z:
            cls.manifest=json.loads(z.read('manifest.json'))
            cls.payload={name:z.read(name) for name in cls.manifest['files']}

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=HERE,prefix='install_');self.addCleanup(self.tmp.cleanup)
        self.target=Path(self.tmp.name)/'runtime';shutil.copytree(self.template,self.target)

    def snapshot(self):
        return {p.relative_to(self.target).as_posix():sha(p.read_bytes()) for p in self.target.rglob('*')
                if p.is_file() and not p.relative_to(self.target).parts[0].startswith('backup_screen_ps_i2c_s2_')}

    def install(self,archive=CANDIDATE):
        with contextlib.redirect_stdout(io.StringIO()):return INSTALL.install(archive,self.target,'prior-board-boot')

    def test_accepts_exact_S1_S1a_S1b_repeat_preserves_originals(self):
        original=self.snapshot()
        for variant,folder in [('S1','ss-screen-ui-s1'),('S1a','ss-screen-iic-s1a'),('S1b','ss-screen-iic-s1b')]:
            with self.subTest(variant=variant):
                self.target=Path(self.tmp.name)/('runtime_'+variant)
                shutil.copytree(self.template,self.target)
                (self.target/'software/screen/hardware.py').write_bytes((ROOT/folder/'software/screen/hardware.py').read_bytes())
                backup=self.install()
                receipt=json.loads((self.target/'SCREEN-INSTALL.json').read_text())
                self.assertEqual(receipt['installed_boot_id'],'prior-board-boot')
                self.assertEqual(receipt['touch_transport'],'PS_I2C0_EMIO_LINUX')
                self.assertEqual(receipt['revision'],'SCREEN_PS_I2C_S2')
                for name,data in self.payload.items():self.assertEqual((self.target/name).read_bytes(),data,name)
                for name,digest in original.items():
                    if name not in self.payload and name not in ('SOURCE.json','SCREEN-INSTALL.json'):
                        self.assertEqual(sha((self.target/name).read_bytes()),digest,name)
                self.assertNotEqual(self.install(),backup)

    def test_unknown_local_and_hardware_rejected_without_mutation(self):
        for name in ('software/screen/hardware.py','soundsight.bit'):
            with self.subTest(name=name):
                original=(self.target/name).read_bytes();(self.target/name).write_bytes(b'unknown-local-version')
                before=self.snapshot()
                with self.assertRaisesRegex(RuntimeError,'Unrecognized'):self.install()
                self.assertEqual(self.snapshot(),before)
                self.assertFalse(list(self.target.glob('backup_screen_ps_i2c_s2_*')))
                (self.target/name).write_bytes(original)

    def test_checksum_and_revision_rejected_without_mutation(self):
        for kind in ('checksum','revision'):
            with self.subTest(kind=kind):
                altered=Path(self.tmp.name)/(kind+'.zip')
                with zipfile.ZipFile(CANDIDATE) as source,zipfile.ZipFile(altered,'w') as dest:
                    for name in source.namelist():
                        data=source.read(name)
                        if kind=='checksum' and name=='software/screen/linux_i2c.py':data+=b'corrupt'
                        if kind=='revision' and name=='manifest.json':
                            m=json.loads(data);m['revision']='UNKNOWN';data=json.dumps(m).encode()
                        dest.writestr(name,data)
                before=self.snapshot()
                with self.assertRaises(RuntimeError):self.install(altered)
                self.assertEqual(before,self.snapshot())
                self.assertFalse(list(self.target.glob('backup_screen_ps_i2c_s2_*')))

    def test_backup_ledger_and_each_replacement_failure_restores_present_absent(self):
        before=self.snapshot();replaced=set(self.payload)|{'SOURCE.json','SCREEN-INSTALL.json'}
        for fail_at in range(1,len(replaced)+1):
            with self.subTest(fail_at=fail_at):
                real_replace=INSTALL.os.replace;calls=[0]
                def failing_replace(src,dest):
                    calls[0]+=1
                    if calls[0]==fail_at:raise OSError('injected replacement failure')
                    return real_replace(src,dest)
                with patch.object(INSTALL.os,'replace',failing_replace),self.assertRaisesRegex(OSError,'injected replacement failure'):
                    self.install()
                self.assertEqual(self.snapshot(),before)
                self.assertFalse(list(self.target.glob('.screen_ps_i2c_s2_stage_*')))
        for backup in self.target.glob('backup_screen_ps_i2c_s2_*'):
            ledger=json.loads((backup/'restore.json').read_text())
            self.assertEqual(set(ledger['present']),set(before)&replaced)
            self.assertEqual(set(ledger['absent']),replaced-set(before))
            for name in ledger['present']:self.assertEqual(sha((backup/name).read_bytes()),before[name])


if __name__=='__main__':unittest.main(verbosity=2)
