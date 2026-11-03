"""Quick boot keeps native ABI and hardware guards; synthetic dependencies only."""
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'software/ps'), str(ROOT/'software/tetra3d/linux'),
               str(ROOT/'software/screen')]
import board_tools
import board_3d
import product


class QuickBootTests(unittest.TestCase):
    def test_quick_checks_both_native_libraries_without_subprocess(self):
        with patch.object(board_tools,'Solver') as old, patch.object(board_3d,'Solver3D') as new, \
                patch.object(board_3d.subprocess,'run') as run:
            board_3d.quick_libraries(ROOT)
            old.assert_called_once(); new.assert_called_once(); run.assert_not_called()

    def test_bad_native_library_fails_before_hardware(self):
        for name in ('Solver','Solver3D'):
            with patch.object(board_3d,'check_hwh'), patch.object(board_tools,'Solver') as old, \
                    patch.object(board_3d,'Solver3D') as new, patch.object(board_tools,'main') as prepare:
                (old if name=='Solver' else new).side_effect=OSError('wrong ELF')
                self.assertNotEqual(board_3d.main(['prepare','--quick']),0)
                prepare.assert_not_called()

    def test_quick_and_full_dispatch_keep_legacy_failure(self):
        for quick in (True,False):
            with patch.object(board_3d,'check_hwh'), patch.object(board_3d,'quick_libraries') as fast, \
                    patch.object(board_3d,'offline') as full, patch.object(board_tools,'main',return_value=1) as prepare:
                self.assertEqual(board_3d.main(['prepare']+(['--quick'] if quick else [])),1)
                prepare.assert_called_once_with(['prepare']+(['--quick'] if quick else []))
                self.assertEqual(fast.call_count,int(quick));self.assertEqual(full.call_count,int(not quick))

    def legacy(self, failure=None, bad_library=False):
        # Host model only. Existing board_tools tests separately exercise real
        # guards with fake MMIO/clock/overlay objects, not bypassed callbacks.
        with contextlib.ExitStack() as stack:
            def mock(obj,name,**kw):return stack.enter_context(patch.object(obj,name,**kw))
            mock(board_tools.os,'geteuid',return_value=0,create=True)
            mock(board_tools.platform,'machine',return_value='armv7l')
            mock(board_tools,'validate_cpus')
            mock(board_tools,'single_owner',return_value=contextlib.nullcontext())
            mock(board_tools,'hwh_check',return_value=(0x40000000,4096))
            mock(board_tools,'get_level',return_value=7000)
            mock(board_tools,'offline_checks',side_effect=AssertionError('No full regression during quick boot'))
            lib=mock(board_tools,'Solver',side_effect=OSError('missing library') if bad_library else None)
            load=mock(board_tools,'load_api',return_value=(1,2,3,4,5))
            hardware=mock(board_tools,'prepare_hardware',side_effect=failure)
            # Only used to select the printed NEXT command after successful init.
            mock(board_tools.ET,'parse',return_value=board_tools.ET.ElementTree(board_tools.ET.Element('ROOT')))
            result=board_tools.main(['prepare','--quick'])
            lib.assert_called_once()
            if bad_library:load.assert_not_called();hardware.assert_not_called()
            else:hardware.assert_called_once_with(1,2,3,4,5,0x40000000,4096)
            return result

    def test_quick_keeps_hardware_preparation(self):
        self.assertEqual(self.legacy(),0)

    def test_quick_propagates_hardware_fault_no_ready(self):
        self.assertEqual(self.legacy(RuntimeError('OLD_FRAMES: preserve')),1)

    def test_quick_missing_library_never_loads_overlay(self):
        self.assertEqual(self.legacy(bad_library=True),1)

    def test_first_boot_timings_survive_later_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'logs/product/latest.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(boot_started_monotonic=20,events=[])))
            with patch.object(product.time,'monotonic',return_value=27):
                product.update_journal(root,'DISPLAY_LIT')
            with patch.object(product.time,'monotonic',return_value=28):
                product.update_journal(root,'READY')
            with patch.object(product.time,'monotonic',return_value=900):
                product.update_journal(root,'READY')
            d=json.loads(p.read_text())['startup_timing']
            self.assertEqual(d['display_lit_since_service_seconds'],7)
            self.assertEqual(d['ready_since_service_seconds'],8)
            self.assertEqual(d['ready_uptime_seconds'],28)


if __name__=='__main__':unittest.main(verbosity=2)
