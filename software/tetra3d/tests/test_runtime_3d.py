"""Independent 3D integration checks. PC software only; never maps real MMIO.

Requirements: PS-MIGRATION.md, frozen snapshot ownership/STOP contract and the
independent analytic forward fixture in test_solver_3d_migration.py. No RTL,
ARM scheduling, acoustic accuracy or board STOP claim is made by this suite.
"""
import contextlib
import copy
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'software/tetra3d/linux'))
sys.path.insert(0, str(ROOT/'software/tetra3d/tests'))
import runtime_3d as runtime
import run_smp_3d as entry
import replay_capture_3d as replay_entry
import run_smp as shared
import ps_client as hw
from solver_3d import Solver3D, read_json, INFO, VALUES, PAIR
from test_solver_3d_migration import synthetic, wire, close_lib

PYTHON = [sys.executable, '-E', '-s', '-B', '-X', 'utf8']


def note(events, kind, seq=None):
    events.put((time.monotonic_ns(), kind, seq))


def assert_durable_order(events, sequence):
    """Acceptance checker: complete, strictly ordered edges for this frame."""
    trace = [kind for _, kind, seq in sorted(events) if seq == sequence]
    required = ['write', 'flush', 'fsync', 'ack', 'consume']
    if any(trace.count(kind) != 1 for kind in required):
        raise AssertionError('missing/duplicate durable edges: '+repr(trace))
    if [trace.index(kind) for kind in required] != sorted(trace.index(kind) for kind in required):
        raise AssertionError('consume preceded durability/ACK: '+repr(trace))


class Device:
    """Only frozen software-visible snapshot effects; not an RTL model."""
    def __init__(self, frame, events):
        self.frame = frame; self.events = events; self.queued = False
        self.locked = False; self.selected = 0; self.fault = 0; self.sys = 8
    def read(self, address):
        if address == hw.MAGIC: return 0x5a5a2026
        if address == hw.ABI: return 0x10000
        if address == hw.FAULT: return self.fault
        if address == hw.SYS: return self.sys
        if address == hw.STATUS:
            return (self.frame['status'] & 0xff100018) | int(self.locked) | (2 if self.queued else 0)
        if address == hw.SEQ: return self.frame['sequence'] if self.locked else 0
        if address in (hw.FEATURE, hw.PEAK, hw.LEFT, hw.RIGHT, hw.SECOND):
            return self.frame['words'][self.selected*5 + (hw.FEATURE,hw.PEAK,hw.LEFT,hw.RIGHT,hw.SECOND).index(address)]
        return 0
    def write(self, address, value):
        note(self.events, 'mmio:%d:%d'%(address,value))
        if address == hw.ACT:
            if value != 2: raise AssertionError('direction path wrote motion control')
            self.fault |= 0x40; note(self.events, 'stop')
        elif address in (hw.ANGLE, hw.WDT):
            raise AssertionError('direction path wrote actuator/watchdog')
        elif address == hw.FAULT: self.fault &= ~value
        elif address == hw.SYS:
            self.sys = value
            if value & 1: self.queued = True
        elif address == hw.SELECT: self.selected = value
        elif address == hw.SNAP:
            if value == 1: self.locked = True
            elif value == 4:
                note(self.events, 'consume', self.frame['sequence'])
                self.locked = False; self.queued = False


def integration_worker(connection, cancel, library, geometry, frame, events):
    """Real spawn/pipe, real C bridge, fake hardware; exactly one HW owner."""
    solver = Solver3D(library, geometry)
    try:
        note(events, 'solver_owner', os.getpid())
        client = runtime.Client3D(Device(frame, events), runtime.SolverAdapter3D(solver), cancel)
        options = SimpleNamespace(mode='real', frames=1, drain_existing=False,
                                  watchdog_ticks=None, clear_faults=0)
        shared.worker_session(connection, cancel, client, options, None,
                              dict(worker_pid=os.getpid(), profile='TETRA40_3D', motion='DISABLED'))
    finally:
        close_lib(solver.lib)


class TraceConnection:
    def __init__(self, connection, events, wrong=False):
        self.connection=connection; self.events=events; self.sequence=None; self.wrong=wrong
    def poll(self, timeout): return self.connection.poll(timeout)
    def recv(self):
        message=self.connection.recv()
        if message[0]=='record': self.sequence=message[2].get('frame',{}).get('sequence')
        return message
    def send(self, message):
        if message[0]=='saved':
            note(self.events,'ack',self.sequence)
            if self.wrong and self.sequence is not None: message=('saved',message[1]+1)
        return self.connection.send(message)


class TraceFile:
    def __init__(self, handle, events, failure=None):
        self.handle=handle; self.events=events; self.failure=failure; self.sequence=None
    def write(self, text):
        self.sequence=json.loads(text).get('frame',{}).get('sequence')
        if self.failure=='write' and self.sequence is not None: raise OSError('injected write failure')
        result=self.handle.write(text); note(self.events,'write',self.sequence); return result
    def flush(self):
        if self.failure=='flush' and self.sequence is not None: raise OSError('injected flush failure')
        self.handle.flush(); note(self.events,'flush',self.sequence)
    def fileno(self): return self.handle.fileno()


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='ss3-runtime-')
        cls.folder=Path(cls.temp.name)
        cls.library=cls.folder/('solver.dll' if os.name=='nt' else 'solver.so')
        cc=os.environ.get('SS_GCC') or shutil.which('gcc')
        if not cc: raise RuntimeError('TOOL_ENV_FAIL: set SS_GCC or add gcc to PATH')
        common=ROOT/'software/common'; core=ROOT/'software/tetra3d/core'
        cmd=[cc,'-std=c99','-O2','-Wall','-Wextra','-Wconversion','-Wshadow','-Werror','-pedantic','-shared']
        if os.name!='nt': cmd+=['-fPIC']
        cmd+=['-I'+str(p) for p in (common,common/'s1',core)]
        cmd += [str(p) for p in (common/'s1/doa_solver.c',core/'doa_solver_3d.c',core/'doa_geometry.c',
                                core/'doa_target_3d.c',ROOT/'software/tetra3d/linux/ss_solver_3d_bridge.c')]
        cmd+=['-lm','-o',str(cls.library)]
        compiled=subprocess.run(cmd,capture_output=True,text=True)
        if compiled.returncode: raise RuntimeError('COMPILE_ELAB_FAIL\n'+compiled.stdout+compiled.stderr)
        cls.geometry=read_json((core/'tetra40-nominal.json').read_text(encoding='utf-8'))
        cls.solver=Solver3D(cls.library,cls.geometry)
        cls.adapter=runtime.SolverAdapter3D(cls.solver)
        cls.context=mp.get_context('spawn')
    @classmethod
    def tearDownClass(cls):
        close_lib(cls.solver.lib); cls.temp.cleanup()
    def setUp(self): self.events=self.context.Queue()
    def tearDown(self): self.events.close(); self.events.join_thread()
    def all_events(self):
        items=[]
        while True:
            try: items.append(self.events.get(timeout=.1))
            except __import__('queue').Empty: return items
    def test_real_bridge_normal_poles_and_no_stale_angles(self):
        for az,el in [(45,30),(-45,-30),(0,90),(0,-90)]:
            result=self.adapter.solve(wire(synthetic(az,el)))
            self.assertEqual(result['bridge_status'],0); self.assertEqual(result['direction_valid'],1)
            self.assertEqual(result['elevation_valid'],1); self.assertEqual(result['servo_cmd_valid'],0)
            self.assertAlmostEqual(result['elevation_deg'],el,delta=.03)
            self.assertEqual(bool(result['azimuth_valid']),abs(el)!=90)
            if abs(el)!=90: self.assertAlmostEqual(result['azimuth_deg'],az,delta=.03)
            else: self.assertEqual(result['azimuth_q8'],0)
            self.assertTrue(set(INFO+VALUES+['bridge_status','pairs','sequence','geometry_revision','geometry_source'])<=set(result))
            self.assertTrue(all(set(PAIR)==set(pair) for pair in result['pairs']))
    def test_algorithm_reject_and_bridge_error_are_distinct(self):
        frame=wire(synthetic(45,30)); frame['status']|=8
        rejected=self.adapter.solve(frame)
        self.assertEqual((rejected['bridge_status'],rejected['direction_valid'],rejected['reason']),(0,0,5))
        frame['sequence']=0
        bad=self.adapter.solve(frame)
        self.assertEqual((bad['bridge_status'],bad['direction_valid']),(-1,0))
    def test_direct_motion_api_and_configuration_rejected(self):
        client=runtime.Client3D(Device(wire(synthetic(0,0)),self.events),self.adapter,threading.Event())
        for method,args in [(client.arm,(123,)),(client.command,({},{})),(client.record_one,(lambda r:None,))]:
            with self.subTest(method=method.__name__):
                with self.assertRaises((ValueError,RuntimeError)):
                    if method==client.record_one: method(*args,motion=True)
                    else: method(*args)
        with self.assertRaises(ValueError): self.adapter.solve(wire(synthetic(0,0)),[1])
        self.assertFalse(self.all_events())
    def test_geometry_validation_and_provenance(self):
        for change in ('source','channel','sample','finite'):
            g=copy.deepcopy(self.geometry)
            if change=='source': g['source_id']='bad source'
            if change=='channel': g['microphones'][1]['channel']=0
            if change=='sample': g['sample_rate_hz']=44100
            if change=='finite': g['microphones'][0]['xyz_mm'][0]=float('nan')
            loaded=[]; native=__import__('ctypes').CDLL
            def load(*args,**kwargs):
                lib=native(*args,**kwargs); loaded.append(lib); return lib
            try:
                with patch('solver_3d.C.CDLL',side_effect=load),self.subTest(change=change),self.assertRaises(ValueError):
                    Solver3D(self.library,g)
            finally:
                for lib in loaded: close_lib(lib)
        g=copy.deepcopy(self.geometry); g['provenance']='MEASURED'; g['position_error_mm']=.1
        solver=Solver3D(self.library,g)
        try: self.assertEqual(solver.solve(wire(synthetic(45,30)))['coordinates_measured'],1)
        finally: close_lib(solver.lib)
        self.assertEqual(self.solver.geometry['provenance'],'NOMINAL')
        g=self.solver.geometry; g['source_id']='mutated'
        self.assertEqual(self.solver.geometry['source_id'],self.geometry['source_id'])
    def test_replay_wrapped_raw_events_complete_record(self):
        frames=[wire(synthetic(45,30)),wire(synthetic(0,90)),wire(synthetic(0,0))]
        frames[-1]['status']|=8
        records=[{'event':'startup'},frames[0],{'frame':frames[1],'geometry':{'source_id':'old'}},
                 {'frame':{'sequence':7},'action':'commit_no_fault_observed'},frames[-1],{'event':'finished'}]
        saved=[]; count=runtime.replay([json.dumps(r)+'\n' for r in records],saved.append,self.adapter)
        self.assertEqual(count,3)
        for frame,record in zip(frames,saved):
            self.assertEqual(record['frame'],frame); self.assertEqual(record['geometry'],self.geometry)
            self.assertEqual(record['geometry_binding'],'EXPLICIT_RECOMPUTE')
            self.assertEqual(record['motion'],'DISABLED'); self.assertGreater(record['call_ns'],0)
        self.assertEqual(saved[-1]['result']['reason'],5)
        display=io.StringIO()
        with contextlib.redirect_stdout(display):
            for record in saved: runtime.display_3d(record)
        self.assertIn('az=UNOBSERVABLE',display.getvalue()); self.assertIn('REJECTED reason=5',display.getvalue())
        self.assertIn('NOMINAL/tetra40-nominal-v1',display.getvalue())
    def test_replay_bad_input_and_api_result_saved_before_stop(self):
        for text in ['{"sequence":1,"sequence":2}',json.dumps({'words':[]})]:
            saved=[]
            with self.assertRaises(ValueError): runtime.replay([text],saved.append,self.adapter)
            self.assertEqual(saved[0]['event'],'input_error'); self.assertEqual(saved[0]['raw_line'],text)
        bad=wire(synthetic(0,0)); bad['sequence']=0; saved=[]
        with self.assertRaises(RuntimeError): runtime.replay([json.dumps(bad),json.dumps(wire(synthetic(0,0)))],saved.append,self.adapter)
        self.assertEqual(len(saved),1); self.assertEqual(saved[0]['result']['bridge_status'],-1)
        with self.assertRaises(ValueError): runtime.replay([json.dumps({'event':'startup'})],lambda r:None,self.adapter)
    def run_ipc(self,frame=None,failure=None,wrong=False,cancel_after_ack=False):
        frame=frame or wire(synthetic(45,30)); parent,child=self.context.Pipe(); cancel=self.context.Event()
        worker=self.context.Process(target=integration_worker,args=(child,cancel,str(self.library),self.geometry,frame,self.events))
        worker.start(); child.close(); error=None
        real_fsync=os.fsync; path=self.folder/('ipc-%s.jsonl'%time.monotonic_ns())
        try:
            with path.open('w',encoding='utf-8') as handle:
                wrapped=TraceFile(handle,self.events,failure)
                def sync(fd):
                    if failure=='fsync' and wrapped.sequence is not None: raise OSError('injected fsync failure')
                    real_fsync(fd); note(self.events,'fsync',wrapped.sequence)
                connection=TraceConnection(parent,self.events,wrong)
                if cancel_after_ack:
                    send=connection.send
                    def send_cancel(message):
                        if connection.sequence is not None: cancel.set()
                        return send(message)
                    connection.send=send_cancel
                with patch.object(runtime.os,'fsync',sync):
                    try: result=shared.collect(connection,worker,cancel,runtime.durable_sink_3d(wrapped,display=None),{})
                    except BaseException as exc: error=exc; result=None
            cancel.set(); worker.join(3)
            self.assertFalse(worker.is_alive(),'TIMEOUT_HANG: integration worker did not exit')
            self.assertEqual(worker.exitcode,0)
            events=self.all_events(); records=[read_json(line) for line in path.read_text(encoding='utf-8').splitlines()]
            return result,error,events,records
        finally:
            cancel.set(); parent.close()
            if worker.is_alive(): worker.terminate(); worker.join(2)
            path.unlink(missing_ok=True)
    def test_real_ipc_fsync_ack_consume_order(self):
        result,error,events,records=self.run_ipc()
        self.assertIsNone(error); self.assertEqual(result['saved'],1)
        assert_durable_order(events,100)
        owners=[seq for _,kind,seq in events if kind=='solver_owner']
        self.assertEqual(len(owners),1); self.assertNotEqual(owners[0],os.getpid())
        self.assertEqual(records[1]['geometry'],self.geometry)
        self.assertEqual(records[1]['frame']['sequence'],records[1]['result']['sequence'])
    def test_real_ipc_storage_failures_no_ack_or_consume(self):
        for failure in ('write','flush','fsync'):
            with self.subTest(failure=failure):
                _,error,events,_=self.run_ipc(failure=failure)
                self.assertIsInstance(error,OSError)
                self.assertFalse(any(kind in ('consume','ack') and seq==100 for _,kind,seq in events))
                self.assertTrue(any(kind=='stop' for _,kind,_ in events))
    def test_real_ipc_wrong_ack_and_cancel_retain(self):
        for options in ({'wrong':True},{'cancel_after_ack':True}):
            with self.subTest(options=options):
                _,error,events,_=self.run_ipc(**options)
                self.assertIsInstance(error,RuntimeError)
                self.assertFalse(any(kind=='consume' for _,kind,_ in events))
                self.assertTrue(any(kind=='stop' for _,kind,_ in events))
    def test_real_ipc_algorithm_reject_consumed_bridge_error_retained(self):
        frame=wire(synthetic(45,30)); frame['status']|=8
        result,error,events,records=self.run_ipc(frame)
        self.assertIsNone(error); self.assertEqual(result['saved'],1); assert_durable_order(events,100)
        self.assertEqual(records[1]['result']['reason'],5)
        frame=wire(synthetic(45,30)); frame['words'][1]=16777216
        _,error,events,records=self.run_ipc(frame)
        self.assertIsInstance(error,RuntimeError)
        self.assertGreater(records[1]['result']['bridge_status'],0)
        self.assertFalse(any(kind=='consume' for _,kind,_ in events))
    def test_acceptance_checker_negative_canaries(self):
        valid=[(i,kind,100) for i,kind in enumerate(('write','flush','fsync','ack','consume'))]
        assert_durable_order(valid,100)
        for kinds in [('write','consume','flush','fsync','ack'),('write','flush','ack','consume'),
                      ('write','flush','fsync','ack','consume','consume')]:
            with self.subTest(kinds=kinds),self.assertRaises(AssertionError):
                assert_durable_order([(i,kind,100) for i,kind in enumerate(kinds)],100)
    def test_cli_no_motion_and_explicit_mode_geometry(self):
        base=['--hwh','x.hwh','--geometry',str(ROOT/'software/tetra3d/core/tetra40-nominal.json'),'--output','x.jsonl']
        parser=entry.argument_parser()
        for extra in ([],['--mode','bist-pass'],['--mode','real','--horizontal-motion'],['--mode','real','--watchdog-ticks','1']):
            with self.subTest(extra=extra),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                args=parser.parse_args(base+extra); entry.prepare_args(args,parser)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit): parser.parse_args(['--hwh','x','--output','x'])
        args=parser.parse_args(base+['--mode','real']); self.assertEqual(entry.prepare_args(args,parser),self.geometry)
        self.assertEqual((args.host_cpu,args.worker_cpu,args.lock_file),(0,1,'/tmp/soundsight-ps-owner.lock'))
        self.assertEqual(shared.ACK_TIMEOUT,.25)
    def test_quiet_full_log_no_host_solver_or_mmio(self):
        frame=wire(synthetic(45,30)); record=dict(frame=frame,result=self.adapter.solve(frame),geometry=self.geometry)
        class Connection:
            def __init__(self): self.messages=[('ready',{}),('record',1,record),('done',{'saved':1})]; self.sent=[]
            def poll(self,timeout): return bool(self.messages)
            def recv(self): return self.messages.pop(0)
            def send(self,message): self.sent.append(message)
            def close(self): pass
        class Worker:
            def __init__(self,**kwargs): self.kwargs=kwargs
            def start(self): pass
        for quiet in (False,True):
            path=self.folder/('quiet-%s.jsonl'%quiet); connection=Connection()
            context=SimpleNamespace(Pipe=lambda:(connection,Connection()),Event=threading.Event,Process=Worker)
            output=io.StringIO()
            with patch.object(entry.mp,'get_context',lambda mode:context),patch.object(shared,'validate_cpus'), \
                 patch.object(shared,'pinned',lambda cpu:contextlib.nullcontext()),patch.object(shared,'finish_worker'), \
                 patch.object(entry,'Solver3D',side_effect=AssertionError('host created solver')), \
                 patch.object(entry.os,'sched_getaffinity',lambda pid:{0,1},create=True), \
                 contextlib.redirect_stdout(output):
                argv=['--hwh',str(ROOT/'document/evidence/inherited/ps/bd_preparation/interface.hwh'),
                      '--geometry',str(ROOT/'software/tetra3d/core/tetra40-nominal.json'),
                      '--output',str(path),'--mode','real']+(['--quiet'] if quiet else [])
                self.assertEqual(entry.main(argv),0)
            rows=[read_json(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0],record); self.assertEqual(connection.sent,[('saved',1)])
            self.assertEqual('3D frame=' in output.getvalue(),not quiet)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError),patch.object(shared,'validate_cpus'),patch.object(entry.mp,'get_context',lambda mode:context): entry.main(argv)
            self.assertEqual(path.read_bytes(),original); path.unlink()


if __name__=='__main__':
    unittest.main(verbosity=2)