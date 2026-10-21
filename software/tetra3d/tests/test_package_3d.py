"""3D delivery/serial checks with real extraction, shell stdin and native C build.

No serial port, PYNQ, hardware, ARM executable or board action is used.
Compiler/shell locations come from SS_GCC/SS_BASH or PATH.
"""
import contextlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'software/tetra3d/linux'))
import package_serial_3d as package
PYTHON=[sys.executable,'-E','-s','-B','-X','utf8']


def shell_path(path):
    path=Path(path).resolve()
    if os.name=='nt': return '/'+path.drive[0].lower()+path.as_posix()[2:]
    return str(path)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='ss3-package-')
        cls.root=Path(cls.temp.name)
        cls.bash=os.environ.get('SS_BASH') or shutil.which('bash')
        cls.cc=os.environ.get('SS_GCC') or shutil.which('gcc')
        if not cls.bash or not cls.cc: raise RuntimeError('TOOL_ENV_FAIL: configure SS_BASH and SS_GCC or PATH')
        cls.output=cls.root/'serial package.zip'
        with contextlib.redirect_stdout(io.StringIO()): cls.payload,cls.lines=package.build(cls.output)
        cls.files=package.selected_files()
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def shell(self,lines,case):
        root=self.root/case; root.mkdir()
        stage=root/'inbox with spaces'; dest=root/'destination with spaces'
        commands=list(lines)
        commands[0]='ss3_stage='+shlex.quote(shell_path(stage))
        commands[1]='ss3_dest='+shlex.quote(shell_path(dest))
        run=subprocess.run([self.bash,'--noprofile','--norc','-s'],input='\n'.join(commands)+'\n',
                           capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
        return run,stage,dest
    def test_archive_dependencies_and_ascii_command_bounds(self):
        required={'software/tetra3d/linux/run_buffered_3d.py','software/tetra3d/linux/run_smp_3d.py',
                  'software/tetra3d/linux/runtime_3d.py','software/tetra3d/linux/solver_3d.py',
                  'software/tetra3d/core/tetra40-nominal.json','software/ps/run_buffered.py',
                  'software/ps/volume_gate.py','software/ps/ram_queue.py','software/ps/recover_ram.py',
                  'software/common/fpga_stm32_abi_frozen.h','software/common/s1/doa_solver.c',
                  'software/tetra3d/tests/solver_3d_reference.c',package.EVIDENCE+'PC-RESULT.json'}
        self.assertTrue(required<=set(self.files),required-set(self.files))
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()),{'payload.tar.gz','serial_commands.txt','copy_serial_step.ps1','三维接合步骤.txt','CONTENTS.txt'})
            self.assertEqual(archive.read('payload.tar.gz'),self.payload)
            self.assertEqual(archive.read('serial_commands.txt').decode('ascii').splitlines(),self.lines)
        with tarfile.open(fileobj=io.BytesIO(self.payload),mode='r:gz') as archive:
            members=archive.getmembers()
            for member in members:
                self.assertTrue(member.isfile()); self.assertFalse(Path(member.name).is_absolute())
                self.assertNotIn('..',Path(member.name).parts)
                self.assertNotIn(Path(member.name).suffix.lower(),('.dll','.so','.elf','.bit','.hwh','.pyc'))
            self.assertEqual({m.name for m in members},set(self.files)|{'PACKAGE.txt'})
        self.assertGreater(len('\n'.join(self.lines).encode('ascii')),32768,'fixture must exercise the Windows argument limit via stdin')
        for line in self.lines:
            self.assertLess(len(line.encode('ascii')),3800)
            self.assertNotIn('\n',line); self.assertNotIn('\r',line)
    def test_serial_stdin_roundtrip_and_chunk_retry(self):
        chunk=next(line for line in self.lines if line.startswith("printf '%s' '"))
        commands=list(self.lines); commands.insert(commands.index(chunk)+1,chunk)
        run,stage,dest=self.shell(commands,'round trip')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('PAYLOAD_3D_OK',run.stdout); self.assertIn('UNPACK_3D_OK',run.stdout)
        self.assertEqual((stage/'payload.tar.gz').read_bytes(),self.payload)
        for name,data in self.files.items(): self.assertEqual((dest/name).read_bytes(),data,name)
        self.assertTrue((dest/'PACKAGE.txt').is_file())
    def test_serial_missing_or_corrupt_chunk_rejects_extraction(self):
        chunk=next(line for line in self.lines if line.startswith("printf '%s' '"))
        for mode in ('missing','corrupt'):
            commands=list(self.lines)
            if mode=='missing': commands.remove(chunk)
            else:
                encoded=chunk.split("'")[3]
                altered=('A' if encoded[0]!='A' else 'B')+encoded[1:]
                commands[commands.index(chunk)]=chunk.replace(encoded,altered,1)
            with self.subTest(mode=mode):
                run,stage,dest=self.shell(commands,mode)
                self.assertNotEqual(run.returncode,0)
                self.assertNotIn('UNPACK_3D_OK',run.stdout); self.assertFalse(dest.exists())
    def test_serial_existing_destination_is_preserved(self):
        run,stage,dest=self.shell(self.lines,'existing')
        self.assertEqual(run.returncode,0,run.stderr)
        marker=dest/'keep.txt'; marker.write_bytes(b'original')
        before={p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}
        commands=['ss3_stage='+shlex.quote(shell_path(stage)),
                  'ss3_dest='+shlex.quote(shell_path(dest)),self.lines[-1]]
        run=subprocess.run([self.bash,'--noprofile','--norc','-s'],input='\n'.join(commands)+'\n',
                           capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertNotEqual(run.returncode,0); self.assertIn('DEST_EXISTS',run.stdout)
        after={p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}
        self.assertEqual(after,before)
    def test_space_path_extract_build_and_offline_entrypoints(self):
        destination=self.root/'extract compile with spaces'; destination.mkdir()
        with tarfile.open(fileobj=io.BytesIO(self.payload),mode='r:gz') as archive:
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertFalse(Path(member.name).is_absolute())
                self.assertNotIn('..',Path(member.name).parts)
            archive.extractall(destination)  # checked regular relative files; Python 3.8 compatible
        for name in ('run_buffered_3d.py','run_smp_3d.py','replay_capture_3d.py'):
            run=subprocess.run(PYTHON+[str(destination/'software/tetra3d/linux'/name),'--help'],cwd=destination,
                               capture_output=True,text=True,encoding='utf-8',timeout=20)
            self.assertEqual(run.returncode,0,run.stderr); self.assertIn('--geometry',run.stdout)
        env=dict(os.environ,CC=shell_path(self.cc))
        script='set -e\ncd '+shlex.quote(shell_path(destination))+'\nsh software/tetra3d/linux/build_solver_3d.sh\n'
        build=subprocess.run([self.bash,'--noprofile','--norc','-s'],input=script,env=env,
                             capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
        self.assertEqual(build.returncode,0,build.stdout+build.stderr)
        library=destination/'software/tetra3d/linux/libss_solver_3d.so'
        self.assertTrue(library.is_file())
        out=destination/'replay result.jsonl'
        command=PYTHON+[str(destination/'software/tetra3d/linux/replay_capture_3d.py'),
                '--geometry',str(destination/'software/tetra3d/core/tetra40-nominal.json'),
                '--input',str(destination/(package.EVIDENCE+'EXAMPLE-FRAMES.jsonl')),'--output',str(out)]
        run=subprocess.run(command,cwd=destination,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('frames=6',run.stdout); self.assertIn('UNOBSERVABLE',run.stdout)
        # The shipped final frame has mask_count=11: minimum-pair rejection.
        self.assertIn('REJECTED reason=1',run.stdout)
        import json
        rows=[json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows),6)
        self.assertTrue(all((rows[-1]['frame']['words'][5*i]>>16)&127==11 for i in range(6)))
        self.assertEqual(rows[-1]['result']['reason'],1)
        self.assertTrue(all(r['geometry_binding']=='EXPLICIT_RECOMPUTE' and r['motion']=='DISABLED' for r in rows))
        before=out.read_bytes()
        repeated=subprocess.run(command,cwd=destination,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertNotEqual(repeated.returncode,0); self.assertEqual(out.read_bytes(),before)
    def test_canary_bad_archive_cannot_claim_transport_success(self):
        corrupt=bytearray(self.payload); corrupt[len(corrupt)//2]^=1
        run,stage,dest=self.shell(package.commands_for(bytes(corrupt)),'negative canary')
        self.assertNotEqual(run.returncode,0); self.assertFalse(dest.exists())
        self.assertNotIn('UNPACK_3D_OK',run.stdout)


if __name__=='__main__': unittest.main(verbosity=2)