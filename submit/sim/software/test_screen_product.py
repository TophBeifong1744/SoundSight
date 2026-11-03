"""P1 lifecycle, touch UI and installer transactions; synthetic files, no hardware."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy  # Load once before tests temporarily replace sys.modules entries.
from unittest.mock import Mock, patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'software/screen'), str(ROOT/'tools')]
import backend
import ui
import product
import hardware
import linux_i2c
import screen_i2c_prepare
import install_product as installer

IDLE = dict(status=983040, fault=64, drops=3, sys=8, actuator=0, dual_axis=0)


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.b = backend.Backend(self.root, control=True, motion=True)
        self.u = ui.UI(self.b, product=True)

    def finish(self, operation='verify-stop', rows=None, code=0):
        self.b.proc = Mock()
        self.b.proc.poll.return_value = code
        self.b.operation = operation
        self.b.status_rows = [IDLE.copy()] if rows is None else rows
        self.b.device_state = self.b.status_rows[0] if self.b.status_rows else None
        with patch.object(backend.os, 'read', return_value=b''), patch.object(self.b, '_group_alive', return_value=False):
            self.b.tick()

    def test_direction_window_and_raw_reason_are_separate_from_permit(self):
        self.b.state = 'STARTING'
        self.b.operation = 'SPEAKER'
        self.b.accept_line('FRAME=10 LEVEL=20000 NO_OUTPUT: COLLECTING_WINDOW '
            'WINDOW=3/5 VALID=1 MIN=2 RAW_REASON=NORM RAW_PAIRS=6 AXES=3 MOTION=NO_FRESH_VALID_DIRECTION '
            'SPEAKER_SCORE=0.55 PERMIT=1 REMAIN=4s POLICY=score_ttl_v2')
        live = self.b.live()
        self.assertEqual(live['angle_reason'], 'COLLECTING_WINDOW')
        self.assertEqual((live['window'], live['valid'], live['minimum']), ('3/5', '1', '2'))
        self.assertEqual(live['raw_reason'], 'NORM')
        self.assertTrue(live['permit'])
        self.assertIsNone(live['azimuth'])
        self.u.mode = 'SPEAKER'
        self.assertEqual(self.u.render().size, (800, 480))

    def test_boot_restores_mode_but_never_axes_or_running(self):
        product.save_mode(self.root, 'SPEAKER')
        u = ui.UI(self.b, product=True)
        self.assertEqual((u.mode, u.axes, self.b.state), ('SPEAKER', 'off', 'IDLE'))
        self.assertFalse(self.b.busy)

    def test_mode_change_persists_and_clears_axes(self):
        self.u.axes = 'both'; self.u.action('MODE')
        self.assertEqual(self.u.axes, 'off')
        self.assertEqual(product.load_preferences(self.root), 'SPEAKER')

    def test_invalid_configuration_blocks_start_but_renders(self):
        (self.root/'settings.local.json').write_text('{bad')
        b = backend.Backend(self.root, control=True, motion=True)
        self.assertEqual(b.state, 'ERROR')
        with self.assertRaises(RuntimeError):
            b.start('SOUND', 'off')
        self.assertEqual(ui.UI(b).render().size, (800, 480))

    def test_corrupt_mode_never_silently_starts(self):
        (self.root/'screen.local.json').write_text('{bad')
        u = ui.UI(self.b, product=True)
        self.assertEqual(self.b.state, 'ERROR')
        self.assertEqual(u.axes, 'off')

    def test_modes_map_to_distinct_cli(self):
        with patch.object(self.b, '_launch') as launch:
            self.b.start('SOUND', 'both')
            self.assertEqual(launch.call_args.args[0][0], 'follow-sound')
            self.b.start('SPEAKER', 'both')
            self.assertEqual(launch.call_args.args[0][0], 'speaker')

    def test_motion_requires_explicit_permission(self):
        b = backend.Backend(self.root, control=True)
        with self.assertRaises(RuntimeError):
            b.start('SOUND', 'both')

    def test_startup_video_does_not_touch_unowned_reset_or_int(self):
        mmio = Mock()
        mmio.read.side_effect = [7, 3, 3]  # RST/INT high, BL high; RST/INT inputs.
        gpio = hardware.ScreenGPIO(mmio, touch_owned=False)
        self.assertEqual(gpio.output & 3, 3)
        self.assertEqual(gpio.direction & 3, 3)
        writes = [c.args for c in mmio.write.call_args_list]
        self.assertEqual(writes, [(0, 3), (4, 3)])

    def test_enrollment_dialog_unique_name_and_cancel(self):
        (self.root/'speaker-profiles/USER1').mkdir(parents=True)
        self.u.action('ENROLL')
        self.assertEqual(self.u.enroll_name, 'user2')
        self.u.action('START')
        self.assertFalse(self.b.busy)
        self.u.action('CANCEL')
        self.assertIsNone(self.u.modal)

    def test_enrollment_uses_existing_cli_no_select_or_motion(self):
        with patch.object(self.b, '_launch') as launch:
            self.u.action('ENROLL'); self.u.action('RECORD')
            launch.assert_called_once_with(['speaker-enroll', 'user1', '--seconds', '5'], 'ENROLL')
            self.assertEqual(self.u.axes, 'off')
            self.assertIsNone(self.b.cache['target'])

    def test_enrollment_race_preserves_existing_profile(self):
        self.u.action('ENROLL')
        (self.root/'speaker-profiles/user1').mkdir(parents=True)
        self.u.action('RECORD')
        self.assertIn('changed', self.u.message)
        self.assertFalse(self.b.busy)

    def test_enrollment_progress_and_target_unchanged(self):
        self.b.operation = 'ENROLL'
        self.b.accept_line('READY_IN=2'); self.assertIn('2', self.b.note)
        self.b.accept_line('RECORD_NOW: speak'); self.assertIn('SPEAK NOW', self.b.note)
        self.b.accept_line('RECORDING_DONE PROCESSING=1'); self.assertIn('Processing', self.b.note)
        self.b.accept_line('ENROLLED=user1 ACTIVE_TARGET_UNCHANGED=1')
        self.assertEqual(self.b.last_enrolled, 'user1')
        self.assertIsNone(self.b.cache['target'])

    def test_enrollment_exit_always_verifies_stop(self):
        with patch.object(self.b, '_verify_stop') as verify:
            self.finish('ENROLL')
            verify.assert_called_once()

    def test_enrollment_duration_bounds(self):
        self.u.action('ENROLL')
        for _ in range(20): self.u.action('LONGER')
        self.assertEqual(self.u.enroll_seconds, 10)
        for _ in range(20): self.u.action('SHORTER')
        self.assertEqual(self.u.enroll_seconds, 2)

    def test_settings_use_original_validating_cli(self):
        with patch.object(self.b, 'command') as command:
            self.u.draft['level'] = 12500
            self.u.action('APPLY'); command.assert_called_with('level', 12500)
            self.u.setting_index = 3; self.u.draft['threshold'] = .45
            self.u.action('APPLY'); command.assert_called_with('speaker-config', .45)

    def test_touch_press_does_not_repeat_start(self):
        self.u.buttons = [((0, 0, 100, 100), 'START')]
        with patch.object(self.b, 'start') as start:
            self.u.touch([(20, 20)]); self.u.touch([(20, 20)])
            start.assert_called_once()

    def test_multitouch_never_starts(self):
        self.u.buttons = [((0, 0, 100, 100), 'START')]
        with patch.object(self.b, 'start') as start:
            self.u.touch([(20, 20), (30, 30)])
            start.assert_not_called()

    def test_fault_requires_explicit_recovery_and_fresh_idle(self):
        self.b.fault('touch failure')
        with self.assertRaises(RuntimeError): self.b.start('SOUND', 'off')
        self.b.recovery_requested = True
        self.finish(rows=[dict(IDLE, sys=9)])
        self.assertEqual(self.b.state, 'ERROR')
        self.b.recovery_requested = True
        self.finish()
        self.assertEqual(self.b.state, 'IDLE')
        self.assertFalse(self.b.session_failed)
        self.assertFalse(self.b.busy)

    def test_duplicate_status_cannot_confirm_stop(self):
        self.finish(rows=[IDLE, IDLE])
        self.assertFalse(self.b.stop_verified)

    def test_error_latched_without_explicit_recovery(self):
        self.b.fault('runtime error'); self.finish()
        self.assertEqual(self.b.state, 'ERROR')

    def test_shutdown_requires_confirmation_and_fresh_readback(self):
        self.u.action('POWER')
        self.assertFalse(self.u.shutdown_pending)
        self.u.action('POWER_CONFIRM')
        self.assertFalse(self.u.poweroff_ready)
        with patch.object(self.b, '_verify_stop') as verify:
            self.u.tick(); verify.assert_called_once()
        self.finish()
        self.assertTrue(self.u.poweroff_ready)

    def test_shutdown_unconfirmed_device_stays_blocked(self):
        self.u.shutdown_pending = self.u.shutdown_checked = True
        self.finish(rows=[dict(IDLE, actuator=1)])
        self.assertFalse(self.u.poweroff_ready)

    def test_stop_cancels_shutdown_and_modal(self):
        self.u.shutdown_pending = True; self.u.modal = 'POWER'
        self.u.action('STOP')
        self.assertFalse(self.u.shutdown_pending)
        self.assertIsNone(self.u.modal)

    def test_modal_pages_render_and_stop_remains_visible(self):
        for page in ('HOME', 'USERS', 'SETTINGS', 'DIAGNOSTICS'):
            self.u.page = page
            self.assertEqual(self.u.render().size, (800, 480))
            self.assertIn('STOP', [a for _,a in self.u.buttons])
        for modal in ('POWER', 'ENROLL'):
            self.u.modal = modal; self.u.enroll_name = 'user1'
            self.u.render()
            self.assertIn('STOP', [a for _,a in self.u.buttons])

    def test_restart_records_only_real_new_boot_and_persistence(self):
        product.save_mode(self.root, 'SPEAKER')
        first = product.Journal(self.root, 'boot-one')
        first.stage('SHUTDOWN_REQUESTED', settings_at_shutdown=product.fingerprints(self.root))
        second = product.Journal(self.root, 'boot-two')
        self.assertTrue(second.value['new_boot'])
        self.assertTrue(second.value['settings_preserved'])
        self.assertNotIn('passed', second.value)

    def test_changed_config_is_not_reported_preserved(self):
        product.save_mode(self.root, 'SOUND')
        j = product.Journal(self.root, 'one')
        j.stage('SHUTDOWN_REQUESTED', settings_at_shutdown=product.fingerprints(self.root))
        product.save_mode(self.root, 'SPEAKER')
        j = product.Journal(self.root, 'two')
        self.assertFalse(j.value['settings_preserved'])

    def test_poweroff_failure_is_recorded_and_not_claimed_success(self):
        runner = Mock(return_value=SimpleNamespace(returncode=1, stderr='denied'))
        with self.assertRaises(RuntimeError): product.poweroff(self.root, runner)
        self.assertEqual(json.loads((self.root/'logs/product/latest.json').read_text())['stage'], 'SHUTDOWN_FAILED')
        self.assertEqual(runner.call_args.args[0], ['systemctl', 'poweroff', '--no-block'])

    def test_damaged_previous_journal_preserved_without_blocking_boot(self):
        p = self.root/'logs/product/latest.json'; p.parent.mkdir(parents=True)
        p.write_text('{bad')
        j = product.Journal(self.root, 'fresh')
        self.assertIn('previous_journal_error', j.value)
        self.assertEqual(len(list(p.parent.glob('damaged-*.json'))), 1)

    def test_installed_product_checksum_is_checked(self):
        p = self.root/'code.py'; p.write_bytes(b'good')
        (self.root/'PRODUCT-INSTALL.json').write_text(json.dumps(dict(
            revision=product.REVISION, files={'code.py':installer.digest(b'good')})))
        product.verify_product(self.root)
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs'): product.verify_product(self.root)

    def test_boot_order_and_owner_descriptor_handoff(self):
        p = self.root/'code.py'; p.write_bytes(b'x')
        (self.root/'PRODUCT-INSTALL.json').write_text(json.dumps(dict(
            revision=product.REVISION, files={'code.py':installer.digest(b'x')})))
        events = []
        fake_fcntl = SimpleNamespace(flock=lambda *a: events.append('lock'), LOCK_EX=2, LOCK_NB=4)
        owner = tempfile.TemporaryFile('a+')
        journal = product.Journal(self.root, 'test-boot')
        class ExecReached(Exception): pass
        with patch.dict(sys.modules, fcntl=fake_fcntl), \
             patch.object(product, 'open', return_value=owner, create=True), \
             patch.object(product, 'Journal', return_value=journal), \
             patch.object(product.signal, 'signal'), \
             patch.object(hardware, 'verify_install', side_effect=lambda r: events.append('receipt')), \
             patch.object(product, 'run_stage', side_effect=lambda *a: events.append('prepare')) as prepare, \
             patch.object(hardware, 'open_overlay', side_effect=lambda r: events.append('inspect')), \
             patch.object(screen_i2c_prepare, 'apply_overlay', side_effect=lambda r: events.append('i2c')), \
             patch.object(product.os, 'execv', side_effect=ExecReached) as execute:
            with self.assertRaises(ExecReached): product.boot(self.root)
            args = execute.call_args.args[1]
            self.assertIn('--owner-fd', args)
            self.assertIn('--product', args)
            self.assertNotIn('--startup-error', args)
            self.assertEqual(prepare.call_args.args[0][-2:], ['prepare', '--quick'])
        self.assertEqual(events, ['lock', 'receipt', 'prepare', 'inspect', 'i2c'])
        self.assertTrue(owner.closed)

    def test_boot_timeout_interrupts_without_killing_or_continuing(self):
        child = Mock(pid=123, returncode=0)
        child.poll.side_effect = [None, None, 0]
        with patch.object(product.subprocess, 'Popen', return_value=child), \
             patch.object(product.time, 'monotonic', side_effect=[0, .01, 1]), \
             patch.object(product.time, 'sleep'), \
             patch.object(product.os, 'killpg', create=True) as signal_group:
            with self.assertRaises(RuntimeError):
                product.run_stage(['fake-prepare'], self.root, [False], timeout=.1)
            signal_group.assert_called_once_with(123, product.signal.SIGINT)

    def test_touch_failure_main_loop_stops_and_keeps_fault_frame(self):
        fake_os = SimpleNamespace(**dict(vars(os), name='posix'))
        fake_fcntl = SimpleNamespace(flock=Mock(), LOCK_EX=2, LOCK_NB=4, LOCK_UN=8)
        owner = tempfile.TemporaryFile('a+')
        display = Mock(active=0)
        display.close.return_value = True
        gpio = Mock(); gpio.locked.return_value = True
        touch = Mock(); touch.probe.return_value = 'test touch'
        touch.poll.side_effect = OSError('injected I2C error')
        with patch.dict(sys.modules, fcntl=fake_fcntl), \
             patch.object(ui, 'os', fake_os), \
             patch.object(ui, 'open', return_value=owner, create=True), \
             patch.object(ui.signal, 'signal'), \
             patch.object(ui, 'Backend', return_value=self.b), \
             patch.object(hardware, 'open_overlay', return_value=(None, Mock(), Mock(), Mock())), \
             patch.object(hardware, 'ScreenGPIO', return_value=gpio), \
             patch.object(hardware, 'Display', return_value=display), \
             patch.object(hardware, 'Touch', return_value=touch), \
             patch.object(linux_i2c, 'LinuxI2C', return_value=Mock()), \
             patch.object(backend.subprocess, 'Popen') as launch:
            result = ui.main(['--root', str(self.root), '--control', '--enable-motion', '--seconds', '.4'])
        self.assertEqual(result, 1)
        self.assertTrue(self.b.session_failed)
        self.assertIn('injected I2C error', self.b.external_fault)
        self.assertGreaterEqual(display.present.call_count, 2)
        launch.assert_not_called()
        display.close.assert_called_once()

    def test_poweroff_main_loop_requires_display_halt_before_os_request(self):
        for halt in (True, False):
            with self.subTest(display_halted=halt):
                b = backend.Backend(self.root, control=True, motion=True)
                b.operation, b.device_state = 'verify-stop', IDLE.copy()
                u = ui.UI(b, product=True)
                u.shutdown_pending = u.shutdown_checked = True
                display = Mock(active=0)
                display.close.side_effect = [halt, True]
                gpio = Mock(); gpio.locked.return_value = True
                touch = Mock(); touch.probe.return_value = 'test'; touch.poll.return_value = []
                owner = tempfile.TemporaryFile('a+')
                events = []
                def close():
                    events.append('display_stop')
                    return halt if events.count('display_stop') == 1 else True
                display.close.side_effect = close
                fake_fcntl = SimpleNamespace(flock=Mock(), LOCK_EX=2, LOCK_NB=4, LOCK_UN=8)
                with patch.dict(sys.modules, fcntl=fake_fcntl), \
                     patch.object(ui, 'os', SimpleNamespace(**dict(vars(os), name='posix'))), \
                     patch.object(ui, 'open', return_value=owner, create=True), \
                     patch.object(ui.signal, 'signal'), \
                     patch.object(ui, 'Backend', return_value=b), patch.object(ui, 'UI', return_value=u), \
                     patch.object(hardware, 'open_overlay', return_value=(None, Mock(), Mock(), Mock())), \
                     patch.object(hardware, 'ScreenGPIO', return_value=gpio), \
                     patch.object(hardware, 'Display', return_value=display), \
                     patch.object(hardware, 'Touch', return_value=touch), \
                     patch.object(linux_i2c, 'LinuxI2C', return_value=Mock()), \
                     patch.object(product, 'verify_product'), \
                     patch.object(product, 'poweroff', side_effect=lambda r: events.append('os_poweroff')) as power:
                    result = ui.main(['--root', str(self.root), '--control', '--enable-motion', '--product', '--seconds', '.5'])
                if halt:
                    self.assertEqual(result, 0)
                    power.assert_called_once()
                    self.assertLess(events.index('display_stop'), events.index('os_poweroff'))
                else:
                    self.assertEqual(result, 1)
                    power.assert_not_called()


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'board'; self.root.mkdir()
        self.unit = self.root.parent/'units/soundsight-product.service'
        self.archive = self.root.parent/'p1.zip'
        self.old_ui = b'old UI'
        old = {'soundsight.bit':b'bit', 'soundsight.hwh':b'hwh', 'software/screen/ui.py':self.old_ui}
        for n, raw in old.items():
            p = self.root/n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
        self.receipt = dict(revision='SCREEN_PS_I2C_S2', touch_transport='PS_I2C0_EMIO_LINUX',
                            installed_boot_id='original-boot',
                            hardware={n:installer.digest(v) for n,v in old.items() if n.startswith('soundsight.')},
                            software={'software/screen/ui.py':installer.digest(self.old_ui)})
        (self.root/'SCREEN-INSTALL.json').write_text(json.dumps(self.receipt))
        self.data = {n:('test '+n).encode() for n in installer.PAYLOAD}
        self.m = dict(revision=installer.REVISION, files={n:installer.digest(v) for n,v in self.data.items()},
                      previous={'software/screen/ui.py':[installer.digest(self.old_ui)]},
                      requires={n:[installer.digest(v)] for n,v in old.items() if n.startswith('soundsight.')})
        self.calls = []
        self.pack()

    def pack(self):
        with ZipFile(self.archive, 'w') as z:
            z.writestr('__main__.py', ''); z.writestr('manifest.json', json.dumps(self.m))
            for n,v in self.data.items(): z.writestr('payload/'+n,v)

    def ctl(self, *args):
        self.calls.append(args)
        out = {'is-active':'inactive', 'is-enabled':'disabled', 'show':'loaded'}.get(args[0], '')
        return SimpleNamespace(returncode=0, stdout=out, stderr='')

    def install(self, ctl=None):
        return installer.install(self.archive, self.root, self.unit, ctl or self.ctl, '/home/xilinx/app')

    def test_install_enables_next_boot_without_start_or_hardware(self):
        r = self.install()
        self.assertFalse(r['service_started'])
        self.assertEqual(r['hardware_actions'], 0)
        self.assertIn(('enable', installer.SERVICE), self.calls)
        self.assertFalse(any(c[0] in ('start', 'restart', 'reboot') for c in self.calls))
        self.assertIn('Restart=no', self.unit.read_text())
        self.assertIn('After=local-fs.target systemd-modules-load.service bootpy.service', self.unit.read_text())
        self.assertIn('KillMode=mixed\nSendSIGKILL=no', self.unit.read_text())

    def test_profiles_config_hardware_and_original_boot_id_preserved(self):
        for n in ('settings.local.json','speaker-target.local.json','speaker-profiles/P02-v1/profile.json'):
            p = self.root/n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'private')
        self.install()
        self.assertEqual((self.root/'soundsight.bit').read_bytes(), b'bit')
        self.assertEqual(json.loads((self.root/'SCREEN-INSTALL.json').read_text())['installed_boot_id'], 'original-boot')
        self.assertEqual((self.root/'speaker-profiles/P02-v1/profile.json').read_bytes(), b'private')

    def test_reinstall_is_accepted_and_receipt_matches_updated_ui(self):
        self.install(); self.install()
        receipt = json.loads((self.root/'SCREEN-INSTALL.json').read_text())
        self.assertEqual(receipt['software']['software/screen/ui.py'], installer.digest(self.data['software/screen/ui.py']))

    def test_unknown_hardware_or_modified_program_rejected_before_writes(self):
        (self.root/'soundsight.bit').write_bytes(b'newer board')
        with self.assertRaisesRegex(ValueError, 'BASELINE_MISMATCH'): self.install()
        self.assertFalse(self.unit.exists())
        (self.root/'soundsight.bit').write_bytes(b'bit')
        (self.root/'software/screen/ui.py').write_bytes(b'independent update')
        with self.assertRaisesRegex(ValueError, 'LOCAL_CHANGE_PRESERVED'): self.install()

    def test_service_enable_failure_rolls_back_all_files(self):
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        def fail(*args):
            r = self.ctl(*args)
            if args[0] == 'enable': r.returncode = 1; r.stderr = 'injected enable failure'
            return r
        with self.assertRaises(RuntimeError): self.install(fail)
        for n,v in before.items(): self.assertEqual((self.root/n).read_bytes(), v)
        self.assertFalse(self.unit.exists())
        self.assertFalse((self.root/'PRODUCT-INSTALL.json').exists())

    def test_service_rollback_failure_does_not_skip_file_restore(self):
        def fail(*args):
            r = self.ctl(*args)
            if args[0] == 'enable': r.returncode=1; r.stderr='injected'
            if args[0] == 'disable': raise TimeoutError('systemctl unavailable')
            return r
        with self.assertRaisesRegex(RuntimeError, 'Rollback needs inspection'): self.install(fail)
        self.assertEqual((self.root/'software/screen/ui.py').read_bytes(), self.old_ui)
        self.assertFalse((self.root/'PRODUCT-INSTALL.json').exists())

    def test_foreign_service_is_preserved(self):
        self.unit.parent.mkdir(); self.unit.write_text('another service')
        with self.assertRaisesRegex(ValueError, 'different systemd'): self.install()
        self.assertEqual(self.unit.read_text(), 'another service')

    def test_active_service_blocks_install(self):
        def active(*args):
            r = self.ctl(*args)
            if args[0] == 'is-active': r.stdout = 'active'
            return r
        with self.assertRaisesRegex(RuntimeError, 'stopped'): self.install(active)

    def test_missing_bootpy_blocks_install(self):
        def missing(*args):
            r = self.ctl(*args)
            if args[0] == 'show': r.stdout = 'not-found'
            return r
        with self.assertRaisesRegex(RuntimeError, 'bootpy'): self.install(missing)

    def test_payload_corruption_and_traversal_rejected(self):
        self.m['files']['software/screen/ui.py'] = '0'*64; self.pack()
        with self.assertRaisesRegex(ValueError, 'Corrupt'): self.install()
        for bad in ('../x','/x','C:/x','a\\b'):
            with self.assertRaises(ValueError): installer.regular(self.root, bad)

    def test_unit_root_cannot_inject_systemd_settings(self):
        for root in ('/home/a\nExecStart=/bin/sh', '/home/has space', '/home/%i', '/home/../etc'):
            with self.assertRaises(ValueError): installer.unit_text(root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
