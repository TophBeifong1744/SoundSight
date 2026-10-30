"""启动入口离线验证：模型记录下载/寄存器副作用；不导入真实PYNQ。"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ps'))
import board_tools as app
import ps_client as hw


class SLCR:
    def __init__(self, fclk=0x300600):
        self.values = {0x108: 0x30000, 0x170: fclk, 0x240: 0}
        self.writes = []
    def read(self, offset): return self.values[offset]
    def write(self, offset, value): self.writes.append((offset, value))


class IP:
    def __init__(self, status=0x34000, fault=0x40, sys=8, permit=0):
        self.values = {hw.MAGIC: 0x5a5a2026, hw.ABI: 0x10001,
                       hw.STATUS: status, hw.FAULT: fault, hw.DROP: 0,
                       hw.SYS: sys, hw.ACT: permit}
    def read(self, offset): return self.values[offset]
    def write(self, *args): raise AssertionError('Device registers must not be written by prepare/status')


class Overlay:
    def __init__(self, slcr, loaded=False, other=False, fail=False):
        self.slcr = slcr; self.loaded = loaded; self.downloads = 0; self.fail = fail
        self.device = SimpleNamespace(bitfile_name='other.bit' if other else 'soundsight.bit' if loaded else '')
        self.clock_dict = {0: dict(enable=1, divisor0=6, divisor1=3)}
    def is_loaded(self): return self.loaded
    def download(self):
        self.downloads += 1
        self.loaded = not self.fail
        self.slcr.values[0x170] = 0x400400


class BoardToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.slcr = SLCR()
        self.clocks = SimpleNamespace(_instance=SimpleNamespace(_ref_clk_mhz=50), fclk0_mhz=99.999999)
        self.ip = IP()
        self.mmio_reads = []

    def tearDown(self): self.temp.cleanup()

    def mmio(self, base, size):
        self.mmio_reads.append((base, size))
        return self.ip

    def prepare(self, overlay, reference=33.333333):
        return app.prepare_hardware(overlay, self.slcr, self.clocks, self.mmio,
                                    reference, 0x40000000, 4096)

    def test_initial_prepare_loads_then_checks_expected_clock_and_abi(self):
        overlay = Overlay(self.slcr)
        state = self.prepare(overlay)
        self.assertEqual(overlay.downloads, 1)
        self.assertEqual(self.slcr.writes, [(8, 0xdf0d)])
        self.assertEqual(overlay.clock_dict[0], dict(enable=1, divisor0=4, divisor1=4))
        self.assertEqual(self.clocks._instance._ref_clk_mhz, 33.333333)
        self.assertEqual(state['fault'], 64)  # 检查不自动清STOP标记。
        self.assertEqual(self.mmio_reads, [(0x40000000, 4096)])

    def test_repeat_prepare_never_redownloads_or_resets(self):
        self.slcr.values[0x170] = 0x400400
        overlay = Overlay(self.slcr, loaded=True)
        self.prepare(overlay)
        self.assertEqual(overlay.downloads, 0)
        self.assertEqual(self.slcr.writes, [])

    def test_old_slots_preserved_and_drain_instruction(self):
        self.slcr.values[0x170] = 0x400400
        self.ip.values[hw.STATUS] |= 3
        overlay = Overlay(self.slcr, loaded=True)
        with self.assertRaisesRegex(RuntimeError, 'OLD_FRAMES.*drain'): self.prepare(overlay)
        self.assertEqual(overlay.downloads, 0)
        self.assertEqual(self.ip.values[hw.STATUS] & 3, 3)

    def test_faults_other_than_stop_are_not_cleared(self):
        self.ip.values[hw.FAULT] = 0x48
        with self.assertRaisesRegex(RuntimeError, 'DEVICE_FAULT=0x48'):
            self.prepare(Overlay(self.slcr))
        self.assertEqual(self.ip.values[hw.FAULT], 0x48)

    def test_bad_clock_reference_pll_or_source_stops_before_download_and_pl_read(self):
        for offset, value, reference in [(0x108, 0, 33.333333), (0x170, 0x20, 33.333333), (0x108, 0x30000, 50)]:
            self.slcr = SLCR(); self.slcr.values[offset] = value
            overlay = Overlay(self.slcr)
            with self.assertRaises(RuntimeError): self.prepare(overlay, reference)
            self.assertEqual(overlay.downloads, 0)
            self.assertEqual(self.slcr.writes, [])
        self.assertEqual(self.mmio_reads, [])

    def test_loaded_wrong_clock_or_reset_does_not_read_pl(self):
        overlay = Overlay(self.slcr, loaded=True)
        with self.assertRaisesRegex(RuntimeError, 'FCLK0'): self.prepare(overlay)
        self.slcr.values[0x170] = 0x400400; self.slcr.values[0x240] = 3
        with self.assertRaisesRegex(RuntimeError, 'reset'): self.prepare(overlay)
        self.assertEqual(self.mmio_reads, [])

    def test_unknown_overlay_and_failed_download_do_not_touch_pl(self):
        other = Overlay(self.slcr, other=True)
        with self.assertRaisesRegex(RuntimeError, 'Another overlay'): self.prepare(other)
        self.assertEqual(other.downloads, 0)
        with self.assertRaisesRegex(RuntimeError, 'not confirmed'): self.prepare(Overlay(self.slcr, fail=True))
        self.assertEqual(self.mmio_reads, [])

    def test_active_device_refuses_ready(self):
        self.ip.values[hw.SYS] = 9
        with self.assertRaisesRegex(RuntimeError, 'DEVICE_ACTIVE'): app.require_idle(app.device_state(self.ip))
        self.ip.values[hw.SYS] = 8; self.ip.values[hw.ACT] = 1
        with self.assertRaisesRegex(RuntimeError, 'DEVICE_ACTIVE'): app.require_idle(app.device_state(self.ip))

    def test_wrong_id_abi_or_capability(self):
        for address, value in [(hw.MAGIC, 0), (hw.ABI, 0x10000), (hw.STATUS, 0)]:
            ip = IP(); ip.values[address] = value
            with self.assertRaises(RuntimeError): app.device_state(ip)

    def test_level_save_show_and_bounds(self):
        self.assertEqual(app.get_level(self.root), 7000)
        app.set_level(4300, self.root)
        self.assertEqual(app.get_level(self.root), 4300)
        for value in (0, -1, 0x1000000):
            with self.assertRaises(ValueError): app.set_level(value, self.root)
        self.assertEqual(app.get_level(self.root), 4300)

    def test_corrupt_settings_fail_instead_of_silent_fallback(self):
        (self.root/app.SETTINGS).write_text('{"min_level":true}')
        with self.assertRaises(ValueError): app.get_level(self.root)

    def test_run_defaults_override_and_unique_paths(self):
        app.set_level(4500, self.root)
        args = SimpleNamespace(operation='normal', frames=None, mode='real', min_level=None)
        command, out, level = app.run_arguments(args, self.root)
        self.assertEqual(level, 4500)
        self.assertEqual(command[command.index('--frames')+1], '0')
        self.assertEqual(command[command.index('--clear-faults')+1], '0x40')
        self.assertEqual(out.parent, self.root/'logs')
        args.operation = 'debug'; args.min_level = 6000
        second, out2, level2 = app.run_arguments(args, self.root)
        self.assertEqual(level2, 6000)
        self.assertEqual(app.get_level(self.root), 4500)
        self.assertEqual(second[second.index('--frames')+1], '1000')
        self.assertIn('--angle-filter', second)
        self.assertNotEqual(out, out2)
        self.assertNotIn('--horizontal-motion', command+second)

    def test_invalid_run_and_bist_frame_counts(self):
        args = SimpleNamespace(operation='normal', frames=None, mode='bist-pass', min_level=7000)
        command, _, _ = app.run_arguments(args, self.root)
        self.assertEqual(command[command.index('--frames')+1], '1')
        for op, mode, count in [('debug','real',0), ('normal','real',-1), ('normal','bist-pass',10)]:
            args.operation, args.mode, args.frames = op, mode, count
            with self.assertRaises(ValueError): app.run_arguments(args, self.root)

    def test_hwh_rejects_non_volume_or_incomplete_actuator_configuration(self):
        (self.root/'soundsight.bit').write_bytes(b'fixture')
        xml = '''<ROOT><MODULE INSTANCE="compute" MODTYPE="bd_clean_compute"><PARAMETER NAME="LEVEL_ENABLE" VALUE="1"/></MODULE><MODULE INSTANCE="ps_link" MODTYPE="bd_ps_link"><PARAMETER NAME="LEVEL_ENABLE" VALUE="1"/><PARAMETER NAME="ACTUATOR_BOUND" VALUE="0"/></MODULE><MEMRANGE INSTANCE="ps_link" SLAVEBUSINTERFACE="S_AXI" MEMTYPE="REGISTER" BASEVALUE="0x40000000" HIGHVALUE="0x40000fff"/></ROOT>'''
        path = self.root/'soundsight.hwh'; path.write_text(xml)
        self.assertEqual(app.hwh_check(self.root), (0x40000000,4096))
        path.write_text(xml.replace('NAME="ACTUATOR_BOUND" VALUE="0"','NAME="ACTUATOR_BOUND" VALUE="1"'))
        with self.assertRaisesRegex(RuntimeError,'ACTUATOR_BOUND'): app.hwh_check(self.root)
        path.write_text(xml.replace('NAME="LEVEL_ENABLE" VALUE="1"','NAME="LEVEL_ENABLE" VALUE="0"'))
        with self.assertRaisesRegex(RuntimeError,'LEVEL_ENABLE'): app.hwh_check(self.root)

    def test_prepare_cli_failure_never_reports_ready(self):
        text = io.StringIO()
        with patch.object(app.os,'geteuid',return_value=0,create=True), \
             patch.object(app.platform,'machine',return_value='armv7l'), \
             patch.object(app,'validate_cpus'), patch.object(app,'single_owner',return_value=contextlib.nullcontext()), \
             patch.object(app,'hwh_check',return_value=(0x40000000,4096)), patch.object(app,'get_level',return_value=7000), \
             patch.object(app,'offline_checks',side_effect=RuntimeError('test failed')), \
             patch.object(app,'load_api') as load, contextlib.redirect_stdout(text), contextlib.redirect_stderr(text):
            self.assertEqual(app.main(['prepare']),1)
            load.assert_not_called()
        self.assertNotIn('READY_FOR_DEBUG',text.getvalue())
        self.assertIn('test failed',text.getvalue())


if __name__ == '__main__': unittest.main()
