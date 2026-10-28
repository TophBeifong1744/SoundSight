"""Manual PS client against an independent lease/register model, no sound/solver."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ps'))
import manual_servo as m

CFG=dict(front_deg=180,direction=1,min_deg=170,max_deg=190)

class Model:
    def __init__(self):
        self.t=0.;self.active=False;self.deadline=0.;self.writes=[]
        self.reg={m.MAGIC:0x5a5a2026,m.ABI:0x10001,m.SYS:8,m.STATUS:3<<18,m.FAULT:0,m.CAP:m.CAPABILITY}
        self.interrupt=False;self.stall=False
    def clock(self):return self.t
    def sleep(self,seconds):
        self.t+=1 if self.stall else seconds
        if self.interrupt:raise KeyboardInterrupt()
    def read(self,a):
        if self.active and self.t>=self.deadline:self.active=False;self.reg[m.FAULT]|=0x100
        if a==m.CONTROL:return int(self.active)
        return self.reg.get(a,0)
    def write(self,a,v):
        self.writes.append((a,v))
        if a==m.FAULT:self.reg[a]&=~v;return
        if a==m.CONTROL:
            if v==0:self.active=False;self.reg[m.FAULT]|=0x40
            elif v==1:
                assert self.reg[m.SYS]==8 and not self.active and not self.reg[m.FAULT]
                self.active=True;self.deadline=self.t+.75
            elif v==2:
                assert self.active
                limits=self.reg[m.LIMITS];assert (limits&511)<=self.reg[m.ANGLE]<=(limits>>16)
                self.deadline=self.t+.75
        else:self.reg[a]=v

class Tests(unittest.TestCase):
    def run_it(self,d,angle=180,seconds=.5):return m.calibrate(d,CFG,angle,seconds,d.clock,d.sleep)
    def test_no_audio_and_renewal_and_stop(self):
        d=Model();out=self.run_it(d,seconds=2)
        self.assertGreaterEqual(out['commits'],19);self.assertFalse(out['audio_started']);self.assertFalse(d.active)
        self.assertEqual(d.writes[-1],(m.CONTROL,0))
        self.assertEqual(set(a for a,v in d.writes),{m.LIMITS,m.ANGLE,m.CONTROL})
    def test_stop_marker_only_can_be_cleared(self):
        d=Model();d.reg[m.FAULT]=0x40;self.run_it(d)
        self.assertEqual(d.writes[0],(m.FAULT,0x40))
        d=Model();d.reg[m.FAULT]=0x48
        with self.assertRaises(RuntimeError):self.run_it(d)
        self.assertEqual(d.writes,[])
    def test_old_bit_never_reads_extension_or_writes(self):
        d=Model();d.reg[m.STATUS]=1<<19
        with self.assertRaisesRegex(RuntimeError,'bitstream'):self.run_it(d)
        self.assertEqual(d.writes,[])
    def test_capture_queue_drain_or_other_manual_refused(self):
        for reg,value in ((m.SYS,9),(m.SYS,10),(m.STATUS,(3<<18)|1),(m.STATUS,(3<<18)|0x8000)):
            d=Model();d.reg[reg]=value
            with self.assertRaises(RuntimeError):self.run_it(d)
            self.assertEqual(d.writes,[])
    def test_out_of_bounds_and_invalid_duration_no_write(self):
        for angle,seconds in ((169,1),(191,1),(True,1),(180,0),(180,float('nan')),(180,61)):
            d=Model()
            with self.assertRaises(ValueError):self.run_it(d,angle,seconds)
            self.assertEqual(d.writes,[])
    def test_ctrl_c_stops(self):
        d=Model();d.interrupt=True
        with self.assertRaises(KeyboardInterrupt):self.run_it(d)
        self.assertFalse(d.active);self.assertEqual(d.writes[-1],(m.CONTROL,0))
    def test_delayed_process_does_not_rearm(self):
        d=Model();d.stall=True
        with self.assertRaisesRegex(RuntimeError,'no automatic restart'):self.run_it(d,seconds=2)
        self.assertEqual(d.writes.count((m.CONTROL,1)),1)
        self.assertFalse(d.active);self.assertEqual(d.writes[-1],(m.CONTROL,0))
    def test_write_failure_still_requests_stop(self):
        d=Model();original=d.write
        def write(a,v):
            if a==m.CONTROL and v==2:raise IOError('injected')
            original(a,v)
        d.write=write
        with self.assertRaises(IOError):self.run_it(d)
        self.assertFalse(d.active);self.assertEqual(d.writes[-1],(m.CONTROL,0))

if __name__=='__main__':unittest.main()
