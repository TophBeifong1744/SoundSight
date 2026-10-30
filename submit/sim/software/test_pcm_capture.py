"""Independent packet fixtures and fault models; no PYNQ or board access."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave
import contextlib
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ps'))
import pcm_capture as app
from run_pcm import next_epoch
import run_pcm
import board_tools
from ps_client import SYS, STATUS, FAULT, DROP


def packet(epoch=7, seq=0, flags=0):
    # mic0 positive, mic1 negative, mic2 positive full scale, mic3 negative full scale.
    return struct.pack('<8I', 0x43505353, 0x00200001, epoch, seq,
                       seq * 512 & 0xffffffff, seq >> 23, (flags << 16) | 512, 8192) + \
        struct.pack('<4i', 123, -456, 8388607, -8388608) * 512


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): self.now += .001; return self.now
    def sleep(self, seconds): self.now += seconds


class Audio:
    def __init__(self):
        self.status = 24
        self.published = 0
        self.epoch = 0
        self.writes = []
    def read(self, address):
        return {0: 0x10001, 0x0c: self.status, 0x10: 48000, 0x14: 0x04201801,
                0x18: 512, 0x1c: 8224, 0x20: 0, 0x24: self.published,
                0x30: self.epoch}[address]
    def write(self, address, value):
        self.writes.append((address, value))
        if address == 8: self.epoch = value
        elif value == 1: self.status = 49
        elif value == 2: self.status = (self.status & 0xff00) | 28  # partial tail at STOP


class Client:
    def __init__(self):
        self.fault = 0
        self.running = False
        self.old_frame = False
        self.actions = []
    def identify(self): pass
    def read(self, address):
        return {0x80: 0x10001, SYS: 9 if self.running else 8,
                STATUS: 2 if self.old_frame else 0, 0x58: 0, 0x74: 0,
                FAULT: self.fault, DROP: 0}[address]
    def disable(self): self.running = False; self.fault |= 64; self.actions.append('STOP')
    def start(self, clear_faults):
        assert clear_faults == 64
        self.running = True; self.fault = 0; self.actions.append('START_NO_MOTION')


class DMA:
    def __init__(self, audio, failure=None):
        self.audio = audio
        self.failure = failure
        self.submitted = 0
        self.reset_count = 0
        self.ip = Mock()
        self.ip.read.return_value = 1
    def reset(self):
        self.reset_count += 1
        if self.failure == 'reset' and self.reset_count == 2:
            raise TimeoutError('injected reset failure')
    def start(self): pass
    def wait_for(self, check, message):
        if not check(): raise TimeoutError(message)
    def submit(self): self.submitted += 1
    def completed(self):
        if self.failure == 'dma': raise RuntimeError('injected slave error')
        if self.failure == 'overflow': self.audio.status |= 1 << 8; return False
        if self.failure == 'timeout': return False
        if self.failure == 'interrupt': raise KeyboardInterrupt()
        return True
    def take(self):
        self.audio.published += 1
        return packet(self.audio.epoch, self.submitted - 1 + int(self.failure == 'gap'))


class PCMTests(unittest.TestCase):
    def hwh(self, path):
        import xml.etree.ElementTree as ET
        tree = ET.Element('SYSTEM')
        for name, kind, base, size in [('audio_capture', 'bd_audio_capture', 0x43c00000, 4096),
                                       ('axi_dma_audio', 'axi_dma', 0x40400000, 65536),
                                       ('compute', 'bd_clean_compute', 0, 0), ('ps_link', 'bd_ps_link', 0, 0)]:
            m = ET.SubElement(tree, 'MODULE', INSTANCE=name, MODTYPE=kind)
            params = {'AUDIO_ENABLE': '1'}
            if name == 'axi_dma_audio':
                params = dict(C_INCLUDE_SG='0', C_INCLUDE_MM2S='0', C_INCLUDE_S2MM='1',
                              C_INCLUDE_S2MM_DRE='0', C_S_AXIS_S2MM_TDATA_WIDTH='32',
                              C_M_AXI_S2MM_DATA_WIDTH='64', C_SG_LENGTH_WIDTH='16')
            for k, v in params.items(): ET.SubElement(m, 'PARAMETER', NAME=k, VALUE=v)
            if size: ET.SubElement(tree, 'MEMRANGE', INSTANCE=name, MEMTYPE='REGISTER',
                                   BASEVALUE=hex(base), HIGHVALUE=hex(base+size-1))
        ET.ElementTree(tree).write(path)

    def test_hwh_rejects_old_or_incompatible_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.hwh'; self.hwh(path)
            self.assertEqual(app.check_hwh(path)['audio_capture'], (0x43c00000, 4096))
            original = path.read_text()
            for before, after in [('audio_capture', 'missing'), ('0x40400000', '0x40500000'),
                                  ('NAME="AUDIO_ENABLE" VALUE="1"', 'NAME="AUDIO_ENABLE" VALUE="0"'),
                                  ('NAME="C_INCLUDE_SG" VALUE="0"', 'NAME="C_INCLUDE_SG" VALUE="1"')]:
                path.write_text(original.replace(before, after))
                with self.subTest(before=before), self.assertRaises(ValueError): app.check_hwh(path)

    def test_pcm_check_is_read_only_and_does_not_allocate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.hwh(root/'soundsight.hwh')
            ps, dma, audio = Mock(), Mock(), Audio()
            ps.read.return_value = 0x10001
            dma.read.return_value = 1
            overlay = Mock(); overlay.is_loaded.return_value = True
            mmio = lambda base, size: {0x40000000: ps, 0x40400000: dma, 0x43c00000: audio}[base]
            with patch.object(board_tools, 'hwh_check', return_value=(0x40000000,4096)), \
                 patch.object(board_tools, 'load_api', return_value=(overlay, Mock(), Mock(), mmio, 33.333333)), \
                 patch.object(board_tools, 'clock_check'), patch.object(board_tools, 'clock_ready'), \
                 patch.object(board_tools, 'device_state', return_value={'fault': 0}), \
                 patch.object(run_pcm, 'single_owner', return_value=contextlib.nullcontext()):
                self.assertEqual(run_pcm.main(True, root=root), 0)
            ps.write.assert_not_called(); dma.write.assert_not_called()
            overlay.download.assert_not_called()
            self.assertEqual(audio.writes, [])
            self.assertFalse((root/'logs').exists())

    def test_signed_extremes_and_channels(self):
        self.assertEqual(app.decode_packet(packet(), 7, 0)['sample_start'], 0)
        self.assertEqual(struct.unpack_from('<4i', packet(), 32), (123, -456, 8388607, -8388608))

    def test_counter_crosses_32bit_sample_boundary(self):
        self.assertEqual(app.decode_packet(packet(seq=2**23), 7, 2**23)['sample_start'], 2**32)

    def test_corrupt_headers_rejected(self):
        for word in range(8):
            data = bytearray(packet()); data[word * 4] ^= 1
            with self.subTest(word=word), self.assertRaises(ValueError):
                app.decode_packet(data, 7, 0)

    def test_unknown_flag_and_bad_sign_extension(self):
        with self.assertRaises(ValueError): app.decode_packet(packet(flags=2), 7, 0)
        data = bytearray(packet()); struct.pack_into('<i', data, 32, 8388608)
        with self.assertRaises(ValueError): app.decode_packet(data, 7, 0)
        self.assertTrue(app.decode_packet(packet(flags=1), 7, 0)['clipped'])

    def test_short_and_long_packet(self):
        for data in (packet()[:-4], packet()+b'1234'):
            with self.assertRaises(ValueError): app.decode_packet(data, 7, 0)

    def test_error_bits_are_15_to_8(self):
        audio = Audio()
        for bit in range(6):
            audio.status = (1 << (8 + bit)) | 24
            self.assertEqual(app.audio_state(audio)['errors'], 1 << bit)

    def test_success_bounded_stop_and_partial_tail(self):
        audio, client, timer = Audio(), Client(), Clock()
        dma = DMA(audio)
        report, raw = app.capture(client, audio, dma, 7, 3, timer, timer.sleep)
        self.assertEqual(report['result'], 'PASS', report)
        self.assertEqual(len(raw), 3)
        self.assertTrue(report['dma_halted'])
        self.assertTrue(report['final_audio_before_dma_reset']['partial_tail'])
        self.assertFalse(client.running)
        self.assertEqual(client.actions.count('START_NO_MOTION'), 1)

    def test_direction_slots_consumed_and_time_checked(self):
        for epoch, expected in [(7, 'PASS'), (6, 'FAIL')]:
            audio, client, timer = Audio(), Client(), Clock()
            queue = []
            normal_read = client.read
            client.read = lambda a: (2 if queue else 0) if a == STATUS else normal_read(a)
            client.acquire = lambda: queue[0]
            client.consume = lambda frame: queue.pop(0)
            dma = DMA(audio)
            take = dma.take
            def take_with_frame():
                i = dma.submitted - 1
                queue.append(dict(sequence=i+1, audio=dict(epoch=epoch, sample_start=i*512,
                    source_window=100+i, sample_count=1024, valid=True)))
                return take()
            dma.take = take_with_frame
            report, raw = app.capture(client, audio, dma, 7, 2, timer, timer.sleep)
            self.assertEqual(report['result'], expected, report)
            self.assertEqual(len(report['frames']), 2)
            self.assertEqual(queue, [])
            if epoch == 7:
                self.assertTrue(report['frames'][0]['audio']['covered_by_recording'])
                self.assertFalse(report['frames'][1]['audio']['covered_by_recording'])

    def test_all_failures_stop_and_preserve_reason(self):
        for failure in ('dma', 'overflow', 'timeout', 'interrupt', 'gap', 'reset'):
            audio, client, timer = Audio(), Client(), Clock()
            dma = DMA(audio, failure)
            with self.subTest(failure=failure):
                report, raw = app.capture(client, audio, dma, 7, 1, timer, timer.sleep)
                self.assertEqual(report['result'], 'FAIL', report)
                self.assertFalse(client.running)
                self.assertEqual(report['dma_halted'], failure != 'reset')
                self.assertIn('final_audio_before_dma_reset', report)
                if failure == 'gap': self.assertEqual(len(raw), 1)

    def test_old_frames_and_faults_preserved_before_first_write(self):
        for field in ('old_frame', 'fault'):
            audio, client = Audio(), Client()
            setattr(client, field, True)
            dma = DMA(audio)
            with self.assertRaises(RuntimeError): app.capture(client, audio, dma, 7)
            self.assertEqual(audio.writes, [])
            self.assertEqual(client.actions, [])
            self.assertEqual(dma.reset_count, 0)

    def test_reused_epoch_refused(self):
        audio = Audio(); audio.epoch = 7
        with self.assertRaises(ValueError): app.capture(Client(), audio, DMA(audio), 7)
        self.assertEqual(audio.writes, [])

    def test_invalid_count_no_writes(self):
        for count in (0, 1025, True):
            audio = Audio()
            with self.assertRaises(ValueError): app.capture(Client(), audio, DMA(audio), 7, count)
            self.assertEqual(audio.writes, [])

    def test_wav_keeps_24bit_channel_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = dict(packets=[app.decode_packet(packet(), 7, 0)])
            app.save_capture(tmp, report, [packet()])
            with wave.open(str(Path(tmp)/'four_mic.wav'), 'rb') as wav:
                self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (4, 3, 48000))
                self.assertEqual(wav.getnframes(), 512)
                self.assertEqual(wav.readframes(1), b'{\0\0\x38\xfe\xff\xff\xff\x7f\0\0\x80')
            saved = json.loads((Path(tmp)/'result.json').read_text())
            self.assertEqual([c['minimum'] for c in saved['channels']], [123, -456, 8388607, -8388608])

    def test_epoch_persists_and_skips_hardware_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(next_epoch(root, 8), 9)
            self.assertEqual(next_epoch(root, 0), 10)
            self.assertEqual(next_epoch(root, 100), 101)

    def test_no_premature_dma_read_or_free(self):
        ip, buffer, timer = Mock(), Mock(), Clock()
        buffer.nbytes = 8224; buffer.physical_address = 0x100000
        ip.read.side_effect = lambda a: 2 if a == app.SR else 8224
        dma = app.SimpleReceive(ip, buffer, timer, timer.sleep)
        dma.submit()
        with self.assertRaises(RuntimeError): dma.submit()
        with self.assertRaises(RuntimeError): dma.take()  # idle alone is not completion
        buffer.invalidate.assert_not_called()
        buffer.freebuffer.assert_not_called()
        ip.read.side_effect = lambda a: 0x1002 if a == app.SR else 8224
        buffer.tobytes.return_value = packet()
        self.assertEqual(dma.take(), packet())
        buffer.invalidate.assert_called_once()

    def test_dma_reset_timeout_preserves_ownership(self):
        ip, buffer, timer = Mock(), Mock(), Clock()
        ip.read.return_value = 4
        dma = app.SimpleReceive(ip, buffer, timer, timer.sleep)
        dma.inflight = dma.exposed = True
        with self.assertRaises(TimeoutError): dma.reset()
        self.assertTrue(dma.exposed)
        buffer.freebuffer.assert_not_called()

    def test_dma_error_and_wrong_actual_length(self):
        for status, length in ((0x10, 8224), (0x1002, 8192)):
            ip, buffer = Mock(), Mock()
            ip.read.side_effect = lambda a: status if a == app.SR else length
            dma = app.SimpleReceive(ip, buffer); dma.inflight = True
            with self.assertRaises((RuntimeError, ValueError)): dma.take()
            buffer.invalidate.assert_not_called()


if __name__ == '__main__': unittest.main()
