"""PC自测：真实spawn/IPC配合假MMIO和假求解器；不代表ARM、C数值或板测。"""
import json
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'software/ps'))
import ps_client as hw
import run_capture as app
import run_smp as smp


class Device:
    """只仿真本次软件需要的寄存器副作用；不是RTL仿真模型。"""
    def __init__(self,output,fault=0):
        self.output=Path(output);self.fault=fault;self.sys=8
        self.queued=False;self.locked=False;self.pair=0;self.permit=False
    def read(self,address):
        if address==hw.MAGIC:return 0x5a5a2026
        if address==hw.ABI:return 0x10000
        if address==hw.FAULT:return self.fault
        if address==hw.SYS:return self.sys
        if address==hw.ACT:return int(self.permit)
        if address==hw.SEQ:return 1 if self.locked else 0
        if address==hw.STATUS:
            return 0x80010|int(self.locked)|(2 if self.queued else 0)|(8 if self.sys&2 else 0)
        if address==hw.FEATURE:return self.pair<<8
        return 0
    def write(self,address,value):
        if address==hw.SELECT:self.pair=value
        elif address==hw.FAULT:self.fault&=~value
        elif address==hw.SYS:
            self.sys=value
            if value&1:self.queued=True
        elif address==hw.ACT:
            if value==2:
                self.fault|=0x40;self.permit=False
                self.output.with_suffix('.stopped').write_text('STOP',encoding='utf-8')
            elif value==1:self.permit=True
            elif value==4:self.permit=False
            elif value==8:
                assert self.records()[0]['result']['direction_valid']==1
                self.output.with_suffix('.commanded').write_text('COMMIT',encoding='utf-8')
        elif address==hw.SNAP:
            if value==1:self.locked=True
            elif value==4:
                records=self.records()
                assert any('result' in r and r['frame']['sequence']==1 for r in records)
                if self.output.with_suffix('.commanded').exists():
                    assert any(r.get('action')=='commit_no_fault_observed' for r in records)
                self.output.with_suffix('.consumed').write_text('CONSUME',encoding='utf-8')
                self.queued=False;self.locked=False
    def records(self):
        return [json.loads(line) for line in self.output.read_text(encoding='utf-8').splitlines()
                if '"frame"' in line]


class Solver:
    def __init__(self,failure=None):self.failure=failure
    def solve(self,frame,config=None):
        if self.failure=='exception':raise ValueError('solver injected failure')
        return dict(bridge_status=-4 if self.failure=='bridge' else 0,direction_valid=1,
                    servo_cmd_valid=int(config is not None),servo_deg=90)


def fake_worker(connection,cancel,options,output):
    client=smp.InterruptibleClient(Device(output,options.initial_fault),Solver(options.solver_failure),cancel)
    smp.worker_session(connection,cancel,client,options,
                       [0,1,-100,100,0,180,180] if options.watchdog_ticks else None,
                       dict(worker_pid=__import__('os').getpid(),backend='fake'))


class SMPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.output=Path(self.tmp.name)/'frames.jsonl'
        self.context=mp.get_context('spawn');self.children=[]
    def tearDown(self):
        for worker,cancel,connection in self.children:
            cancel.set();connection.close();worker.join(1)
            if worker.is_alive():worker.terminate();worker.join(1)
        self.tmp.cleanup()
    def start(self,**overrides):
        values=dict(mode='real',frames=1,drain_existing=False,watchdog_ticks=None,
                    clear_faults=0,initial_fault=0,solver_failure=None)
        values.update(overrides);options=SimpleNamespace(**values)
        parent,child=self.context.Pipe();cancel=self.context.Event()
        worker=self.context.Process(target=fake_worker,args=(child,cancel,options,self.output))
        worker.start();child.close();self.children.append((worker,cancel,parent))
        return worker,cancel,parent
    def collect(self,worker,cancel,parent,sink=None):
        with self.output.open('a',encoding='utf-8') as handle:
            return smp.collect(parent,worker,cancel,sink or app.durable_sink(handle),{'backend':'fake'})
    def marker(self,kind):return self.output.with_suffix('.'+kind).exists()
    def test_spawn_save_before_consume(self):
        worker,cancel,parent=self.start()
        result=self.collect(worker,cancel,parent);worker.join(1)
        self.assertEqual(result['saved'],1);self.assertEqual(result['stats']['consumed'],1)
        self.assertTrue(result['stats']['max_service_ns']>0)
        self.assertTrue(self.marker('consumed'));self.assertFalse(self.marker('commanded'))
        self.assertEqual(worker.exitcode,0)
    def test_motion_has_result_then_commit_then_action_then_consume(self):
        worker,cancel,parent=self.start(watchdog_ticks=1000)
        self.collect(worker,cancel,parent);worker.join(1)
        self.assertTrue(self.marker('commanded'));self.assertTrue(self.marker('consumed'))
    def test_sink_failure_retains_frame(self):
        worker,cancel,parent=self.start()
        def fail(record):
            if 'frame' in record:raise OSError('disk full')
        with self.assertRaisesRegex(OSError,'disk full'):self.collect(worker,cancel,parent,fail)
        worker.join(1)
        self.assertTrue(self.marker('stopped'));self.assertFalse(self.marker('consumed'))
    def test_interrupt_retains_frame(self):
        worker,cancel,parent=self.start()
        def fail(record):
            if 'frame' in record:raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.collect(worker,cancel,parent,fail)
        worker.join(1)
        self.assertTrue(self.marker('stopped'));self.assertFalse(self.marker('consumed'))
    def test_action_log_failure_retains_already_commanded_frame(self):
        worker,cancel,parent=self.start(watchdog_ticks=1000)
        with self.output.open('a',encoding='utf-8') as handle:
            save=app.durable_sink(handle)
            def fail_action(record):
                if 'action' in record:raise OSError('action log full')
                save(record)
            with self.assertRaisesRegex(OSError,'action log full'):
                smp.collect(parent,worker,cancel,fail_action,{'backend':'fake'})
        worker.join(1)
        self.assertTrue(self.marker('commanded'));self.assertFalse(self.marker('consumed'))
        self.assertTrue(self.marker('stopped'))
    def advance_to_frame(self,parent):
        self.assertTrue(parent.poll(5));self.assertEqual(parent.recv()[0],'ready')
        self.assertTrue(parent.poll(1));startup=parent.recv();self.assertEqual(startup[2]['event'],'startup')
        parent.send(('saved',startup[1]))
        self.assertTrue(parent.poll(1));message=parent.recv()
        self.assertEqual(message[0],'record');self.assertIn('frame',message[2])
        return message
    def test_missing_ack_times_out_and_stops(self):
        worker,cancel,parent=self.start();self.advance_to_frame(parent)
        worker.join(1)
        self.assertFalse(worker.is_alive());self.assertTrue(self.marker('stopped'))
        self.assertFalse(self.marker('consumed'));self.assertEqual(parent.recv()[0],'error')
    def test_wrong_ack_stops(self):
        worker,cancel,parent=self.start();message=self.advance_to_frame(parent)
        parent.send(('saved',message[1]+1));worker.join(1)
        self.assertFalse(self.marker('consumed'));self.assertEqual(parent.recv()[0],'error')
    def test_eof_stops(self):
        worker,cancel,parent=self.start();self.advance_to_frame(parent)
        parent.close();worker.join(1)
        self.assertFalse(worker.is_alive());self.assertTrue(self.marker('stopped'))
        self.assertFalse(self.marker('consumed'))
    def test_solver_exception_reaches_host(self):
        worker,cancel,parent=self.start(solver_failure='exception')
        with self.assertRaisesRegex(RuntimeError,'solver injected failure'):self.collect(worker,cancel,parent)
        self.assertFalse(self.marker('consumed'));self.assertTrue(self.marker('stopped'))
    def test_bridge_failure_saved_but_retained(self):
        worker,cancel,parent=self.start(solver_failure='bridge')
        with self.assertRaisesRegex(RuntimeError,'C bridge error'):self.collect(worker,cancel,parent)
        self.assertIn('"bridge_status": -4',self.output.read_text(encoding='utf-8'))
        self.assertFalse(self.marker('consumed'))
    def test_historical_fault_requires_explicit_clear(self):
        worker,cancel,parent=self.start(initial_fault=2)
        with self.assertRaisesRegex(RuntimeError,'Existing fault 0x2'):self.collect(worker,cancel,parent)
        self.assertFalse(self.marker('consumed'))
    def test_explicit_fault_clear(self):
        worker,cancel,parent=self.start(initial_fault=2,clear_faults=2)
        self.collect(worker,cancel,parent);self.assertTrue(self.marker('consumed'))
    def test_cancel_after_ack_still_blocks_commit_and_consume(self):
        cancel=self.context.Event();client=smp.InterruptibleClient(Device(self.output),Solver(),cancel)
        cancel.set()
        with self.assertRaises(smp.Cancelled):client.command({}, {})
        with self.assertRaises(smp.Cancelled):client.consume({})
        self.assertFalse(self.marker('consumed'));self.assertFalse(self.marker('commanded'))
    def test_affinity_checks_and_restore(self):
        state=[{0,1}]
        def set_affinity(pid,cpus):state[0]=cpus
        with patch.object(smp.os,'sched_getaffinity',lambda pid:state[0],create=True), \
             patch.object(smp.os,'sched_setaffinity',set_affinity,create=True):
            self.assertEqual(smp.validate_cpus(0,1),{0,1})
            with self.assertRaises(RuntimeError):smp.validate_cpus(0,0)
            with self.assertRaises(RuntimeError):smp.validate_cpus(0,2)
            with smp.pinned(1):self.assertEqual(state[0],{1})
            self.assertEqual(state[0],{0,1})
    def test_calibration_invalid_before_hardware(self):
        valid=[90*256,1,-90*256,90*256,0,180,180]
        self.assertEqual(app.validate_servo_config(valid),valid)
        for index,value in [(0,8388608),(1,0),(2,-46081),(3,46080),(4,-1),(5,181),(6,512),(1,True)]:
            bad=valid[:];bad[index]=value
            with self.subTest(index=index,value=value),self.assertRaises(ValueError):
                app.validate_servo_config(bad)
    def test_fault_while_saving_stops_and_retains(self):
        device=Device(self.output);device.queued=True
        client=hw.Client(device,Solver())
        def save_then_fault(record):device.fault=2
        with self.assertRaisesRegex(RuntimeError,'New device fault'):client.record_one(save_then_fault)
        self.assertFalse(self.marker('consumed'));self.assertTrue(device.locked)
    def test_fault_frame_requires_explicit_drain(self):
        device=Device(self.output,fault=2);device.queued=True
        client=hw.Client(device,Solver())
        with self.assertRaisesRegex(RuntimeError,'while locking frame'):client.record_one(lambda r:None)
        self.assertTrue(device.locked);self.assertFalse(self.marker('consumed'))
        with self.output.open('a',encoding='utf-8') as handle:
            self.assertEqual(app.capture(client,app.durable_sink(handle),'real',1,True),1)
        self.assertTrue(self.marker('consumed'))


if __name__=='__main__':unittest.main()
