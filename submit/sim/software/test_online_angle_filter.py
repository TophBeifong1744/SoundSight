"""在线门限/窗口/圆周边界/停止与保存顺序；仅假硬件，不访问PYNQ。"""
import copy
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ps'))
from angle_filter import OnlineAngleFilter, circular_mean
from volume_gate import VolumeClient, gate_record, LEVEL_CAP, LEVEL_VALID
import run_buffered


def record(seq, angle=10, level=1000, valid=True, fault=0, extra_status=0):
    return dict(frame=dict(sequence=seq, energy=level, status=LEVEL_CAP | LEVEL_VALID | 1 | extra_status,
                           fault=fault, drops=0, words=[0]*30),
                result=dict(angle_q8=round(angle*256), direction_valid=int(valid), api_status=0,
                            bridge_status=0, reason=0 if valid else 1), motion_requested=False)


def feed(f, angles, start=1, **kwargs):
    return [f.apply(gate_record(record(start+i, a or 0, valid=a is not None, **kwargs), 1000))
            for i, a in enumerate(angles)]


class OnlineTests(unittest.TestCase):
    def test_twentieth_frame_only_and_incomplete(self):
        rows = feed(OnlineAngleFilter(), [10]*21)
        self.assertEqual([r['frame']['sequence'] for r in rows if r['direction_output']['valid']], [20])
        self.assertAlmostEqual(rows[19]['direction_output']['angle_deg'], 10)
        self.assertIsNone(rows[20]['direction_output']['angle_q8'])

    def test_wrap_is_not_zero(self):
        row = feed(OnlineAngleFilter(), [179]*10+[-179]*10)[-1]
        self.assertAlmostEqual(abs(row['direction_output']['angle_deg']), 180)

    def test_spikes_removed(self):
        row = feed(OnlineAngleFilter(), [-13]*18+[-90]*2)[-1]
        self.assertAlmostEqual(row['direction_output']['angle_deg'], -13)
        self.assertEqual(row['angle_filter']['inlier_count'], 18)

    def test_split_and_small_majority_rejected(self):
        for angles in ([0]*10+[90]*10, [0]*12+[90]*8, [0]*11+[None]*9):
            row = feed(OnlineAngleFilter(), angles)[-1]
            self.assertFalse(row['direction_output']['valid'])
            self.assertIsNone(row['direction_output']['angle_deg'])

    def test_twelve_of_twenty_valid_can_pass(self):
        row = feed(OnlineAngleFilter(), [20]*12+[None]*8)[-1]
        self.assertTrue(row['direction_output']['valid'])
        self.assertFalse(row['frame_direction']['valid'])
        self.assertAlmostEqual(row['direction_output']['angle_deg'], 20)

    def test_deadband_accumulates_against_last_output(self):
        rows = feed(OnlineAngleFilter(), [0]*20+[2]*20+[3]*20+[4]*20+[80]*20)
        outputs = [rows[i]['direction_output'] for i in (19,39,59,79,99)]
        self.assertEqual([o['updated'] for o in outputs], [True,False,True,False,True])
        self.assertEqual([round(o['angle_deg']) for o in outputs], [0,0,3,3,80])

    def test_deadband_across_wrap(self):
        rows = feed(OnlineAngleFilter(), [179]*20+[-179]*20+[-177]*20)
        self.assertFalse(rows[39]['direction_output']['updated'])
        self.assertTrue(rows[59]['direction_output']['updated'])

    def test_silence_resets_window_and_target(self):
        f = OnlineAngleFilter()
        feed(f, [10]*39)
        quiet = f.apply(gate_record(record(40, level=999),1000))
        self.assertEqual(quiet['direction_output']['reason'], 'below_volume_threshold')
        self.assertIsNone(quiet['direction_output']['angle_deg'])
        rows = feed(f, [11]*20,41)
        self.assertFalse(any(r['direction_output']['valid'] for r in rows[:-1]))
        self.assertTrue(rows[-1]['direction_output']['updated'])
        self.assertAlmostEqual(rows[-1]['direction_output']['angle_deg'], 11)

    def test_fault_cancel_bist_missing_level_reset(self):
        for changed in (record(20, fault=64),record(20, extra_status=1<<20),
                        record(20, extra_status=8)):
            f = OnlineAngleFilter(); feed(f,[10]*19)
            out = f.apply(gate_record(changed,1000))
            self.assertFalse(out['direction_output']['valid'])
            self.assertEqual(f.count,0)
        f = OnlineAngleFilter(); feed(f,[10]*19)
        r=record(20); r['frame']['status']=1
        self.assertFalse(f.apply(gate_record(r,1000))['direction_output']['valid'])
        self.assertEqual(f.count,0)

    def test_gap_duplicate_and_reversal_clear_partial(self):
        for seq in (19,21,1):
            f=OnlineAngleFilter(); feed(f,[10]*19)
            out=f.apply(gate_record(record(seq),1000))
            self.assertTrue(out['angle_filter']['sequence_reset'])
            self.assertFalse(out['direction_output']['valid'])
            self.assertEqual(out['angle_filter']['frame_count'],1)

    def test_rejected_window_does_not_publish_old_target(self):
        rows=feed(OnlineAngleFilter(),[10]*20+[None]*20)
        self.assertTrue(rows[19]['direction_output']['valid'])
        self.assertFalse(rows[-1]['direction_output']['valid'])
        self.assertIsNone(rows[-1]['direction_output']['angle_deg'])

    def test_stop_clears_and_tail_cannot_emit(self):
        f=OnlineAngleFilter(); feed(f,[10]*19); f.stop()
        rows=feed(f,[10]*21,20)
        self.assertTrue(all(r['direction_output']['reason']=='stopped_or_drain' for r in rows))

    def test_measurement_only_and_raw_preserved(self):
        raw=record(1); original=copy.deepcopy(raw)
        out=OnlineAngleFilter().apply(gate_record(raw,None))
        self.assertEqual(raw,original)
        self.assertFalse(out['direction_output']['valid'])
        self.assertEqual(out['result'],raw['result'])

    def test_undefined_mean(self):
        self.assertIsNone(circular_mean([0,180]))

    def test_solver_error_cannot_finish_window(self):
        for key in ('api_status','bridge_status'):
            f=OnlineAngleFilter(); feed(f,[10]*19)
            r=record(20);r['result'][key]=1
            out=f.apply(gate_record(r,1000))
            self.assertEqual(out['direction_output']['reason'],'solver_error')
            self.assertEqual(f.count,0)

    def test_client_processes_once_and_saves_before_consume(self):
        client=VolumeClient(Mock(),Mock(),1000,angle_filter=True)
        rows=[record(i) for i in range(1,21)]
        client.acquire=Mock(side_effect=[r['frame'] for r in rows])
        client.solver.solve=Mock(side_effect=[r['result'] for r in rows])
        client.read=Mock(return_value=0)
        saved=[]
        def consume(frame):
            self.assertEqual(saved[-1]['frame']['sequence'],frame['sequence'])
        client.consume=consume
        for _ in rows:
            returned=client.record_one(saved.append)
            self.assertIs(returned,saved[-1])
        self.assertEqual(sum(r['direction_output']['valid'] for r in saved),1)
        self.assertTrue(saved[-1]['direction_output']['valid'])
        self.assertTrue(all(not r['motion_requested'] for r in saved))
        client.ip.write.assert_not_called()

    def test_save_failure_retains_slot(self):
        client=VolumeClient(Mock(),Mock(),1000,angle_filter=True)
        r=record(1);client.acquire=Mock(return_value=r['frame'])
        client.solver.solve=Mock(return_value=r['result'])
        client.consume=Mock();client.stop=Mock()
        with self.assertRaises(OSError):
            client.record_one(Mock(side_effect=OSError('RAM full')))
        client.consume.assert_not_called();client.stop.assert_called_once()

    def test_cli_requires_volume_and_forbids_motion(self):
        args=['--hwh','missing.hwh','--output','unused.jsonl','--mode','real']
        with self.assertRaises(SystemExit):run_buffered.main(args+['--angle-filter'])
        with self.assertRaises(ValueError):VolumeClient(Mock(),Mock(),angle_filter=True)
        c=VolumeClient(Mock(),Mock(),1000,angle_filter=True)
        for call in (lambda:c.arm(10),lambda:c.command({},{}),lambda:c.record_one(None,motion=True)):
            with self.assertRaises(ValueError):call()
        c.ip.write.assert_not_called()

    def test_session_stops_filter_before_tail(self):
        # Real session orchestration, real VolumeClient/filter, fake MMIO and IPC.
        client=VolumeClient(Mock(),Mock(),1000,angle_filter=True)
        client.start=Mock(); client.disable=Mock()
        rows=[record(i) for i in range(1,22)]
        client.acquire=Mock(side_effect=[r['frame'] for r in rows])
        client.solver.solve=Mock(side_effect=[r['result'] for r in rows])
        client.consume=Mock()
        client.read=lambda a: (1 if client.consume.call_count==20 else 0) if a==52 else 0
        class Connection:
            records=[]
            ticket=None
            def send(self,message):
                if message[0]=='record':
                    self.ticket=message[1];self.records.append(message[2])
            def poll(self,t):return True
            def recv(self):return ('queued',self.ticket)
            def close(self):pass
        conn=Connection()
        opts=SimpleNamespace(mode='real',frames=20,clear_faults=0,drain_existing=False,angle_filter=True)
        run_buffered.buffered_session(conn,threading.Event(),threading.Event(),client,opts,{})
        frames=[r for r in conn.records if 'frame' in r]
        self.assertEqual(len(frames),21)
        self.assertTrue(frames[19]['direction_output']['valid'])
        self.assertEqual(frames[20]['direction_output']['reason'],'stopped_or_drain')


if __name__=='__main__':unittest.main()
