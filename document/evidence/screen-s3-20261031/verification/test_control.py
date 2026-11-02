"""Independent host tests. No PYNQ imports, hardware or private asset extraction."""
import argparse
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
PACKAGE = ROOT/'delivery/soundsight_screen_control_s3.zip'
A_ZIP = BASE/'download/soundsight_pynq_3d_speaker.zip'
S2 = BASE/'ss-screen-ps-i2c-ui-s2'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


be = module('backend', ROOT/'runtime/software/screen/backend.py')
ui = module('ui', ROOT/'runtime/software/screen/ui.py')
with zipfile.ZipFile(PACKAGE) as archive:
    MANIFEST = json.loads(archive.read('manifest.json'))
    INSTALLER = archive.read('__main__.py')
    PAYLOAD = {name: archive.read(name) for name in MANIFEST['files']}
installer = types.ModuleType('candidate_installer')
exec(compile(INSTALLER, str(PACKAGE)+'!/__main__.py', 'exec'), installer.__dict__)


def original_functions(member, names, namespace):
    """Execute only public pure formatting/parser functions, from actual A ZIP."""
    with zipfile.ZipFile(A_ZIP) as archive:
        source = archive.read('SoundSight_PYNQ_3D_Speaker/'+member).decode()
    tree = ast.parse(source)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), member, 'exec'), namespace)
    return namespace


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='s3-independent-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = 100.
        self.clock = patch.object(be.time, 'monotonic', lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.b = be.Backend(self.root, control=True, motion=True)

    def ended(self, operation, code=0, lines=()):
        self.b.operation = operation
        self.b.state = 'STOPPING' if operation in ('SOUND', 'SPEAKER') else 'VERIFYING'
        self.b.proc = Mock()
        self.b.proc.poll.return_value = code
        self.b.pgid = 123
        self.b.status_rows = []
        for line in lines:
            self.b.accept_line(line)
        with patch.object(be.os, 'read', return_value=b''), patch.object(self.b, '_group_alive', return_value=False):
            self.b.tick()

    def verification_launch(self):
        self.b.state = 'VERIFYING'
        self.b.operation = 'verify-stop'


IDLE = dict(status=0x100000, fault=0, drops=0, sys=0, actuator=0, dual_axis=0)


class StopTests(Base):
    def test_full_two_process_runtime_to_readback_lifecycle(self):
        (self.root/'soundsight-3d.sh').write_text('fixture only')
        runtime, status = Mock(), Mock()
        runtime.pid, status.pid = 101, 102
        runtime.stdout.fileno.return_value, status.stdout.fileno.return_value = 11, 12
        runtime.poll.return_value = status.poll.return_value = 0
        pending = {11: [b'THREE_D_STOPPED SUMMARY=fixture ERROR=None\n', b''],
                   12: [('DEVICE_STATE='+json.dumps(dict(IDLE,fault=0x40))+'\n').encode(), b'']}
        def read(fd, size):
            return pending[fd].pop(0) if pending[fd] else b''
        def gone(pid, sig):
            if sig == 0: raise ProcessLookupError()
        with patch.object(be.os,'name','posix'), patch.object(be.os,'set_blocking'), \
             patch.object(be.os,'read', side_effect=read), patch.object(be.os,'killpg',side_effect=gone,create=True), \
             patch.object(be.subprocess,'Popen',side_effect=[runtime,status]) as popen:
            self.b.start('SOUND','both')
            self.assertFalse(self.b.stop_verified)
            self.b.tick()
            self.assertEqual(self.b.state,'VERIFYING')
            self.assertTrue(self.b.busy)
            self.assertEqual(popen.call_args.args[0][-1], 'status')
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            self.assertEqual(popen.call_args.kwargs['stdin'], be.subprocess.DEVNULL)
            with self.assertRaises(RuntimeError): self.b.start('SPEAKER','off')
            self.b.tick()
        self.assertEqual(self.b.state,'IDLE')
        self.assertFalse(self.b.busy)
        self.assertTrue(self.b.stop_verified)
        self.assertEqual(self.b.last_runtime_code,0)

    def test_all_idle_fields_and_activity_bits(self):
        self.assertTrue(be.Backend.idle_state(IDLE))
        self.assertTrue(be.Backend.idle_state(dict(IDLE, fault=0x40)))
        for key, bits in dict(status=(1, 2, 0x8000), sys=(1,), actuator=(1,),
                              dual_axis=(1, 8, 16), fault=(1, 2, 0x80)).items():
            for bit in bits:
                with self.subTest(key=key, bit=bit):
                    self.assertFalse(be.Backend.idle_state(dict(IDLE, **{key:bit})))
        for key in IDLE:
            for value in (None, True, -1, 0x100000000, '0', 0.0):
                with self.subTest(key=key, value=value):
                    self.assertFalse(be.Backend.idle_state(dict(IDLE, **{key:value})))
            missing = dict(IDLE)
            del missing[key]
            self.assertFalse(be.Backend.idle_state(missing))

    def test_runtime_exit_requires_separate_readback(self):
        for operation in ('SOUND', 'SPEAKER'):
            with self.subTest(operation=operation), patch.object(self.b, '_verify_stop', side_effect=self.verification_launch) as verify:
                self.b.stop_verified = False
                self.ended(operation)
                verify.assert_called_once()
                self.assertFalse(self.b.stop_verified)
                self.assertEqual(self.b.state, 'VERIFYING')
            self.ended('verify-stop', lines=['DEVICE_STATE='+json.dumps(IDLE)])
            self.assertTrue(self.b.stop_verified)
            self.assertEqual(self.b.state, 'IDLE')

    def test_missing_duplicate_bad_json_nonzero_and_active_status_block(self):
        good = 'DEVICE_STATE='+json.dumps(IDLE)
        cases = [(0, []), (0, [good, good]), (0, ['DEVICE_STATE={broken']),
                 (1, [good]), (0, ['DEVICE_STATE='+json.dumps(dict(IDLE, dual_axis=8))])]
        for code, lines in cases:
            with self.subTest(code=code, lines=lines):
                self.ended('verify-stop', code, lines)
                self.assertEqual(self.b.state, 'ERROR')
                self.assertFalse(self.b.stop_verified)
                with self.assertRaises(RuntimeError):
                    self.b.start('SOUND', 'off')

    def test_runtime_failure_remains_latched_after_idle_and_ack(self):
        with patch.object(self.b, '_verify_stop', side_effect=self.verification_launch):
            self.ended('SPEAKER', 1)
        self.ended('verify-stop', lines=['DEVICE_STATE='+json.dumps(IDLE)])
        self.assertTrue(self.b.session_failed)
        self.assertEqual(self.b.state, 'ERROR')
        with patch.object(self.b, '_verify_stop', side_effect=self.verification_launch) as verify:
            self.b.acknowledge()
            verify.assert_called_once()
        self.ended('verify-stop', lines=['DEVICE_STATE='+json.dumps(IDLE)])
        self.assertTrue(self.b.session_failed)
        with self.assertRaises(RuntimeError): self.b.start('SOUND', 'off')

    def test_parent_exit_with_live_group_never_unlocks_or_forcekills(self):
        self.b.proc, self.b.pgid = Mock(), 123
        self.b.proc.poll.return_value = 0
        self.b.operation, self.b.state = 'SOUND', 'RUNNING'
        with patch.object(be.os, 'read', return_value=b''), patch.object(be.os, 'killpg', create=True) as kill:
            self.b.tick()
            self.now += 6
            self.b.tick()
            self.assertTrue(self.b.busy)
            self.assertEqual(self.b.state, 'STOPPING')
            self.assertIn('UNCONFIRMED', self.b.note)
            self.assertTrue(all(c.args[1] in (0, be.signal.SIGINT) for c in kill.call_args_list))

    def test_verify_timeout_signals_once_and_retains_ownership(self):
        self.b.proc, self.b.pgid = Mock(), 123
        self.b.proc.poll.return_value = None
        self.b.operation, self.b.state, self.b.started = 'verify-stop', 'VERIFYING', 0
        with patch.object(be.os, 'read', return_value=b''), patch.object(be.os, 'killpg', create=True) as kill:
            self.b.tick()
            self.now += 6
            self.b.tick()
            kill.assert_called_once_with(123, be.signal.SIGINT)
            self.assertTrue(self.b.busy)


class TelemetryTests(Base):
    def setUp(self):
        super().setUp()
        env = original_functions('software/tetra3d/linux/runtime_3d.py', {'angle_text','display'},
                                 dict(time=be.time, HOST_TIMEOUT=.75))
        self.angle = env['display']
        env = original_functions('software/tetra3d/linux/speaker_runtime_3d.py', {'display'},
                                 dict(angle_display=self.angle))
        self.speaker = env['display']
        output = dict(valid=True, azimuth_valid=True, elevation_valid=True,
                      azimuth_deg=12.5, elevation_deg=-7.25)
        self.state = dict(phase='running', latest=dict(sequence=123, level=9000, at=self.now,
            output=output, window_count=20, window_size=20, valid_count=18, min_valid=12,
            motion=dict(axes=3, reason='COMMIT_ACCEPTED')),
            last_group=dict(sequence=100, at=self.now-5, output=dict(output, azimuth_deg=99., elevation_deg=55.)), last_clear=None)
        self.b.operation, self.b.state = 'SOUND', 'RUNNING'

    def test_actual_formatter_current_history_nooutput_and_unobservable(self):
        self.b.accept_line(self.angle(self.state).strip())
        self.assertEqual(self.b.live()['azimuth'], 12.5)
        self.assertEqual(self.b.live()['elevation'], -7.25)
        self.state['latest']['output'] = dict(valid=False, reason='below_volume_threshold')
        self.b.accept_line(self.angle(self.state).strip())
        self.assertIsNone(self.b.live()['azimuth'])
        self.assertEqual(self.b.live()['angle_reason'], 'BELOW_VOLUME_THRESHOLD')
        self.state['latest']['output'] = dict(valid=True, azimuth_valid=False,
            elevation_valid=True, elevation_deg=90.)
        self.b.accept_line(self.angle(self.state).strip())
        self.assertIsNone(self.b.live()['azimuth'])
        self.assertEqual(self.b.live()['elevation'], 90.)

    def test_actual_speaker_low_score_old_permission_age_and_expiry(self):
        self.state['speaker'] = dict(display_result=dict(score=.2, usable=True, reason='BELOW_THRESHOLD'),
            display_score_age_seconds=1.2, threshold=.45, permit=True, remaining_seconds=.8, reason='PERMITTED')
        self.b.operation = 'SPEAKER'
        self.b.accept_line(self.speaker(self.state).strip())
        live = self.b.live()
        self.assertEqual(live['score'], .2)
        self.assertTrue(live['permit'])
        self.now += .9
        live = self.b.live()
        self.assertFalse(live['permit'])
        self.assertEqual(live['remain'], 0.)
        self.assertAlmostEqual(live['score_age'], 2.1)
        self.now += 1.2
        self.assertTrue(self.b.live()['stale'])
        self.assertNotIn('score', self.b.live())

    def test_stop_malformed_long_and_policy_unknown_mask_values(self):
        self.b.accept_line(self.angle(self.state).strip())
        self.b.proc, self.b.pgid = Mock(), 1
        with patch.object(be.os, 'killpg', create=True): self.b.stop()
        self.assertTrue(self.b.live()['stale'])
        self.b.state, self.b.operation = 'RUNNING', 'SPEAKER'
        self.b.accept_line('FRAME=1 AZIMUTH=nan ELEVATION=inf SPEAKER_SCORE=.9 PERMIT=1 REMAIN=3s POLICY=old')
        live = self.b.live()
        self.assertIsNone(live['azimuth'])
        self.assertIsNone(live['elevation'])
        self.assertIsNone(live['permit'])
        self.b.accept_line('FRAME='+('x'*4097))
        self.assertTrue(self.b.live()['stale'])


class RoutingTests(Base):
    def test_real_parser_accepts_continuous_commands_and_ui_resets_axes(self):
        parser = original_functions('software/tetra3d/linux/board_3d.py', {'parser'},
            dict(argparse=argparse, Path=Path, ROOT=self.root, MASKS=dict(off=0,horizontal=1,vertical=2,both=3)))['parser']()
        view = ui.UI(self.b)
        with patch.object(self.b, '_launch') as launch:
            view.action('AXES')
            self.assertEqual(view.axes, 'horizontal')
            view.action('START')
            argv = launch.call_args.args[0]
            parsed = parser.parse_args(argv)
            self.assertEqual((parsed.command, parsed.frames, parsed.axes), ('follow-sound', 0, 'horizontal'))
            launch.reset_mock()
            view.action('MODE')
            launch.assert_not_called()
            self.assertEqual(view.axes, 'off')
            view.action('START')
            parsed = parser.parse_args(launch.call_args.args[0])
            self.assertEqual((parsed.command, parsed.frames, parsed.seconds, parsed.axes), ('speaker', 0, 0., 'off'))
        self.assertEqual(ui.parser().parse_args([]).seconds, 0.)
        self.assertEqual(ui.parser().parse_args([]).frames, 0)

    def test_busy_blocks_configuration_but_stop_and_exit_remain_available(self):
        view = ui.UI(self.b)
        self.b.proc, self.b.pgid, self.b.state = Mock(), 1, 'RUNNING'
        with patch.object(self.b, 'command') as command, patch.object(be.os, 'killpg', create=True) as kill:
            for action in ('USER_SELECT','APPLY','MODE','AXES','DISABLE'): view.action(action)
            command.assert_not_called()
            self.assertEqual(view.mode, 'SOUND')
            view.action('STOP')
            self.assertEqual(view.axes, 'off')
            view.action('EXIT')
            self.assertTrue(view.exit_requested)
            kill.assert_called_once_with(1, be.signal.SIGINT)

    def test_completion_forces_axis_reselection_and_repeated_press_not_retriggered(self):
        view = ui.UI(self.b)
        view.axes = 'both'
        self.b.state, self.b.generation = 'IDLE', 10
        view.tick()
        self.assertEqual(view.axes, 'off')
        view.buttons = [((0,0,20,20), 'START')]
        with patch.object(view, 'action') as action:
            for points in ([(2,2)], None, [(2,2)], [(2,2),(3,3)], [(2,2)]): view.touch(points)
            action.assert_called_once_with('START')


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {}
        with zipfile.ZipFile(A_ZIP) as archive:
            for name in MANIFEST['dependencies']:
                if (S2/name).is_file(): cls.sources[name] = (S2/name).read_bytes()
                elif name in ('soundsight.bit','soundsight.hwh'):
                    cls.sources[name] = (BASE/'ss-screen-ps-i2c-s2/output'/name).read_bytes()
                else: cls.sources[name] = archive.read('SoundSight_PYNQ_3D_Speaker/'+name)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='s3-install-independent-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'runtime'
        self.root.mkdir()
        for name, value in self.sources.items(): self.write(name, value)
        for name, before in MANIFEST['before'].items():
            if before is not None: self.write(name, (S2/name).read_bytes())
        receipt = dict(revision='SCREEN_PS_I2C_S2', touch_transport='PS_I2C0_EMIO_LINUX',
            installed_boot_id='preserve-original-boot', hardware={n:MANIFEST['dependencies'][n] for n in ('soundsight.bit','soundsight.hwh')},
            software={n:hashlib.sha256(v).hexdigest() for n,v in self.sources.items() if n.startswith('software/screen/')})
        receipt['software']['software/screen/ui.py'] = MANIFEST['before']['software/screen/ui.py']
        self.write('SCREEN-INSTALL.json', json.dumps(receipt).encode())
        # Synthetic sentinels, never personal assets from the source archive.
        for name in ('speaker-profiles/test/profile.json', 'servo3d.local.json', 'speaker-target.local.json',
                     'speaker-follow.local.json', 'settings.local.json', 'logs/retained.json'):
            self.write(name, b'SYNTHETIC_PROTECTED_SENTINEL\x00\n')
        self.before = self.snapshot()

    def write(self, name, value):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and not any(x.startswith(('backup_screen_control_s3_', '.screen-control-stage-'))
                                           for x in p.relative_to(self.root).parts)}

    def run_install(self):
        with contextlib.redirect_stdout(io.StringIO()): return installer.install(PACKAGE, self.root)

    def test_package_product_identity_and_crc(self):
        self.assertEqual(INSTALLER, (ROOT/'install_update.py').read_bytes())
        for name, value in PAYLOAD.items():
            self.assertEqual(value, (ROOT/'runtime'/name).read_bytes())
            self.assertEqual(hashlib.sha256(value).hexdigest(), MANIFEST['files'][name])
        with zipfile.ZipFile(PACKAGE) as archive: self.assertIsNone(archive.testzip())
        for name, value in self.sources.items():
            self.assertEqual(hashlib.sha256(value).hexdigest(), MANIFEST['dependencies'][name])

    def test_success_repeat_backup_receipt_and_private_preservation(self):
        backup = self.run_install()
        for name, value in self.before.items():
            if name not in MANIFEST['files'] and name != 'SCREEN-INSTALL.json':
                self.assertEqual((self.root/name).read_bytes(), value)
        for name, value in PAYLOAD.items(): self.assertEqual((self.root/name).read_bytes(), value)
        receipt = json.loads((self.root/'SCREEN-INSTALL.json').read_bytes())
        self.assertEqual(receipt['installed_boot_id'], 'preserve-original-boot')
        self.assertEqual(receipt['revision'], 'SCREEN_PS_I2C_S2')
        self.assertEqual(receipt['control_revision'], 'SCREEN_CONTROL_S3')
        self.assertEqual((backup/'software/screen/ui.py').read_bytes(), self.before['software/screen/ui.py'])
        once = self.snapshot()
        self.run_install()
        self.assertEqual(once, self.snapshot())

    def test_six_replace_failure_positions_restore_exact_originals(self):
        replace = installer.os.replace
        for fail_at in range(1, 7):
            count = [0]
            def faulty(source, dest):
                count[0] += 1
                if count[0] == fail_at: raise OSError('injected replacement failure')
                return replace(source, dest)
            with self.subTest(fail_at=fail_at), patch.object(installer.os, 'replace', faulty):
                with self.assertRaisesRegex(OSError, 'injected'): self.run_install()
            self.assertEqual(self.snapshot(), self.before)
            self.assertFalse(list(self.root.glob('.screen-control-stage-*')))

    def test_every_unknown_dependency_and_edited_product_is_rejected_before_write(self):
        for name in list(MANIFEST['dependencies']) + list(MANIFEST['files']):
            with self.subTest(name=name):
                old = (self.root/name).read_bytes() if (self.root/name).exists() else None
                self.write(name, b'UNKNOWN LOCAL MODIFICATION')
                edited = self.snapshot()
                with self.assertRaises(RuntimeError): self.run_install()
                self.assertEqual(edited, self.snapshot())
                if old is None: (self.root/name).unlink()
                else: self.write(name, old)
        self.assertFalse(list(self.root.glob('backup_screen_control_s3_*')))

    def test_wrong_receipt_missing_dependency_and_corrupt_payload_are_rejected(self):
        path = self.root/'SCREEN-INSTALL.json'
        original = path.read_bytes()
        receipt = json.loads(original)
        receipt['revision'] = 'UNKNOWN'
        path.write_text(json.dumps(receipt))
        with self.assertRaises(RuntimeError): self.run_install()
        path.write_bytes(original)
        missing = self.root/'soundsight-3d.sh'
        value = missing.read_bytes()
        missing.unlink()
        with self.assertRaises(RuntimeError): self.run_install()
        missing.write_bytes(value)
        broken = Path(self.tmp.name)/'corrupt.zip'
        with zipfile.ZipFile(PACKAGE) as src, zipfile.ZipFile(broken,'w') as dst:
            for name in src.namelist(): dst.writestr(name, b'BAD' if name == 'software/screen/ui.py' else src.read(name))
        with self.assertRaisesRegex(RuntimeError, 'checksum'): installer.install(broken, self.root)
        self.assertEqual(self.before, self.snapshot())

    def test_linux_entry_locks_and_busy_tokens_are_simulated_only(self):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=Mock())
        fake_open = Mock()
        proc = Mock()
        proc.name = '999999999'
        proc.__truediv__ = Mock(return_value=Mock())
        proc.__truediv__.return_value.read_bytes.return_value = b''
        proc_root = types.SimpleNamespace(iterdir=lambda:[proc])
        def path(value):
            return proc_root if str(value) == '/proc' else Path(value)
        with patch.dict(sys.modules, {'fcntl':fake_fcntl}), patch.object(installer.sys,'platform','linux'), \
             patch.object(installer.os,'geteuid',return_value=0,create=True), \
             patch.object(installer,'open',fake_open,create=True), patch.object(installer,'Path',side_effect=path), \
             patch.object(installer.sys,'argv',[str(PACKAGE)]), patch.object(installer,'install') as install:
            installer.main()
            self.assertEqual(fake_fcntl.flock.call_count,2)
            self.assertEqual([c.args[0] for c in fake_open.call_args_list],
                ['/tmp/soundsight-screen-owner.lock','/tmp/soundsight-ps-owner.lock'])
            install.assert_called_once()
            install.reset_mock()
            for token in (b'board_3d.py',b'run_pcm.py',b'run_buffered.py',b'live_speaker.py',
                          b'speaker_process.py',b'pipeline_backend',b'software/screen/ui.py',
                          b'software/screen/screen_i2c_prepare.py'):
                proc.__truediv__.return_value.read_bytes.return_value = b'python\x00'+token
                with self.subTest(token=token), self.assertRaisesRegex(RuntimeError,'Stop screen/runtime'):
                    installer.main()
            install.assert_not_called()
            proc.__truediv__.return_value.read_bytes.return_value = b''
            fake_fcntl.flock.side_effect = BlockingIOError('busy lock')
            with self.assertRaises(BlockingIOError): installer.main()
            install.assert_not_called()


if __name__ == '__main__':
    print('HOST_ONLY=1 HARDWARE_ACTIONS=0 PRIVATE_ASSETS_EXTRACTED=0', flush=True)
    print('PACKAGE_SHA256='+hashlib.sha256(PACKAGE.read_bytes()).hexdigest(), flush=True)
    unittest.main(verbosity=2)
