"""Recovery register protocol and panel latch tests. No PYNQ or hardware."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
for folder in ('software/ps', 'software/tetra3d/linux', 'software/screen'):
    sys.path.insert(0, str(ROOT/folder))
from capture_recovery import recover, idle
from ps_client import SYS, STATUS, FAULT
from backend import Backend
from ui import UI


class Model:
    def __init__(self, fault=0):
        self.ip = self
        self.reg = {0:0x5a5a2026, 0x6c:0x10001, 0xa0:0x44554101,
                    SYS:9, STATUS:3, FAULT:fault, 0x68:378, 0x58:1, 0xa8:0x301}
        self.frames = [dict(sequence=445), dict(sequence=446)]
        self.events=[]
    def identify(self):pass
    def read(self, address):return self.reg[address]
    def write(self, address, value):
        self.events.append(('write',address,value))
        assert (address,value)==(0xa4,0), 'Recovery must not arm/commit an axis'
        self.reg[0xa8]=0x300
    def disable(self):
        self.events.append(('STOP',))
        self.reg[SYS]=8;self.reg[0x58]=0;self.reg[FAULT]|=64
    def acquire(self):return self.frames[0]
    def consume(self, frame):
        self.events.append(('consume',frame['sequence']))
        self.frames.pop(0);self.reg[STATUS]=3 if self.frames else 0


class Audio:
    def __init__(self):
        self.raw=278;self.epoch=62;self.configured=62;self.published=282;self.rejected=1
        self.writes=[];self.fail_arm=False
    def read(self,a):
        return {0:0x10001,0x10:48000,0x14:0x04201801,0x18:512,0x1c:8224,
                0x0c:self.raw,0x30:self.epoch,0x24:self.published,0x20:self.rejected}[a]
    def write(self,a,v):
        self.writes.append((a,v))
        if a==8:
            assert self.raw & 8
            self.configured=v
        elif v==1:
            assert self.configured>self.epoch and self.raw & 8
            if self.fail_arm:raise OSError('injected arm write')
            self.raw=49;self.epoch=self.configured;self.published=self.rejected=0
        elif v==2:
            self.raw &= ~1
            if not self.raw & 2:self.raw |= 8


class DMA:
    def __init__(self,a):self.audio=a;self.ip=Mock();self.ip.read.return_value=4098;self.reset_count=0;self.fail=False
    def reset(self):
        self.reset_count+=1
        if self.fail:raise TimeoutError('reset failed')
        self.audio.raw=24|0x2000;self.ip.read.return_value=1
    def wait_for(self,check,message):
        if not check():raise TimeoutError(message)


class RecoveryTests(unittest.TestCase):
    def case(self,**kw):
        m=Model(**kw);a=Audio();d=DMA(a);rows=[]
        def save(row):
            rows.append(copy.deepcopy(row))
            m.events.append(('save',row['event']))
        return m,a,d,rows,save

    def test_preserve_then_consume_reset_new_epoch_and_idle_without_motion(self):
        m,a,d,rows,save=self.case()
        final=recover(m,a,d,lambda old:old+1,save)
        self.assertTrue(idle(final));self.assertEqual(final['audio']['epoch'],63)
        self.assertEqual([r['frame']['sequence'] for r in rows if 'frame'in r],[445,446])
        self.assertEqual(rows[0]['device']['audio']['errors'],1)
        self.assertLess(m.events.index(('save','retained_snapshot')),m.events.index(('consume',445)))
        self.assertEqual(d.reset_count,1)
        self.assertEqual(a.writes,[(4,2),(8,63),(4,1),(4,2)])

    def test_save_failure_retains_locked_snapshot_and_never_resets_audio(self):
        m,a,d,rows,save=self.case()
        def failure(row):
            if row['event']=='retained_snapshot':raise OSError('SD failed')
            save(row)
        with self.assertRaises(OSError):recover(m,a,d,lambda old:old+1,failure)
        self.assertEqual(len(m.frames),2);self.assertEqual(d.reset_count,0)
        self.assertFalse(m.reg[SYS]&1);self.assertFalse(m.reg[0xa8]&0x19)

    def test_unrelated_ps_fault_is_preserved_not_cleared(self):
        m,a,d,rows,save=self.case(fault=8)
        with self.assertRaisesRegex(RuntimeError,'UNEXPECTED_PS_FAULT'):
            recover(m,a,d,lambda old:old+1,save)
        self.assertEqual(m.reg[FAULT],72);self.assertEqual(d.reset_count,0)
        self.assertEqual(len(m.frames),2)

    def test_reset_failure_does_not_rearm_or_claim_recovery(self):
        m,a,d,rows,save=self.case();d.fail=True
        with self.assertRaises(TimeoutError):recover(m,a,d,lambda old:old+1,save)
        self.assertNotIn((4,1),a.writes)
        self.assertNotEqual(rows[-1]['event'],'recovered')

    def test_arm_write_failure_still_attempts_stop(self):
        m,a,d,rows,save=self.case();a.fail_arm=True
        with self.assertRaises(OSError):recover(m,a,d,lambda old:old+1,save)
        self.assertEqual(a.writes[-1],(4,2))

    def test_first_save_failure_still_stops_but_never_consumes_or_resets(self):
        m,a,d,rows,save=self.case()
        with self.assertRaises(OSError):recover(m,a,d,lambda old:old+1,Mock(side_effect=OSError('disk')))
        self.assertFalse(m.reg[SYS]&1);self.assertFalse(m.reg[0xa8]&0x19)
        self.assertEqual(len(m.frames),2);self.assertEqual(d.reset_count,0)

    def test_panel_checks_audio_and_requires_explicit_confirmation(self):
        m,a,d,rows,save=self.case();state=recover(m,a,d,lambda old:old+1,save)
        self.assertTrue(Backend.idle_state(state))
        bad=copy.deepcopy(state);bad['dma_status']=0x11
        self.assertFalse(Backend.idle_state(bad));self.assertFalse(idle(bad))
        for key,value in [('errors',1),('pending',True),('armed',True),('idle',False)]:
            bad=copy.deepcopy(state);bad['audio'][key]=value
            self.assertFalse(Backend.idle_state(bad))
        with tempfile.TemporaryDirectory() as temp:
            b=Backend(Path(temp),control=True,motion=True,demo=True);u=UI(b)
            b.session_failed=True;b.state='ERROR';b.stop_verified=False
            with patch.object(b,'_launch') as launch:
                u.action('ACK');launch.assert_not_called();self.assertEqual(u.modal,'RECOVER')
                u.action('CANCEL');launch.assert_not_called()
                u.action('ACK');u.action('RECOVER_CONFIRM')
                launch.assert_called_once_with(['recover-capture'],'recover-capture')
                self.assertFalse(b.stop_verified);self.assertEqual(u.axes,'off')

    def test_panel_recovery_requires_success_marker_and_single_idle_readback(self):
        m,a,d,rows,save=self.case();state=recover(m,a,d,lambda old:old+1,save)
        for success in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                b=Backend(Path(temp),control=True);b.operation='recover-capture'
                b.state='RUNNING';b.session_failed=True;b.recovery_requested=True
                b.capture_recovered=success;b.status_rows=[state];b.device_state=state
                b.proc=Mock();b.proc.poll.return_value=0;b.proc.stdout.fileno.return_value=9
                with patch('backend.os.read',return_value=b''),patch.object(b,'_group_alive',return_value=False):b.tick()
                self.assertEqual(b.state,'IDLE' if success else 'ERROR')
                self.assertEqual(b.stop_verified,success)
                self.assertEqual(b.session_failed,not success)


if __name__=='__main__':unittest.main(verbosity=2)
