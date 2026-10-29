"""No hardware: packet hooks, STOP ownership, settings, queue and PCM contracts."""
import array
import contextlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'software/ps'))
sys.path.insert(0,str(ROOT/'software/tests'))
import pcm_capture as pcm
import board_tools
import run_pcm
from speaker_settings import window_value,get_window,set_window,capture_blocks,import_settings
from live_speaker import pcm32_mic0,LiveSpeaker
from test_pcm_capture import Audio,Client,DMA,Clock,packet


class LiveTests(unittest.TestCase):
    def test_window_and_duration_rejected_before_hardware(self):
        for v in (0,.5,3,True,float('nan')):
            with self.assertRaises(ValueError):window_value(v)
        self.assertEqual(capture_blocks(10,2),938)
        for v in (0,2,11,float('inf')):
            with self.assertRaises(ValueError):capture_blocks(v,2)

    def test_s32_converter_exact_and_other_channels_ignored(self):
        values=[-8380220,-65536,-1,0,1,65536,8380219]+[0]*505
        raw=bytes(32)+b''.join(struct.pack('<4i',v,8388607,-8388608,88) for v in values)
        self.assertEqual(pcm32_mic0(raw).tobytes(),array.array('f',(v/8388608. for v in values)).tobytes())
        with self.assertRaises(ValueError):pcm32_mic0(raw[:-1])
        with self.assertRaises(ValueError):pcm32_mic0(bytes(32)+struct.pack('<4i',8388608,0,0,0)*512)
        with self.assertRaises(ValueError):pcm32_mic0(bytes(32)+struct.pack('<4i',8388607,0,0,0)*512)

    def test_callbacks_order_and_stop_on_consumer_failure(self):
        for failure in (False,True):
            audio,client,timer=Audio(),Client(),Clock();dma=DMA(audio);events=[]
            def start(t):events.append(('start',t));self.assertNotIn('START_NO_MOTION',client.actions)
            def consume(data,meta):
                events.append(('packet',meta['block_seq']))
                self.assertIn('START_NO_MOTION',client.actions)
                if failure:raise RuntimeError('injected input overflow')
            report,raw=pcm.capture(client,audio,dma,7,3,timer,timer.sleep,packet_sink=consume,started=start)
            self.assertEqual(report['result'],'FAIL' if failure else 'PASS')
            self.assertTrue(report['dma_halted']);self.assertFalse(client.running)
            self.assertEqual(events[0][0],'start')
            self.assertEqual(len(raw),1 if failure else 3)

    def test_bad_header_never_reaches_worker(self):
        audio,client,timer=Audio(),Client(),Clock();sink=Mock()
        report,raw=pcm.capture(client,audio,DMA(audio,'gap'),7,1,timer,timer.sleep,packet_sink=sink)
        sink.assert_not_called();self.assertEqual(report['result'],'FAIL');self.assertTrue(report['dma_halted'])

    def test_import_preserves_settings_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'old';dest=Path(tmp)/'new';source.mkdir();dest.mkdir()
            original={'min_level':1234,'window_frames':20,'min_valid':12}
            (source/'settings.local.json').write_text(json.dumps(original))
            (source/'horizontal.local.json').write_text(json.dumps(dict(front_deg=90,direction=-1,min_deg=20,max_deg=160)))
            (source/'pcm_epoch.local.json').write_text('{"last_epoch":17}')
            r=import_settings(source,dest);self.assertEqual(r['settings.local.json'],'COPIED')
            for p in source.iterdir():self.assertEqual(p.read_bytes(),(dest/p.name).read_bytes())
            self.assertEqual(import_settings(source,dest)['settings.local.json'],'ALREADY_IDENTICAL')
            (dest/'settings.local.json').write_text('{"min_level":777}')
            with self.assertRaises(ValueError):import_settings(source,dest)
            self.assertEqual(json.loads((dest/'settings.local.json').read_text())['min_level'],777)
            self.assertEqual(get_window(dest),1.5);set_window(dest,2);self.assertEqual(get_window(dest),2)

    def test_input_capacity_and_epoch_guards(self):
        # No backend processes: exercise the exact nonblocking DMA callback state.
        import queue,threading
        from stream_bench import Latest
        s=LiveSpeaker.__new__(LiveSpeaker)
        s.origin=0.;s.input_done=threading.Event();s.error=None;s.accepted=0;s.epoch=None
        s.input=queue.Queue(maxsize=32);s.input_highwater=0;s.error_lock=threading.Lock();s.stop=threading.Event();s.mail=Latest()
        for n in range(32):s.submit(packet(seq=n),dict(block_seq=n,sample_start=n*512,epoch=7))
        self.assertEqual(s.input_highwater,32)
        with self.assertRaisesRegex(RuntimeError,'OVERFLOW'):s.submit(packet(seq=32),dict(block_seq=32,sample_start=32*512,epoch=7))
        self.assertTrue(s.stop.is_set());self.assertEqual(s.input.qsize(),32)

    def test_old_cli_and_new_dispatch(self):
        with patch.object(board_tools,'ROOT',Path('/no-device')),patch('live_speaker.main',return_value=0) as run:
            self.assertEqual(board_tools.main(['speaker','--window','2','--seconds','10']),0)
            run.assert_called_once_with(Path('/no-device'),2.,10.)
        with patch('live_speaker.main') as run:
            with self.assertRaises(SystemExit):board_tools.main(['speaker','--horizontal-motion'])
            run.assert_not_called()


if __name__=='__main__':unittest.main()
