"""Independent fake register model; actual Client/filter/normal session, no hardware."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import contextlib
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ps'))
import ps_client as hw
import horizontal_motion as motion
from volume_gate import VolumeClient
from test_normal import Device as BaseDevice, Connection
import run_normal
import board_tools

CFG = dict(front_deg=180, direction=1, min_deg=90, max_deg=270)


class Device(BaseDevice):
    def __init__(self):
        super().__init__()
        self.bound = True
        self.permit = False
        self.watchdog = 0
        self.shadow = 0
        self.actions = []
        self.last_command = 0
        self.good_pairs = True
        self.draining = False

    def read(self, a):
        if a == hw.STATUS:
            return super().read(a) | 16 | (int(self.bound) << 19) | (int(self.draining) << 15)
        if a == hw.FEATURE:
            return (0x11202800 if self.good_pairs else 0x11000000) | self.pair << 8
        if a == hw.ACT: return int(self.permit)
        return super().read(a)

    def write(self, a, v):
        self.actions.append((self.sequence, a, v))
        if a == hw.WDT:
            assert not self.permit
            self.watchdog = v
        elif a == hw.ANGLE:
            assert v & 0x40000 and not v & 0x80000
            self.shadow = v & 511
        elif a == hw.ACT:
            if v in (0, 2, 4): self.permit = False
            if v == 2: super().write(a, v)
            elif v == 1:
                assert self.active and not self.fault and self.watchdog and self.bound
                self.permit = True
            elif v == 8:
                assert self.permit and self.locked and self.good_pairs and not self.draining
                assert self.sequence != self.last_command and not self.fault
                self.last_command = self.sequence
        else: super().write(a, v)


class Solver:
    def __init__(self): self.valid = True; self.angle = 10*256
    def solve(self, frame, config=None):
        return dict(api_status=0, bridge_status=0, direction_valid=int(self.valid),
                    angle_q8=self.angle, reason=0 if self.valid else 3, valid_pairs=6,
                    servo_cmd_valid=0)


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.d = Device(); self.s = Solver()
        self.c = motion.HorizontalClient(self.d, self.s, 7000, CFG, window_frames=3, min_valid=2)
        self.c.start()
        self.records = []

    def frame(self): return self.c.record_one(self.records.append)
    def commands(self): return [x for x in self.d.actions if x[1:] == (hw.ACT, 8)]

    def test_window_then_refresh_same_target_before_consume(self):
        self.frame(); self.frame(); self.assertFalse(self.commands())
        r = self.frame()
        self.assertEqual(r['motion']['servo_deg'], 190)
        self.frame()
        self.assertEqual([x[0] for x in self.commands()], [3, 4])
        self.assertEqual(self.d.watchdog, 46080000)
        for seq in (3, 4):
            ops = [(a, v) for n, a, v in self.d.actions if n == seq]
            self.assertLess(ops.index((hw.ACT, 8)), ops.index((hw.SNAP, 4)))

    def test_deadband_refresh_is_not_target_movement(self):
        for _ in range(3): self.frame()
        self.s.angle = 12*256
        for _ in range(3): r = self.frame()
        self.assertEqual(r['direction_output']['reason'], 'within_deadband')
        self.assertEqual(r['motion']['servo_deg'], 190)
        self.assertEqual(len(self.commands()), 4)

    def test_quiet_revokes_and_requires_a_new_window(self):
        for _ in range(3): self.frame()
        self.d.low = True; self.frame()
        self.assertFalse(self.d.permit)
        self.d.low = False
        self.frame(); self.frame(); self.assertFalse(self.d.permit)
        self.frame(); self.assertTrue(self.d.permit)

    def test_raw_rejection_on_good_window_does_not_commit(self):
        self.frame(); self.frame(); self.s.valid = False
        r = self.frame()
        self.assertTrue(r['direction_output']['valid'])
        self.assertFalse(r['motion']['committed'])
        self.assertFalse(self.commands())

    def test_raw_hardware_disqualification_prevents_command(self):
        self.d.good_pairs = False
        for _ in range(3): self.frame()
        self.assertFalse(self.commands())

    def test_isolated_rejected_sample_never_refreshes_watchdog(self):
        for _ in range(3): self.frame()
        self.s.valid = False; self.frame()
        self.assertTrue(self.d.permit)
        self.assertEqual(len(self.commands()), 1)
        self.s.valid = True; self.frame()
        self.assertEqual(len(self.commands()), 2)

    def test_outside_mechanics_rejects_without_clamp(self):
        self.s.angle = 120*256
        for _ in range(3): r = self.frame()
        self.assertEqual(r['motion']['reason'], 'OUTSIDE_MECHANICAL_RANGE')
        self.assertFalse(self.commands())

    def test_gap_drops_existing_target(self):
        for _ in range(3): self.frame()
        self.d.sequence += 1; self.frame()
        self.assertFalse(self.d.permit)
        self.assertIsNone(self.c.target)

    def test_rejected_window_revokes(self):
        for _ in range(3): self.frame()
        for a in (-40, 0, 40): self.s.angle = a*256; r = self.frame()
        self.assertFalse(r['direction_output']['valid'])
        self.assertFalse(self.d.permit)

    def test_manual_still_needs_loud_real_fresh_frame(self):
        self.c = motion.HorizontalClient(self.d, self.s, 7000, CFG, manual_angle=175)
        r = self.frame(); self.assertEqual(r['motion']['servo_deg'], 175)
        self.d.low = True; self.frame(); self.assertFalse(self.d.permit)

    def test_drain_wait_does_not_block_frame_release(self):
        self.d.draining = True
        for _ in range(3): r = self.frame()
        self.assertEqual(r['motion']['reason'], 'WAITING_FOR_PWM_DRAIN')
        self.assertEqual(self.d.consumed, 3)
        self.d.draining = False; self.frame(); self.assertTrue(self.d.permit)

    def test_stop_tail_cannot_move(self):
        for _ in range(3): self.frame()
        self.c.stop_direction_output(); self.c.disable()
        self.c.record_one(self.records.append, allow_fault=True)
        self.assertFalse(self.d.permit)
        self.assertEqual(len(self.commands()), 1)

    def test_user_stop_arrives_during_acquire_prevents_new_commit(self):
        self.frame(); self.frame()
        self.c.stop_requested = lambda: True
        self.frame()
        self.assertFalse(self.commands())
        self.assertFalse(self.d.permit)

    def test_fault_or_sink_failure_retains_lock_and_stops(self):
        self.frame(); self.frame()
        def fail(record): raise IOError('injected sink failure')
        with self.assertRaises(IOError): self.c.record_one(fail)
        self.assertTrue(self.d.locked)
        self.assertFalse(self.d.permit)
        self.assertEqual(self.d.consumed, 2)

    def test_unbound_refused_before_write(self):
        self.d.bound = False; self.d.actions.clear()
        with self.assertRaises(RuntimeError): self.c.identify()
        self.assertFalse(self.d.actions)

    def test_normal_session_counts_and_stops_motion(self):
        # Exercise actual session STOP/drain; model acquisition is already idle.
        self.c.disable()
        if self.d.queued:
            self.c.acquire(); self.c.consume(dict(sequence=self.d.sequence))
        self.d.fault = 0
        conn = Connection()
        class Mail:
            def publish(self, state):
                import time
                return time.monotonic()
        stop = SimpleNamespace(is_set=lambda: False)
        args = SimpleNamespace(frames=8, mode='real', clear_faults=0x40, horizontal_motion=True)
        run_normal.normal_session(conn, stop, Mail(), self.c, args)
        kind, out = conn.messages[-1]
        self.assertEqual(kind, 'done', out)
        self.assertEqual(out['stats']['motion_commits'], 6)
        self.assertTrue(out['motion_requested'])
        self.assertFalse(self.d.permit)

    def test_default_volume_client_cannot_arm(self):
        with self.assertRaises(ValueError): VolumeClient(self.d, self.s, 7000).arm(1)

    def test_mapping_boundaries_sign_and_nearest_even(self):
        self.assertEqual(motion.map_angle(10*256, dict(CFG, direction=-1)), 170)
        self.assertEqual(motion.map_angle(128, CFG), 180)
        self.assertEqual(motion.map_angle(384, CFG), 182)
        self.assertIsNone(motion.map_angle(90*256+1, CFG))
        self.assertIsNone(motion.map_angle(180*256, CFG))
        for cfg in (dict(CFG, direction=0), dict(CFG, front_deg=0), dict(CFG, max_deg=361)):
            with self.assertRaises(ValueError): motion.validate_calibration(cfg)

    def test_geometry_direction_only_preserves_every_q8_angle(self):
        # Offset alone gives no depth: keep the exact old integer-angle map.
        config = dict(CFG, geometry=dict(pivot_x_cm=20, pivot_y_cm=-30, source_range_cm=None))
        for angle in range(-180*256, 180*256):
            expected = round(180+angle/256) if -90*256 <= angle <= 90*256 else None
            self.assertEqual(motion.map_angle(angle, config), expected)

    def test_geometry_known_right_triangle_and_reverse_direction(self):
        # Array source=(100,0), pivot=(0,100): bearing is exactly -45 deg.
        config = dict(CFG, geometry=dict(pivot_x_cm=0, pivot_y_cm=100, source_range_cm=100))
        self.assertEqual(motion.map_angle(0, config), 135)
        self.assertEqual(motion.map_angle(0, dict(config, direction=-1)), 225)
        config['geometry']['pivot_y_cm'] = -100
        self.assertEqual(motion.map_angle(0, config), 225)
        # Source=(0,100), pivot=(100,0): 135 deg about pivot, unlike array's 90.
        config = dict(CFG, min_deg=0, max_deg=360,
                      geometry=dict(pivot_x_cm=100, pivot_y_cm=0, source_range_cm=100))
        self.assertEqual(motion.map_angle(90*256, config), 315)

    def test_geometry_zero_offset_and_limits_and_singularity(self):
        cfg = dict(CFG, geometry=dict(pivot_x_cm=0, pivot_y_cm=0, source_range_cm=10))
        self.assertEqual(motion.map_angle(128, cfg), 180)
        self.assertEqual(motion.map_angle(384, cfg), 182)
        cfg['geometry'] = dict(pivot_x_cm=0, pivot_y_cm=100, source_range_cm=100)
        self.assertIsNone(motion.map_angle(0, dict(cfg, min_deg=150)))
        cfg['geometry'] = dict(pivot_x_cm=100, pivot_y_cm=0, source_range_cm=100)
        self.assertEqual(motion.mapped_target(0, cfg), (None, 'GEOMETRY_TARGET_UNDEFINED'))
        cfg['geometry']['pivot_x_cm'] = 200
        # Behind the pivot normalizes to -180; no artificial wrapping/clamping.
        self.assertEqual(motion.map_angle(0, dict(cfg, min_deg=0)), 0)

    def test_geometry_rejects_bad_settings(self):
        for geom in (None, dict(pivot_x_cm=float('nan')), dict(pivot_y_cm=float('inf')),
                     dict(pivot_x_cm=True), dict(source_range_cm=0), dict(source_range_cm=-1),
                     dict(source_range_cm='100'), dict(pivot_z_cm=10)):
            with self.subTest(geometry=geom), self.assertRaises(ValueError):
                motion.validate_calibration(dict(CFG, geometry=geom))

    def test_geometry_actual_session_corrects_and_singular_target_revokes(self):
        self.s.angle = 0
        self.c = motion.HorizontalClient(self.d, self.s, 7000,
            dict(CFG, geometry=dict(pivot_x_cm=100, pivot_y_cm=0, source_range_cm=100)),
            window_frames=1, min_valid=1)
        # With source bearing +90, target about pivot is 135: outside limits.
        self.s.angle = 90*256
        r = self.frame(); self.assertEqual(r['motion']['reason'], 'OUTSIDE_MECHANICAL_RANGE')
        self.s.angle = -90*256
        self.c.calibration['min_deg'] = 0
        r = self.frame(); self.assertEqual(r['motion']['servo_deg'], 45)
        self.assertTrue(self.d.permit)
        self.s.angle = 0
        r = self.frame(); self.assertEqual(r['motion']['reason'], 'GEOMETRY_TARGET_UNDEFINED')
        self.assertFalse(self.d.permit)
        self.assertEqual(self.d.consumed, 3)

    def test_manual_servo_angle_does_not_apply_source_geometry(self):
        cfg = dict(CFG, geometry=dict(pivot_x_cm=100, pivot_y_cm=0, source_range_cm=100))
        self.s.angle = 0
        self.c = motion.HorizontalClient(self.d, self.s, 7000, cfg, manual_angle=175)
        self.assertEqual(self.frame()['motion']['servo_deg'], 175)

    def test_geometry_cli_preserves_calibration_and_no_hardware(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(board_tools, 'ROOT', Path(tmp)), \
                patch.object(board_tools, 'single_owner', return_value=contextlib.nullcontext()), \
                patch.object(board_tools, 'load_api') as api, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'horizontal.local.json'
            self.assertEqual(board_tools.main(['servo-config','180','1','90','270']), 0)
            self.assertEqual(board_tools.main(['servo-geometry','0','100','--source-range-cm','100']), 0)
            cfg = motion.load_calibration(path)
            self.assertEqual(motion.map_angle(0, cfg), 135)
            self.assertEqual(board_tools.main(['servo-config','180','-1','90','270']), 0)
            cfg = motion.load_calibration(path)
            self.assertEqual(motion.map_angle(0, cfg), 225)
            self.assertEqual(board_tools.main(['servo-geometry','0','100']), 0)
            cfg = motion.load_calibration(path)
            self.assertIsNone(cfg['geometry']['source_range_cm'])
            self.assertEqual(motion.map_angle(0, cfg), 180)
            before = path.read_bytes()
            self.assertEqual(board_tools.main(['servo-geometry','0','100','--source-range-cm','0']), 1)
            self.assertEqual(path.read_bytes(), before)
            api.assert_not_called()

    def test_hwh_and_explicit_cli_motion_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = dict(ACTUATOR_BOUND=1, LEVEL_ENABLE=1, CLK_FREQ_HZ=61440000,
                          SERVO_MAX=360, MECHANICAL_MIN=0, MECHANICAL_MAX=360)
            def xml():
                return ('<ROOT><MODULE INSTANCE="compute" MODTYPE="bd_clean_compute">'
                        '<PARAMETER NAME="LEVEL_ENABLE" VALUE="1"/></MODULE>'
                        '<MODULE INSTANCE="ps_link" MODTYPE="bd_ps_link">'+
                        ''.join('<PARAMETER NAME="%s" VALUE="%s"/>' % p for p in params.items())+
                        '</MODULE><MEMRANGE INSTANCE="ps_link" SLAVEBUSINTERFACE="S_AXI" '
                        'MEMTYPE="REGISTER" BASEVALUE="0x40000000" HIGHVALUE="0x40000fff"/></ROOT>')
            (root/'soundsight.hwh').write_text(xml())
            (root/'soundsight.bit').write_bytes(b'fixture')
            (root/'horizontal.local.json').write_text(json.dumps(CFG))
            self.assertEqual(board_tools.hwh_check(root), (0x40000000, 4096))
            args = SimpleNamespace(operation='normal', frames=10, mode='real', min_level=7000,
                                   horizontal_motion=False, manual_angle=None)
            cmd, _, _ = board_tools.run_arguments(args, root)
            self.assertNotIn('--horizontal-motion', cmd)
            args.horizontal_motion = True; args.manual_angle = 175
            with self.assertRaisesRegex(ValueError, 'separate calibration'):
                board_tools.run_arguments(args, root)
            args.manual_angle = None
            cmd, _, _ = board_tools.run_arguments(args, root)
            parsed = run_normal.parse_args(cmd[2:])
            self.assertTrue(parsed.horizontal_motion)
            self.assertIsNone(parsed.manual_angle)
            # The old automatic path must not bypass the current 3-D speaker
            # gate. Reject from both short helper and direct CLI before MMIO.
            params['DUAL_AXIS_ENABLE'] = 1
            (root/'soundsight.hwh').write_text(xml())
            # General readiness and manual calibration share this checker;
            # those must remain valid on the same dual-axis metadata.
            self.assertEqual(board_tools.hwh_check(root), (0x40000000, 4096))
            with self.assertRaisesRegex(ValueError, 'Dual-axis hardware requires'):
                board_tools.run_arguments(args, root)
            with self.assertRaises(SystemExit):
                run_normal.parse_args(cmd[2:])
            import run_capture
            old_parser = run_capture.argument_parser()
            legacy_config = root/'legacy.json'
            legacy_config.write_text(json.dumps([0, 1, -46080, 46079, 0, 360, 360]))
            legacy_args = old_parser.parse_args([
                '--hwh', str(root/'soundsight.hwh'), '--output', str(root/'unused.jsonl'),
                '--mode', 'real', '--horizontal-motion', '--servo-config', str(legacy_config),
                '--watchdog-ticks', '46080000'])
            with self.assertRaisesRegex(ValueError, 'Dual-axis hardware requires'):
                run_capture.prepare_args(legacy_args, old_parser)
            params['DUAL_AXIS_ENABLE'] = 0
            (root/'soundsight.hwh').write_text(xml())
            self.assertEqual(run_capture.prepare_args(legacy_args, old_parser),
                             [0, 1, -46080, 46079, 0, 360, 360])
            for bad in ('debug',):
                args.operation = bad
                with self.assertRaises(ValueError): board_tools.run_arguments(args, root)
            params['ACTUATOR_BOUND'] = 0; (root/'soundsight.hwh').write_text(xml())
            with self.assertRaises(ValueError): motion.check_hwh(root/'soundsight.hwh')

    def test_calibration_save_has_no_hardware_action_or_implicit_enable(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(board_tools, 'ROOT', Path(tmp)), \
                patch.object(board_tools, 'single_owner', return_value=contextlib.nullcontext()), \
                patch.object(board_tools, 'load_api') as api, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(board_tools.main(['servo-config','180','-1','170','190']), 0)
            saved = motion.load_calibration(Path(tmp)/'horizontal.local.json')
            self.assertEqual(saved['direction'], -1)
            self.assertNotIn('enabled', saved)
            api.assert_not_called()

    def test_bist_rejected_and_stale_console_is_not_current_servo_target(self):
        frame = dict(sequence=1, status=24, words=[0x11202800,0,0,0,0]*6, fault=0)
        self.assertFalse(motion.qualified(frame, self.s.solve(frame)))
        for _ in range(3): r = self.frame()
        state = run_normal.RuntimeState(); state.accept(r)
        line = run_normal.display_line(state.snapshot(), now=state.latest['at']+2)
        self.assertIn('STOPPED_FAULT_OR_STALE_DATA', line)


if __name__ == '__main__': unittest.main()
