"""Bounded four-microphone PCM diagnostic; never grants motion permission.

Uses Simple S2MM registers directly so every wait has a deadline. No PYNQ
DMA driver is instantiated (its constructor may start the channel).
"""
import json
import struct
import time
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

from ps_client import SYS, STATUS, FAULT, DROP, SEQ
from volume_gate import VolumeClient

PACKET_BYTES = 8224
SAMPLES = 512
RATE = 48000
CR, SR, DA, LENGTH = 0x30, 0x34, 0x48, 0x58
DMA_ERRORS = 0x770
S24_SIGN_BYTES = bytes(128) + bytes([255]) * 128


def check_hwh(path):
    tree = ET.parse(path)
    expected = {'audio_capture': ('bd_audio_capture', 0x43c00000, 4096),
                'axi_dma_audio': ('axi_dma', 0x40400000, 65536)}
    found = {}
    for name, (kind, base, size) in expected.items():
        modules = [m for m in tree.iter('MODULE') if m.get('INSTANCE') == name
                   and m.get('MODTYPE') == kind]
        ranges = {(int(m.get('BASEVALUE'), 0), int(m.get('HIGHVALUE'), 0))
                  for m in tree.iter('MEMRANGE') if m.get('INSTANCE') == name
                  and m.get('MEMTYPE') == 'REGISTER'}
        if len(modules) != 1 or ranges != {(base, base + size - 1)}:
            raise ValueError('PCM HWH module/address mismatch: ' + name)
        found[name] = (base, size)
        if name == 'axi_dma_audio':
            params = {p.get('NAME'): p.get('VALUE') for p in modules[0].iter('PARAMETER')}
            for key, value in {'C_INCLUDE_SG': '0', 'C_INCLUDE_MM2S': '0',
                               'C_INCLUDE_S2MM': '1', 'C_INCLUDE_S2MM_DRE': '0',
                               'C_S_AXIS_S2MM_TDATA_WIDTH': '32',
                               'C_M_AXI_S2MM_DATA_WIDTH': '64',
                               'C_SG_LENGTH_WIDTH': '16'}.items():
                if params.get(key) != value:
                    raise ValueError('Unsupported DMA configuration: ' + key)
    for name in ('compute', 'ps_link'):
        modules = [m for m in tree.iter('MODULE') if m.get('INSTANCE') == name]
        if len(modules) != 1 or not any(p.get('NAME') == 'AUDIO_ENABLE' and
                                       p.get('VALUE') == '1' for p in modules[0].iter('PARAMETER')):
            raise ValueError('AUDIO_ENABLE=1 required: ' + name)
    return found


def audio_state(ip):
    raw = int(ip.read(0x0c))
    # Actual RTL packs {16'b0, errors[7:0], status[7:0]}.
    return dict(raw=raw, errors=(raw >> 8) & 255, armed=bool(raw & 1),
                pending=bool(raw & 2), partial_tail=bool(raw & 4),
                idle=bool(raw & 8), dma_reset_released=bool(raw & 16),
                ready=bool(raw & 32), rejected=int(ip.read(0x20)),
                published=int(ip.read(0x24)), epoch=int(ip.read(0x30)))


def identify_audio(ip):
    expected = {0x00: 0x10001, 0x10: RATE, 0x14: 0x04201801,
                0x18: SAMPLES, 0x1c: PACKET_BYTES}
    for address, value in expected.items():
        if int(ip.read(address)) != value:
            raise RuntimeError('Audio register mismatch at 0x%x' % address)
    return audio_state(ip)


def decode_packet(data, epoch, sequence):
    if len(data) != PACKET_BYTES:
        raise ValueError('Incorrect DMA packet length: %d' % len(data))
    magic, fmt, session, seq, low, high, count_flags, size = struct.unpack_from('<8I', data)
    start = low | (high << 32)
    flags = count_flags >> 16
    if (magic, fmt, session, seq, start, count_flags & 65535, size) != (
            0x43505353, 0x00200001, epoch, sequence, sequence * SAMPLES, SAMPLES, 8192):
        raise ValueError('Packet header/session/sequence/sample continuity mismatch')
    if flags & ~1:
        raise ValueError('Unknown packet flags')
    # Reject malformed S24 sign extension rather than silently truncating it.
    if bytes(data[34::4]).translate(S24_SIGN_BYTES) != bytes(data[35::4]):
        raise ValueError('PCM is not sign-extended S24')
    return dict(epoch=session, block_seq=seq, sample_start=start,
                sample_count=SAMPLES, clipped=bool(flags & 1))


class TimedClient(VolumeClient):
    def acquire(self, timeout=.25):
        frame = super().acquire(timeout)
        frame['audio'] = dict(epoch=self.read(0x84),
                              sample_start=self.read(0x88) | (self.read(0x8c) << 32),
                              source_window=self.read(0x90))
        info = self.read(0x94)
        frame['audio'].update(sample_count=info & 65535, valid=bool(info & 0x10000))
        if self.read(SEQ) != frame['sequence'] or not self.read(STATUS) & 1:
            raise RuntimeError('Timed snapshot changed while locked')
        return frame


class SimpleReceive:
    def __init__(self, ip, buffer, clock=time.monotonic, sleep=time.sleep):
        self.ip, self.buffer, self.clock, self.sleep = ip, buffer, clock, sleep
        self.inflight = False
        self.exposed = False

    def wait_for(self, condition, message, timeout=.5):
        end = self.clock() + timeout
        while not condition():
            if self.clock() >= end:
                raise TimeoutError(message)
            self.sleep(.0002)

    def reset(self):
        self.ip.write(CR, 4)
        self.wait_for(lambda: not self.ip.read(CR) & 4 and self.ip.read(SR) & 1,
                      'DMA reset/halt timeout; buffer must remain allocated')
        self.inflight = False
        self.exposed = False

    def start(self):
        address = int(self.buffer.physical_address)
        if self.buffer.nbytes != PACKET_BYTES or address % 8 or not 0 < address < 2**32 - PACKET_BYTES:
            raise ValueError('DMA requires an aligned 8224-byte buffer below 4 GiB')
        self.buffer.flush()
        self.ip.write(CR, 1)  # Polling only; interrupts disabled.
        self.wait_for(lambda: not self.ip.read(SR) & 1, 'DMA did not start')

    def submit(self):
        if self.inflight:
            raise RuntimeError('DMA buffer is still owned by hardware')
        self.ip.write(SR, 0x7000)
        self.ip.write(DA, int(self.buffer.physical_address))
        self.inflight = True  # A failed LENGTH write may still have reached hardware.
        self.exposed = True
        self.ip.write(LENGTH, PACKET_BYTES)

    def completed(self):
        status = int(self.ip.read(SR))
        if status & DMA_ERRORS or status & 1:
            raise RuntimeError('DMA error/halted: 0x%x' % status)
        return bool(status & 2 and status & 0x1000)

    def take(self):
        if not self.inflight or not self.completed():
            raise RuntimeError('DMA completion not confirmed')
        length = int(self.ip.read(LENGTH))
        self.inflight = False
        if length != PACKET_BYTES:
            raise ValueError('DMA returned %d bytes, expected 8224' % length)
        self.buffer.invalidate()
        return self.buffer.tobytes()


def capture(client, audio, dma, epoch, blocks=1, clock=time.monotonic, sleep=time.sleep,
            packet_sink=None, started=None):
    """RAM-only service loop; caller saves results after STOP and confirmed DMA halt.

    Errors are data in the report, not successful recordings. Existing frames or
    faults are refused without consuming/resetting them. A normal bounded stop
    drains complete audio packets and records any unpublished partial tail.
    """
    if type(blocks) is not int or not 1 <= blocks <= 1024 or not 1 <= epoch <= 0xffffffff:
        raise ValueError('blocks must be 1..1024 and epoch must be nonzero uint32')
    if any(callback is not None and not callable(callback) for callback in (packet_sink, started)):
        raise ValueError('Capture callbacks must be callable')
    report = dict(result='FAIL', epoch=epoch, requested_blocks=blocks, packets=[],
                  frames=[], error=None, cleanup_errors=[], dma_halted=False, motion=False)
    raw = []
    client.identify()
    if client.read(0x80) != 0x10001:
        raise RuntimeError('Timed snapshot capability missing')
    initial = identify_audio(audio)
    report['initial_audio'] = initial
    if (client.read(SYS) & 1 or client.read(STATUS) & (3 | 0x8000) or
            client.read(0x58) & 1 or client.read(0x74) & 3):
        raise RuntimeError('Stop the current owner and preserve/drain old snapshots first')
    if client.read(FAULT) & ~0x40 or initial['errors'] or initial['armed'] or initial['pending']:
        raise RuntimeError('Existing fault/audio data; preserve diagnostics before retry')
    if epoch == initial['epoch']:
        raise ValueError('New capture epoch required')
    if not dma.ip.read(SR) & 1:
        raise RuntimeError('DMA is not halted; inspect prior owner before capture')

    timing = dict(max_poll_gap_seconds=0., max_rearm_seconds=0.,
                  max_frame_service_seconds=0., max_decode_seconds=0.,
                  max_sink_seconds=0., early_rearms=0)
    report['receiver_timing'] = timing
    report['first_fault'] = None
    poll_previous = None

    def observe_fault():
        # Read before STOP/reset changes status; sequential MMIO, not an atomic snapshot.
        if report['first_fault'] is None:
            report['first_fault'] = dict(audio=audio_state(audio),
                fault=int(client.read(FAULT)), drops=int(client.read(DROP)),
                status=int(client.read(STATUS)), dma_status=int(dma.ip.read(SR)),
                received_packets=len(report['packets']))

    def service_frames():
        begin = clock()
        # At most two original slots; no solver/SD writes in the receiver loop.
        for _ in range(2):
            if not client.read(STATUS) & 3:
                break
            frame = client.acquire()
            if len(report['frames']) >= blocks * 2 + 32:
                raise RuntimeError('Snapshot RAM limit reached')
            report['frames'].append(frame)
            client.consume(frame)
        timing['max_frame_service_seconds'] = max(timing['max_frame_service_seconds'], clock()-begin)

    def receive(check_faults=True, rearm=False):
        nonlocal poll_previous
        end = clock() + .5
        while True:
            now = clock()
            if poll_previous is not None:
                timing['max_poll_gap_seconds'] = max(timing['max_poll_gap_seconds'], now-poll_previous)
            poll_previous = now
            if dma.completed():
                break
            service_frames()
            if check_faults and (client.read(FAULT) or int(audio.read(0x0c)) & 0xff00):
                observe_fault()
                raise RuntimeError('Acquisition fault; recording is incomplete')
            if clock() >= end:
                raise TimeoutError('DMA packet timeout')
            sleep(.0002)
        begin = clock()
        data = dma.take()  # Immutable copy; hardware may now reuse its buffer.
        raw.append(data)  # Preserve malformed completed input for diagnosis too.
        if rearm:
            # Keep hardware draining while Python validates and services snapshots.
            # Failure below still follows STOP/reset; buffer remains owned until halt.
            dma.submit()
            timing['early_rearms'] += 1
            timing['max_rearm_seconds'] = max(timing['max_rearm_seconds'], clock()-begin)
        begin = clock()
        report['packets'].append(decode_packet(data, epoch, len(report['packets'])))
        timing['max_decode_seconds'] = max(timing['max_decode_seconds'], clock()-begin)
        service_frames()
        # Immutable completed bytes only. The live consumer must enqueue without
        # waiting; any callback error enters the same STOP/reset cleanup path.
        if packet_sink is not None and check_faults:
            begin = clock()
            packet_sink(data, report['packets'][-1])
            timing['max_sink_seconds'] = max(timing['max_sink_seconds'], clock()-begin)

    try:
        client.disable()
        dma.reset()
        dma.start()
        audio.write(0x08, epoch)
        audio.write(0x04, 1)
        dma.wait_for(lambda: audio_state(audio)['ready'], 'Audio ARM timeout')
        dma.submit()
        if started is not None:
            started(clock())  # Conservative host origin before START MMIO.
        client.start(clear_faults=0x40)
        for i in range(blocks):
            receive(rearm=i + 1 < blocks)
        audio.write(0x04, 2)
        client.disable()
        # Synchronised armed/run state settles while the old compute path drains.
        dma.wait_for(lambda: not audio_state(audio)['armed'], 'Audio STOP timeout')
        service_frames()
        for _ in range(8):
            if not audio_state(audio)['pending']:
                break
            dma.submit()
            receive(check_faults=False)
        else:
            raise RuntimeError('Audio drain did not finish within bounded FIFO capacity')
        state = audio_state(audio)
        if state['errors'] or state['rejected'] or client.read(FAULT) & ~0x40:
            observe_fault()
            raise RuntimeError('Fault at end of recording')
        if state['published'] != len(report['packets']):
            raise RuntimeError('Published/received block count mismatch')
        previous = None
        for frame in report['frames']:
            meta = frame['audio']
            if meta['valid'] and (meta['epoch'] != epoch or meta['sample_count'] != 1024
                                  or meta['sample_start'] % 512):
                raise RuntimeError('Direction/audio time association mismatch')
            if meta['valid']:
                # Window IDs survive enable/disable; sample indices restart.
                if previous and (meta['source_window'] != previous['source_window'] + 1 or
                                 meta['sample_start'] != previous['sample_start'] + 512):
                    raise RuntimeError('Direction window discontinuity')
                meta['covered_by_recording'] = meta['sample_start'] + 1024 <= len(report['packets']) * 512
                previous = meta
        report['result'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        try:
            observe_fault()
        except (Exception, KeyboardInterrupt) as diagnostic_error:
            report['fault_readback_error'] = repr(diagnostic_error)
    finally:
        for name, operation in [('audio_stop', lambda: audio.write(0x04, 2)),
                                ('source_stop', client.disable), ('snapshot_drain', service_frames)]:
            try:
                operation()
            except (Exception, KeyboardInterrupt) as exc:
                report['cleanup_errors'].append(name + ': ' + str(exc))
        try:
            report['final_audio_before_dma_reset'] = audio_state(audio)
            report['final_ps'] = dict(status=client.read(STATUS), fault=client.read(FAULT),
                                      drops=client.read(DROP))
            report['final_dma_before_reset'] = int(dma.ip.read(SR))
        except Exception as exc:
            report['cleanup_errors'].append('readback: ' + str(exc))
        try:
            dma.reset()
            report['dma_halted'] = True
        except (Exception, KeyboardInterrupt) as exc:
            report['cleanup_errors'].append('dma_reset: ' + str(exc))
        if report['cleanup_errors']:
            report['result'] = 'FAIL'
    return report, raw


def save_capture(directory, report, packets):
    directory = Path(directory)
    # Caller reserves a new directory before touching hardware.
    (directory/'packets.bin').write_bytes(b''.join(packets))
    # WAV is 24-bit, 48 kHz, interleaved mic0..3; no automatic normalization.
    valid = packets[:len(report['packets'])]
    pcm = b''.join(data[32:] for data in valid)
    packed = bytearray()
    for offset in range(0, len(pcm), 4):
        packed.extend(pcm[offset:offset+3])
    with wave.open(str(directory/'four_mic.wav'), 'wb') as wav:
        wav.setnchannels(4); wav.setsampwidth(3); wav.setframerate(RATE)
        wav.writeframes(bytes(packed))
    count = len(pcm) // 16
    lows, highs, totals = [8388607]*4, [-8388608]*4, [0]*4
    for values in struct.iter_unpack('<4i', pcm):
        for channel, value in enumerate(values):
            lows[channel] = min(lows[channel], value)
            highs[channel] = max(highs[channel], value)
            totals[channel] += abs(value)
    report['channels'] = [dict(mic=c, samples=count,
        minimum=lows[c] if count else None, maximum=highs[c] if count else None,
        mean_abs=totals[c]/count if count else None) for c in range(4)]
    with (directory/'result.json').open('x', encoding='ascii') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)
        handle.write('\n')
