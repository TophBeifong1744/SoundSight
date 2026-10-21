"""New 3D RAM integration only; main queue/IPC regression remains authoritative.

Real native C bridge + spawn + RamQueue, using main's read-only frozen-slot
fixture. Windows temp files substitute for tmpfs: this is not an ARM/board run.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'software/tetra3d/tests'))
sys.path.insert(0,str(ROOT/'software/tests'))
import test_runtime_3d as fixture
from test_runtime_3d import note, Solver3D, close_lib, runtime, wire, synthetic
from test_buffered import BufferedDevice
from ram_queue import RamQueue,MAX_RECORD_BYTES
from recover_ram import recover
import run_buffered as shared
import run_buffered_3d as entry
import ps_client as hw
from volume_gate import LEVEL_CAP,LEVEL_VALID


class ThreeDDevice(BufferedDevice):
    def __init__(self,output,ram,events,measure=False,old=False,bad=None):
        super().__init__(output,ram); self.events=events; self.measure=measure; self.bad=bad
        self.features=wire(synthetic(45,30))['words']; self.queued=old
    def read(self,address):
        if address==hw.MAGIC and self.bad=='magic': return 0
        if address==hw.ABI: return 0x10001 if self.measure and self.bad!='abi' else 0x10000
        if address==hw.STATUS:
            return super().read(address) | (LEVEL_CAP|LEVEL_VALID if self.measure and self.bad!='cap' else 0)
        if address==hw.ENERGY: return 123456 if self.measure else 0
        if address in (hw.FEATURE,hw.PEAK,hw.LEFT,hw.RIGHT,hw.SECOND):
            return self.features[self.pair*5+(hw.FEATURE,hw.PEAK,hw.LEFT,hw.RIGHT,hw.SECOND).index(address)]
        return super().read(address)
    def write(self,address,value):
        note(self.events,'control:%d:%d'%(address,value))
        if address==hw.SNAP and value==4: note(self.events,'consume',self.sequence)
        if address==hw.ACT and value==2: note(self.events,'stop')
        if address in (hw.ANGLE,hw.WDT) or address==hw.ACT and value!=2:
            raise AssertionError('unexpected motion write')
        return super().write(address,value)


def worker(connection,abort,stop,library,geometry,output,ram,events,frames,measure,old):
    solver=Solver3D(library,geometry)
    try:
        client=runtime.Client3D(ThreeDDevice(output,ram,events,measure,old),runtime.SolverAdapter3D(solver),abort,measure)
        client.identify()
        shared.buffered_session(connection,abort,stop,client,
            SimpleNamespace(mode='real',frames=frames,drain_existing=False,clear_faults=0),
            dict(profile='TETRA40_3D',geometry=geometry,motion='DISABLED',worker_pid=os.getpid()))
    finally: close_lib(solver.lib)


class ObservedQueue(RamQueue):
    def __init__(self,*args,events,**kwargs): super().__init__(*args,**kwargs); self.events=events
    def put(self,record):
        ticket=super().put(record)
        note(self.events,'ram_complete',record.get('frame',{}).get('sequence'))
        return ticket


class Connection:
    def __init__(self,pipe,events): self.pipe=pipe; self.events=events; self.sequence=None
    def poll(self,timeout): return self.pipe.poll(timeout)
    def recv(self):
        message=self.pipe.recv()
        if message[0]=='record': self.sequence=message[2].get('frame',{}).get('sequence')
        return message
    def send(self,message):
        note(self.events,'queued_ack',self.sequence); return self.pipe.send(message)


def assert_ram_order(events,sequence):
    trace=[kind for _,kind,seq in sorted(events) if seq==sequence]
    required=['ram_complete','queued_ack','consume']
    if any(trace.count(kind)!=1 for kind in required): raise AssertionError('missing/duplicate RAM edge: '+repr(trace))
    indexes=[trace.index(kind) for kind in required]
    if indexes!=sorted(indexes): raise AssertionError('consume preceded complete RAM acceptance: '+repr(trace))


class Buffered3DTests(unittest.TestCase):
    setUpClass=classmethod(fixture.RuntimeTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.RuntimeTests.tearDownClass.__func__)
    all_events=fixture.RuntimeTests.all_events
    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.folder)
        self.root=Path(self.case.name); self.ram=self.root/'ram'; self.ram.mkdir()
        self.output=self.root/'frames.jsonl'; self.events=self.context.Queue()
    def tearDown(self):
        self.events.close(); self.events.join_thread(); self.case.cleanup()
    def session(self,frames=3,high=12,capacity=16,measure=False,old=False,disk_fail=False):
        parent,child=self.context.Pipe(); abort,stop=self.context.Event(),self.context.Event()
        release=threading.Event(); handle=self.output.open('x',encoding='utf-8')
        save=runtime.durable_sink_3d(handle,display=None)
        def writer(record):
            if not release.wait(5): raise TimeoutError('test writer gate was not released')
            if disk_fail and 'frame' in record: raise OSError('injected SD failure on 3D frame')
            save(record); note(self.events,'sd_fsync',record.get('frame',{}).get('sequence'))
        q=ObservedQueue(self.ram,capacity,writer,events=self.events)
        process=self.context.Process(target=worker,args=(child,abort,stop,str(self.library),self.geometry,
                    self.output,self.ram,self.events,frames,measure,old))
        process.start(); child.close(); q.start(); finish_error=None
        try:
            kind,result=shared.collect(Connection(parent,self.events),stop,q,high,{})
            process.join(3); self.assertFalse(process.is_alive(),'TIMEOUT_HANG: worker did not exit')
            self.assertEqual(process.exitcode,0)
            release.set()
            try: q.finish(3)
            except RuntimeError as exc: finish_error=exc
            events=self.all_events()
            rows=[json.loads(line) for line in self.output.read_text(encoding='utf-8').splitlines()]
            return kind,result,q,events,rows,finish_error
        finally:
            release.set(); abort.set(); parent.close(); process.join(1)
            if process.is_alive(): process.terminate(); process.join(1)
            if q.writer.is_alive(): q.writer.join(3)
            handle.close()
    def test_real_c_ram_acceptance_and_volume_remains_raw(self):
        kind,result,q,events,rows,error=self.session(measure=True)
        self.assertIsNone(error); self.assertEqual(kind,'done')
        self.assertEqual((result['stats']['consumed'],result['stats']['drained']),(3,2))
        frames=[r for r in rows if 'frame' in r]
        self.assertEqual(q.durable_frames,5)
        for row in frames:
            seq=row['frame']['sequence']; assert_ram_order(events,seq)
            self.assertEqual(row['result']['sequence'],seq)
            self.assertEqual((row['result']['bridge_status'],row['result']['direction_valid']),(0,1))
            self.assertAlmostEqual(row['result']['azimuth_deg'],45,delta=.03)
            self.assertAlmostEqual(row['result']['elevation_deg'],30,delta=.03)
            self.assertEqual(row['geometry'],self.geometry)
            self.assertEqual(row['direction_output'],{'valid':False,'reason':'raw_solver_only'})
            self.assertEqual((row['volume']['level_counts'],row['volume']['threshold_counts']),(123456,None))
            self.assertEqual(row['motion'],'DISABLED')
            self.assertLessEqual(len((json.dumps(row,ensure_ascii=False)+'\n').encode('utf-8')),MAX_RECORD_BYTES)
        self.assertEqual(MAX_RECORD_BYTES,16384)
        first_consume=min(t for t,k,s in events if k=='consume')
        first_disk=min(t for t,k,s in events if k=='sd_fsync')
        self.assertLess(first_consume,first_disk,'RAM mode must not wait for SD fsync')
    def test_high_water_stops_and_drains_two_complete_3d_tail_frames(self):
        kind,result,q,events,rows,error=self.session(frames=100,high=3,capacity=7)
        self.assertIsNone(error); self.assertEqual(kind,'done')
        self.assertEqual(result['host_stop_reason'],'queue_high_water')
        self.assertLess(result['stats']['consumed'],100); self.assertEqual(result['stats']['drained'],2)
        self.assertLessEqual(q.peak,7)
        seq=[r['frame']['sequence'] for r in rows if 'frame' in r]
        self.assertEqual(seq,list(range(1,len(seq)+1)))
        for sequence in seq: assert_ram_order(events,sequence)
    def test_disk_failure_preserves_full_3d_ram_records_for_recovery(self):
        kind,result,q,events,rows,error=self.session(disk_fail=True)
        self.assertIsInstance(error,RuntimeError); self.assertIn('injected SD failure',str(error))
        self.assertEqual(q.durable_frames,0); self.assertGreater(q.depth,0)
        recovered=self.root/'recovered.jsonl'
        self.assertGreater(recover(self.ram,recovered),0)
        frames=[json.loads(line) for line in recovered.read_text(encoding='utf-8').splitlines()]
        frames=[r for r in frames if 'frame' in r]
        self.assertEqual(len(frames),5)
        for row in frames:
            self.assertEqual(row['geometry'],self.geometry)
            self.assertEqual(len(row['frame']['words']),30)
            self.assertEqual(len(row['result']['pairs']),6)
        self.assertTrue(list(self.ram.glob('*.jsonl')),'recovery must retain RAM originals')
    def test_failed_start_does_not_drain_old_slots(self):
        kind,result,q,events,rows,error=self.session(old=True)
        self.assertIsNone(error); self.assertEqual(kind,'error')
        self.assertEqual((result['stats']['consumed'],result['stats']['drained']),(0,0))
        self.assertFalse(any(k=='consume' for _,k,_ in events))
        self.assertFalse(any('frame' in row for row in rows))
    def test_measure_level_bad_identity_never_writes_controls(self):
        for bad in ('magic','abi','cap'):
            device=ThreeDDevice(self.output,self.ram,self.events,True,bad=bad)
            messages=[]
            connection=SimpleNamespace(send=messages.append,close=lambda:None)
            options=SimpleNamespace(worker_cpu=1,lock_file='unused',library=self.library,measure_level=True)
            with patch.object(entry,'pinned',lambda cpu:contextlib.nullcontext()), \
                 patch.object(entry,'single_owner',lambda path:contextlib.nullcontext()), \
                 patch.object(entry,'Solver3D',lambda *args:self.solver), \
                 patch.dict(sys.modules,{'pynq':SimpleNamespace(MMIO=lambda *args:device)}), \
                 contextlib.redirect_stdout(io.StringIO()):
                entry.worker_main(connection,threading.Event(),threading.Event(),options,0,4096,self.geometry)
            self.assertEqual(messages[0][0],'error')
        self.assertFalse(self.all_events(),'identity rejection must issue zero MMIO writes')
    def test_buffered_cli_limits_startup_and_service_budgets(self):
        base=['--hwh','missing.hwh','--geometry',str(ROOT/'software/tetra3d/core/tetra40-nominal.json'),
              '--output','unused.jsonl','--mode','real']
        for extra in (['--queue-capacity','4'],['--high-water','64'],['--flush-timeout','0'],
                      ['--min-level','10'],['--horizontal-motion']):
            with self.subTest(extra=extra),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                entry.main(base+extra)
        self.assertIs(entry.shared,shared); self.assertEqual(shared.START_TIMEOUT,20.0)
        self.assertEqual(shared.QueuedBeforeConsume(SimpleNamespace(),threading.Event()).timeout,.25)
        self.assertEqual(shared.HOST_TIMEOUT,.75)
    def test_ram_order_checker_negative_canary(self):
        assert_ram_order([(0,'ram_complete',1),(1,'queued_ack',1),(2,'consume',1)],1)
        for events in ([(0,'consume',1),(1,'ram_complete',1),(2,'queued_ack',1)],
                       [(0,'queued_ack',1),(1,'consume',1)]):
            with self.assertRaises(AssertionError): assert_ram_order(events,1)


if __name__=='__main__': unittest.main(verbosity=2)