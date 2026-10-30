"""No hardware: threshold, capability, record preservation and command boundaries."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ps'))
from volume_gate import gate_record, VolumeClient, LEVEL_ABI, LEVEL_CAP, LEVEL_VALID
from ps_client import MAGIC, ABI, STATUS


def record(level=100, status=LEVEL_CAP | LEVEL_VALID | 1, fault=0, valid=1):
    return dict(frame=dict(sequence=1, status=status, energy=level, fault=fault, words=[0]*30, drops=0),
                result=dict(direction_valid=valid, angle_q8=-3328, api_status=0, bridge_status=0, reason=0),
                motion_requested=False)


class IP:
    def __init__(self, abi=LEVEL_ABI, status=LEVEL_CAP):
        self.values = {MAGIC: 0x5a5a2026, ABI: abi, STATUS: status}
        self.writes = []
    def read(self, address): return self.values[address]
    def write(self, address, value): self.writes.append((address, value))


class VolumeGateTests(unittest.TestCase):
    def test_below_equal_above(self):
        for level, valid in [(99,False), (100,True), (101,True)]:
            result = gate_record(record(level),100)['direction_output']
            self.assertEqual(result['valid'],valid)
            self.assertEqual(result['angle_q8'], -3328 if valid else None)

    def test_silence_not_zero_degree(self):
        result = gate_record(record(0),1)
        self.assertEqual(result['direction_output']['reason'], 'below_volume_threshold')
        self.assertIsNone(result['direction_output']['angle_q8'])

    def test_old_bit_rejected_without_writes(self):
        ip = IP(0x10000)
        with self.assertRaises(RuntimeError): VolumeClient(ip,None,100).identify()
        self.assertEqual(ip.writes,[])

    def test_missing_capability_rejected_without_writes(self):
        ip = IP(status=0)
        with self.assertRaises(RuntimeError): VolumeClient(ip,None,100).identify()
        self.assertEqual(ip.writes,[])

    def test_unavailable_level(self):
        for status in (1,LEVEL_CAP|1,LEVEL_VALID|1):
            self.assertEqual(gate_record(record(status=status),100)['direction_output']['reason'],'level_unavailable')

    def test_bad_measurement_range(self):
        for value in (-1,0x1000000):
            self.assertFalse(gate_record(record(value),100)['direction_output']['valid'])

    def test_measurement_only_never_grants_direction(self):
        out = gate_record(record(),None)
        self.assertEqual(out['volume']['level_counts'],100)
        self.assertEqual(out['direction_output']['reason'],'measurement_only')

    def test_bist_not_real_level(self):
        out = gate_record(record(100000, LEVEL_CAP|LEVEL_VALID|9),100)
        self.assertIsNone(out['volume']['level_counts'])
        self.assertFalse(out['direction_output']['valid'])

    def test_solver_rejection_not_overridden(self):
        self.assertEqual(gate_record(record(valid=0),10)['direction_output']['reason'],'solver_rejected')

    def test_fault_and_cancel(self):
        for r in (record(fault=64),record(status=LEVEL_CAP|LEVEL_VALID|(1<<20)|1)):
            self.assertEqual(gate_record(r,10)['direction_output']['reason'],'fault_or_cancelled')

    def test_raw_record_preserved(self):
        r = record()
        out = gate_record(r,101)
        self.assertIs(out['frame'],r['frame'])
        self.assertIs(out['result'],r['result'])
        self.assertNotIn('direction_output',r)
        self.assertEqual(out['result']['direction_valid'],1)

    def test_low_volume_is_saved_then_consumed(self):
        r = record(1)
        solver = Mock(); solver.solve.return_value = r['result']
        client = VolumeClient(IP(), solver, 100)
        client.acquire = Mock(return_value=r['frame'])
        client.read = Mock(return_value=0)
        order = []
        client.consume = lambda f: order.append('consume')
        def sink(saved):
            self.assertFalse(saved['direction_output']['valid'])
            self.assertEqual(saved['frame']['sequence'],1)
            order.append('save')
        client.record_one(sink)
        self.assertEqual(order,['save','consume'])

    def test_save_failure_preserves_low_volume_frame(self):
        r = record(1)
        solver = Mock(); solver.solve.return_value = r['result']
        client = VolumeClient(IP(),solver,100)
        client.acquire = Mock(return_value=r['frame'])
        client.consume = Mock(); client.stop = Mock()
        with self.assertRaises(OSError):
            client.record_one(Mock(side_effect=OSError('disk failure')))
        client.consume.assert_not_called(); client.stop.assert_called_once()

    def test_no_motion_calls(self):
        c = VolumeClient(IP(),None,100)
        for call in (lambda:c.arm(100),lambda:c.command({},{}),lambda:c.record_one(None,motion=True)):
            with self.assertRaises(ValueError): call()
        self.assertEqual(c.ip.writes,[])

    def test_invalid_threshold(self):
        for threshold in (0,-1,True,1.5,0x1000000):
            with self.assertRaises(ValueError): gate_record(record(),threshold)


if __name__ == '__main__': unittest.main()
