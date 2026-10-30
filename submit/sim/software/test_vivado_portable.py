"""Offline checks for the portable source kit; native Vivado evidence is separate."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
import shutil

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('kit', ROOT/'tools/package_vivado_ps_3d.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class PortableKitTests(unittest.TestCase):
    def test_complete_payload_no_machine_paths(self):
        files = kit.payload()
        self.assertEqual(len(files), 50)
        self.assertEqual(sum(n.endswith(('.v', '.sv')) for n in files), 31)
        self.assertEqual(sum(n.endswith('.mem') for n in files), 1)
        self.assertNotIn('tools.local.env', files)
        self.assertFalse(any(n.endswith(('.dcp', '.xpr', '.log')) for n in files))

    def test_missing_dependency_and_absolute_path_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, data in kit.payload().items():
                p = root/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            missing = root/'project/rtl/hann-u18f17.mem'
            original = missing.read_bytes()
            missing.unlink()
            with self.assertRaises(FileNotFoundError): kit.payload(root)
            missing.write_bytes(original)
            p = root/'project/script/rebuild_ps_3d.tcl'
            with p.open('a') as stream: stream.write('\n# '+chr(81)+':/private/source.v\n')
            with self.assertRaises(ValueError): kit.payload(root)

    def test_no_automatic_runs_or_hardware_commands(self):
        script = (ROOT/'project/script/rebuild_ps_3d.tcl').read_text('utf-8')
        for command in ('launch_runs', 'synth_design', 'open_hw_manager', 'program_hw_devices'):
            self.assertNotIn(command, script)
        self.assertIn('import_files', script)
        self.assertIn('IS_ENABLED 0', script)


if __name__ == '__main__': unittest.main()
