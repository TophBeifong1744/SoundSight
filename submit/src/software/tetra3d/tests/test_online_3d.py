"""Offline three-dimensional policy/protocol tests. No PYNQ import or motion."""
import copy
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
for path in ('software/ps', 'software/tests', 'software/tetra3d/linux'):
    sys.path.insert(0, str(ROOT/path))
import ps_client as hw
from test_normal import Device as SnapshotModel, Connection
from filter_3d import SpatialFilter, angles
import motion_3d as motion
from client_3d import ThreeDClient
from runtime_3d import State3D, display
import board_3d
import run_normal


def result(az=0, el=0, valid=True):
    a, e = math.radians(az), math.radians(el)
    return dict(api_status=0, bridge_status=0, direction_valid=int(valid), reason=0 if valid else 1,
                ux=math.cos(e)*math.cos(a), uy=math.cos(e)*math.sin(a), uz=math.sin(e),
                azimuth_valid=int(abs(el)<89.99), elevation_valid=1, valid_pairs=6)


def frame(seq=1, level=10000):
    return dict(sequence=seq, status=0x20031, energy=level, fault=0, drops=0)


def config():
    return dict(horizontal=dict(front_deg=180, direction=1, min_deg=0, max_deg=360),
                vertical=dict(front_deg=110, direction=1, min_deg=0, max_deg=220))


class AxisModel(SnapshotModel):
    """Independent register-side model of the published dual-axis commands.

    Logical commands only: physical PWM/CDC/lease boundaries belong to XSim.
    """
    def __init__(self):
        super().__init__()
        self.reg = {motion.STATE: 0, motion.CAP: motion.CAPABILITY}
        self.writes = []
        self.used = 0
        self.fresh_target = self.fresh_frame = False

    def read(self, address):
        if address in self.reg:
            return self.reg[address]
        if address == 0x94:
            return 1024  # PCM isn't enabled by the angle-only path.
        return super().read(address)

    def write(self, a, value):
        self.writes.append((a, value))
        if a == motion.TARGET:
            self.fresh_target = True
        if a == motion.FRAME:
            self.fresh_frame = True
        if a == motion.COMMAND:
            state = self.reg[motion.STATE]
            if value == 0:
                self.reg[motion.STATE] &= 0x300
            elif value == 4:
                assert not state & 0x19
                self.reg[motion.STATE] = self.reg[motion.AXES] << 8
                self.reg[0xcc], self.reg[0xd0] = self.reg[motion.H_LIMITS], self.reg[motion.V_LIMITS]
            elif value in (1, 2):
                assert (self.active if value == 2 else not self.active and not self.queued)
                assert not self.fault and not state & 0x19
                self.reg[motion.STATE] |= 1 | (2 if value == 2 else 0)
                self.fresh_target = self.fresh_frame = False
            elif value == 3:
                assert state & 1 and self.fresh_target and not self.fault
                if state & 2:
                    assert self.locked and self.fresh_frame
                    assert self.reg[motion.FRAME] == self.sequence != self.used
                    self.used = self.sequence
                    self.reg[motion.LAST_FRAME] = self.sequence
                self.reg[motion.LAST_TARGET] = self.reg[motion.TARGET]
                self.reg[motion.STATE] |= 4
                self.fresh_target = self.fresh_frame = False
            else:
                raise AssertionError('Undefined command')
            return
        if a >= motion.CAP:
            self.reg[a] = value
            return
        if a == hw.ACT or a == hw.SYS and not value & 1:
            self.reg[motion.STATE] &= 0x300
        super().write(a, value)


class FixedSolver:
    def solve(self, snapshot):
        return result(30, 20)


class OnlineTests(unittest.TestCase):
    def group(self, filt, az=0, el=0, start=1):
        for seq in range(start, start+filt.window):
            row = filt.apply(frame(seq), result(az, el), 7000)
        return row

    def test_spatial_wrap_poles_and_deadband(self):
        f = SpatialFilter(4, 3)
        for i, az in enumerate((179, -179, 178, -178), 1):
            row = f.apply(frame(i), result(az), 7000)
        self.assertTrue(row['direction_output']['valid'])
        self.assertAlmostEqual(abs(row['direction_output']['azimuth_deg']), 180)
        held = self.group(f, 179, start=5)['direction_output']
        self.assertFalse(held['updated'])
        pole = self.group(SpatialFilter(4, 3), 0, 90)['direction_output']
        self.assertTrue(pole['valid'])
        self.assertFalse(pole['azimuth_valid'])
        self.assertAlmostEqual(pole['elevation_deg'], 90)

    def test_outliers_rejection_and_minimum(self):
        f = SpatialFilter(6, 4)
        for i, az in enumerate((0, 1, -1, 2, 120, -120), 1):
            row = f.apply(frame(i), result(az), 7000)
        self.assertTrue(row['direction_output']['valid'])
        self.assertEqual(row['angle_filter']['inlier_count'], 4)
        for i in range(7, 13):
            row = f.apply(frame(i), result(i*45), 7000)
        self.assertFalse(row['direction_output']['valid'])
        self.assertIsNone(f.held)

    def test_quiet_fault_gap_and_stop_clear_target(self):
        for kind in ('quiet', 'fault', 'cancel', 'unmeasured', 'gap', 'stop', 'nan'):
            f = SpatialFilter(4, 3)
            self.group(f)
            fr, res = frame(5), result()
            if kind == 'quiet': fr['energy'] = 1
            if kind == 'fault': fr['fault'] = 8
            if kind == 'cancel': fr['status'] |= 1 << 20
            if kind == 'unmeasured': fr['status'] &= ~32
            if kind == 'gap': fr['sequence'] = 7
            if kind == 'stop': f.stop()
            if kind == 'nan': res['ux'] = float('nan')
            row = f.apply(fr, res, 7000)
            self.assertIsNone(f.held, kind)
            self.assertTrue(row['angle_filter']['reset_reason'], kind)
            self.assertFalse(row['direction_output']['valid'], kind)

    def test_vector_storage_is_bounded(self):
        f = SpatialFilter(20, 12)
        for n in range(1, 20001):
            f.apply(frame(n), result(), 7000)
            self.assertLess(len(f.vectors), 20)

    def test_axis_mapping_ranges_pole_and_translation(self):
        c = config()
        out = dict(angles([1, 1, 1]), valid=True)
        targets, why = motion.mapped_targets(out, c, 3)
        self.assertEqual(targets, dict(horizontal=225, vertical=145))
        pole = dict(angles([0, 0, 1]), valid=True)
        self.assertIsNone(motion.mapped_targets(pole, c, 3)[0])
        self.assertEqual(motion.mapped_targets(pole, c, 2)[0]['vertical'], 200)
        c['horizontal']['max_deg'] = 200
        self.assertIsNone(motion.mapped_targets(out, c, 3)[0])
        c = config()
        c['pointing'] = dict(pivot_y_cm=100, source_range_cm=100)
        target = motion.mapped_targets(dict(angles([1, 0, 0]), valid=True), c, 1)[0]
        self.assertEqual(target['horizontal'], 135)

    def test_config_rejects_invalid_and_has_no_hardware_effect(self):
        d = AxisModel()
        axes = motion.DualAxis(d)
        axes.identify()
        self.assertEqual(d.writes, [])
        bad = config()
        bad['vertical']['max_deg'] = 221
        with self.assertRaises(ValueError): axes.configure(bad, 3)
        self.assertEqual(d.writes, [])
        with self.assertRaises(ValueError): motion.pointing_geometry({'pivot_x_cm': float('nan')})

    def test_manual_both_no_audio_and_revoke_on_error(self):
        d = AxisModel()
        now = [0.]
        report = motion.manual(d, config(), dict(horizontal=185, vertical=110), .21,
                               clock=lambda: now[0], sleep=lambda t: now.__setitem__(0, now[0]+t))
        self.assertEqual(report['commits'], 3)
        self.assertFalse(report['audio_started'])
        self.assertFalse(d.read(motion.STATE) & 1)
        self.assertFalse(any(a == hw.SYS and v & 1 for a, v in d.writes))
        d = AxisModel()
        with self.assertRaises(KeyboardInterrupt):
            motion.manual(d, config(), {'vertical': 110}, 1.,
                          sleep=lambda t: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertFalse(d.read(motion.STATE) & 1)

    def test_manual_rejects_capture_and_unconfigured_range(self):
        d = AxisModel()
        d.active = True
        with self.assertRaises(RuntimeError): motion.manual(d, config(), {'horizontal': 185})
        self.assertEqual(d.writes, [])
        with self.assertRaises(ValueError): motion.manual(AxisModel(), config(), {'vertical': 221})

    def test_manual_extension_revoke_error_attempts_legacy_stop(self):
        d = AxisModel()
        original_write = d.write
        def write(address, value):
            if address == motion.COMMAND and value == 0:
                raise OSError('injected extension failure')
            return original_write(address, value)
        d.write = write
        now = [0.]
        with self.assertRaises(OSError):
            motion.manual(d, config(), {'horizontal': 185}, .1,
                clock=lambda: now[0], sleep=lambda n: now.__setitem__(0, now[0]+n))
        self.assertFalse(d.read(motion.STATE) & 1)
        self.assertEqual(d.writes[-2:], [(hw.ACT, 2), (hw.SYS, 8)])

    def test_follow_atomic_write_and_fresh_sequence(self):
        d = AxisModel()
        d.active = d.queued = d.locked = True
        a = motion.DualAxis(d)
        a.configure(config(), 3)
        a.arm(True)
        a.commit(dict(horizontal=210, vertical=130), 1)
        self.assertEqual(d.writes[-3:], [(motion.TARGET, 210 | 130 << 16),
                                        (motion.FRAME, 1), (motion.COMMAND, 3)])
        with self.assertRaises(AssertionError):
            a.commit(dict(horizontal=211, vertical=131), 1)

    def test_normal_session_off_consumes_and_keeps_debug_after_stop(self):
        d = AxisModel()
        c = ThreeDClient(d, FixedSolver(), 7000, 4, 3)
        con = Connection()
        ctx = mp.get_context('spawn')
        box, stop = run_normal.Mailbox(ctx), ctx.Event()
        box.poll()
        state = State3D(14)
        args = SimpleNamespace(mode='real', frames=12, clear_faults=0, motion_requested=False)
        run_normal.normal_session(con, stop, box, c, args, state_factory=lambda: state,
                                  final_extra=lambda: dict(records=state.records))
        kind, report = con.messages[-1]
        self.assertEqual(kind, 'done', report)
        self.assertEqual(report['stats']['consumed'], 12)
        self.assertEqual(report['stats']['drained'], 1)
        self.assertEqual(len(report['records']), 13)
        self.assertNotIn('records', box.poll())
        self.assertFalse(any(a == motion.COMMAND and v in (1, 2, 3) for a, v in d.writes))

    def test_follow_session_commits_only_after_group_and_stops(self):
        d = AxisModel()
        c = ThreeDClient(d, FixedSolver(), 7000, 4, 3, 3, config())
        c.identify()
        c.start()
        rows = []
        for _ in range(5): c.record_one(rows.append)
        self.assertFalse(any(r['motion']['committed'] for r in rows[:3]))
        self.assertTrue(all(r['motion']['committed'] for r in rows[3:]))
        self.assertEqual(rows[-1]['motion']['targets'], dict(horizontal=210, vertical=130))
        c.stop_direction_output()
        c.disable()
        self.assertFalse(d.read(motion.STATE) & 1)

    def test_quiet_and_target_expiry_revoke(self):
        d = AxisModel()
        c = ThreeDClient(d, FixedSolver(), 7000, 4, 3, 1, config())
        c.start()
        for _ in range(4): c.record_one(lambda r: None)
        self.assertTrue(d.read(motion.STATE) & 1)
        c.target_time = time.monotonic()-1
        c.record_one(lambda r: None)
        self.assertFalse(d.read(motion.STATE) & 1)
        for _ in range(3): c.record_one(lambda r: None)
        self.assertTrue(d.read(motion.STATE) & 1)
        d.low = True
        c.record_one(lambda r: None)
        self.assertFalse(d.read(motion.STATE) & 1)

    def test_sink_failure_and_solver_exception_stop_retain_snapshot(self):
        for cause in ('sink', 'solver'):
            d = AxisModel()
            c = ThreeDClient(d, FixedSolver(), 7000, 4, 3)
            c.start()
            if cause == 'solver':
                c.solver.solve = lambda f: (_ for _ in ()).throw(ValueError('solver failed'))
            count = [0]
            def sink(row):
                count[0] += 1
                raise OSError('sink failed')
            with self.assertRaises((OSError, ValueError)): c.record_one(sink)
            self.assertTrue(d.locked)
            self.assertEqual(d.consumed, 0)
            self.assertFalse(d.active)
            self.assertLessEqual(count[0], 1)

    def test_hardware_fault_prevents_consume_and_motion_restart(self):
        d = AxisModel()
        c = ThreeDClient(d, FixedSolver(), 7000, 4, 3, 3, config())
        c.start()
        for _ in range(4): c.record_one(lambda r: None)
        d.fault = 256
        with self.assertRaises(RuntimeError): c.record_one(lambda r: None)
        self.assertEqual(d.consumed, 4)
        self.assertTrue(d.locked)
        self.assertFalse(d.read(motion.STATE) & 1)

    def test_final_extension_failure_still_attempts_legacy_stop(self):
        for operation in ('read', 'write'):
            d = AxisModel()
            c = ThreeDClient(d, FixedSolver(), 7000, 4, 3)
            original_stop = c.stop_direction_output
            def failing_revoke():
                if operation == 'read':
                    c.axes.read = lambda address: (_ for _ in ()).throw(OSError('STATE read failed'))
                else:
                    d.reg[motion.STATE] = 1
                    c.axes.revoke = lambda: (_ for _ in ()).throw(OSError('A4 revoke failed'))
                original_stop()
            c.stop_direction_output = failing_revoke
            con = Connection()
            ctx = mp.get_context('spawn')
            box = run_normal.Mailbox(ctx)
            box.poll()
            run_normal.normal_session(con, ctx.Event(), box, c,
                SimpleNamespace(mode='real', frames=1, clear_faults=0), state_factory=State3D)
            self.assertEqual(con.messages[-1][0], 'error')
            self.assertIn('STOP/drain', con.messages[-1][1]['error'])
            self.assertFalse(d.active)
            self.assertFalse(d.read(motion.STATE) & 1)
            self.assertIn((hw.SYS, 8), d.writes)

    def test_invalid_and_history_display(self):
        state = State3D()
        row = dict(frame=frame(), result=result())
        row.update(SpatialFilter().apply(row['frame'], row['result'], 7000))
        state.accept(row)
        line = display(state.snapshot())
        self.assertIn('WINDOW=1/20', line)
        self.assertIn('NO_OUTPUT', line)
        self.assertNotIn('AZIMUTH=0', line)
        self.assertTrue(line.isascii())

    def test_bounded_summary_and_debug_capacity(self):
        state = State3D()
        filt = SpatialFilter(4, 3)
        for n in range(1, 2001):
            fr, res = frame(n), result()
            row = dict(frame=fr, result=res)
            row.update(filt.apply(fr, res, 7000))
            state.accept(row)
        self.assertEqual(state.records, [])
        self.assertLess(len(json.dumps(state.snapshot())), 3000)
        debug = State3D(1)
        debug.accept(row)
        with self.assertRaises(RuntimeError): debug.accept(row)

    def test_cli_defaults_explicit_manual_and_bounded_debug(self):
        p = board_3d.parser()
        args = p.parse_args(['run'])
        self.assertEqual(args.axes, 'off')
        self.assertEqual(args.frames, 0)
        args = p.parse_args(['run', '--debug'])
        with self.assertRaises(ValueError): board_3d.run_options(args)
        man = p.parse_args(['manual', '--vertical', '110'])
        self.assertIsNone(man.horizontal)
        self.assertEqual(man.vertical, 110)

    def test_hwh_rejects_old_before_mmio(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'x.hwh'
            params = dict(DUAL_AXIS_ENABLE=1, AUDIO_ENABLE=1, LEVEL_ENABLE=1,
                          ACTUATOR_BOUND=1, CLK_FREQ_HZ=61440000, SERVO_MAX=360)
            def write():
                p.write_text('<SYSTEM><MODULE INSTANCE="ps_link" MODTYPE="bd_ps_link"><PARAMETERS>'+
                    ''.join('<PARAMETER NAME="%s" VALUE="%s"/>' % (k,v) for k,v in params.items())+
                    '</PARAMETERS></MODULE><MEMRANGE INSTANCE="ps_link" SLAVEBUSINTERFACE="S_AXI" '+
                    'MEMTYPE="REGISTER" BASEVALUE="0x40000000" HIGHVALUE="0x40000fff"/></SYSTEM>')
            write()
            self.assertEqual(board_3d.check_hwh(p), (0x40000000,4096))
            params['DUAL_AXIS_ENABLE'] = 0
            write()
            with self.assertRaises(ValueError): board_3d.check_hwh(p)

    def test_local_calibration_roundtrip_does_not_change_shared_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            original = '{"min_level":8000}'
            (p/'settings.local.json').write_text(original)
            board_3d.save_config(config(), p)
            self.assertEqual(board_3d.load_config(p), config())
            self.assertEqual((p/'settings.local.json').read_text(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
