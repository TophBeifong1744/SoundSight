"""Real Linux IPC faults and STOP ownership, without hardware or model assets."""
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import sys
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'software/ps'))
sys.path.insert(0,str(ROOT/'software/tests'))
from speaker_process import ProcessSpeaker
from test_pcm_capture import Audio,Client,DMA,Clock,packet
from pcm_capture import capture


class Policy:
    info={'test':True}
    def prefix(self,role):return []


def stub(mode,fd):
    sock=socket.socket(fileno=fd)
    if mode=='startup_exit':return
    if mode=='startup_hang':time.sleep(10);return
    sock.send(b'R');count=0;origin=None
    while True:
        data=sock.recv(9000)
        if not data:return
        if data[:1]==b'S':origin=struct.unpack('<d',data[1:])[0]
        if data[:1]==b'P':
            count+=1
            if mode=='crash':os._exit(7)
            if mode=='bad_ack':sock.send(b'A'+struct.pack('<I',999));continue
            if mode=='bad_message':sock.send(b'?');continue
            if mode!='no_ack':sock.send(b'A'+struct.pack('<I',count))
        if data[:1]==b'F':
            passed,expected=struct.unpack('<?I',data[1:])
            result=dict(status='PASS',input_packets=count+(mode=='bad_count'),origin=origin,
                        results=[dict(eligible=True,state='target')],eligible_results=1,
                        pid=os.getpid(),expected=expected)
            sock.send(b'D'+json.dumps(result).encode());return


class ProcessTests(unittest.TestCase):
    def engine(self,mode='normal',**kw):
        e=ProcessSpeaker('.',1.,Policy(),worker_command=[sys.executable,'-B',__file__,'--stub',mode],**kw)
        self.addCleanup(e.close);return e

    def send(self,e,n):e.submit(packet(seq=n),dict(epoch=7,block_seq=n,sample_start=n*512))

    def wait_readable(self,e):
        self.assertTrue(select.select([e.sock],[],[],2)[0])

    def test_success_separate_pid_no_parent_thread_and_origin_preserved(self):
        before={t.ident for t in threading.enumerate()}
        e=self.engine();e.started(123.456)
        for n in range(5):self.send(e,n)
        r=e.finish(True)
        self.assertEqual(r['status'],'PASS');self.assertEqual(r['origin'],123.456)
        self.assertNotEqual(r['pid'],os.getpid());self.assertEqual(r['ipc']['frontend_taken'],5)
        self.assertEqual(before,{t.ident for t in threading.enumerate()})
        e.close();e.close();self.assertIsNotNone(e.p.poll())

    def test_credit_budget_is_not_returned_just_by_transport_receipt(self):
        e=self.engine('no_ack');e.started(0.)
        for n in range(32):
            self.send(e,n)
            # Permit kernel transport consumption; child deliberately sends no credit.
            time.sleep(.002)
        begin=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'CREDIT_OVERFLOW'):self.send(e,32)
        self.assertLess(time.monotonic()-begin,.1)
        self.assertEqual(e.acked,0);self.assertEqual(e.highwater,32)
        self.assertEqual(e.finish(False)['status'],'FAIL')

    def test_kernel_backpressure_is_nonblocking(self):
        e=self.engine();e.started(0.);os.kill(e.p.pid,signal.SIGSTOP)
        e.sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,8192)
        begin=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'BACKPRESSURE'):
            for n in range(32):self.send(e,n)
        self.assertLess(time.monotonic()-begin,.1)
        os.kill(e.p.pid,signal.SIGCONT)

    def test_packet_continuity_epoch_and_start_guard(self):
        e=self.engine()
        with self.assertRaises(ValueError):self.send(e,0)
        e.started(0.)
        with self.assertRaises(ValueError):self.send(e,1)
        self.send(e,0)
        with self.assertRaises(ValueError):e.submit(packet(seq=1),dict(epoch=8,block_seq=1,sample_start=512))
        with self.assertRaises(RuntimeError):e.started(0.)
        self.assertEqual(e.finish(False)['status'],'FAIL')

    def test_bad_control_messages_fail_closed(self):
        for mode in ('bad_ack','bad_message'):
            e=self.engine(mode);e.started(0.);self.send(e,0);self.wait_readable(e)
            with self.assertRaises(RuntimeError):self.send(e,1)
            e.close()

    def test_child_crash_stops_capture_and_halts_dma(self):
        e=self.engine('crash');audio,client,timer=Audio(),Client(),Clock()
        def sink(data,meta):
            e.submit(data,meta)
            if meta['block_seq']==0:e.p.wait(timeout=2)
        report,_=capture(client,audio,DMA(audio),7,3,timer,timer.sleep,
                         packet_sink=sink,started=e.started)
        self.assertEqual(report['result'],'FAIL');self.assertTrue(report['dma_halted'])
        self.assertFalse(client.running);self.assertEqual(e.finish(False)['status'],'FAIL')

    def test_failed_capture_invalidates_successful_child_scores(self):
        e=self.engine();e.started(0.);self.send(e,0);r=e.finish(False)
        self.assertEqual(r['status'],'FAIL');self.assertEqual(r['eligible_results'],0)
        self.assertFalse(r['results'][0]['eligible']);self.assertEqual(r['current_identity'],'insufficient')

    def test_mismatched_counts_cannot_pass(self):
        e=self.engine('bad_count');e.started(0.);self.send(e,0)
        self.assertEqual(e.finish(True)['error'],'SPEAKER_IPC_ACCOUNTING')

    def test_startup_failure_and_timeout_are_bounded(self):
        with self.assertRaises(RuntimeError):self.engine('startup_exit')
        with self.assertRaises(TimeoutError):self.engine('startup_hang',startup_timeout=.1)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--stub':stub(sys.argv[2],int(sys.argv[3]))
    else:unittest.main()
