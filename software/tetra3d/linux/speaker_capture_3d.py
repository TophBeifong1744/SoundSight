"""One hardware owner: priority DMA rearm, 3-D snapshots, and delayed speaker gate.

Normal mode keeps counters/latest values only. Nothing is written to SD while
sampling. Existing native inference remains in its separate lower-priority process.
"""
import time

from pcm_capture import identify_audio, audio_state, decode_packet, SR
from ps_client import SYS, STATUS, FAULT, DROP
from speaker_permission import SpeakerPermission


def capture_joint(client, audio, dma, speaker, epoch, state, config, frames=0,
                  seconds=0., stop=lambda: False, display=lambda state: None,
                  clock=time.monotonic, sleep=time.sleep):
    client.identify()
    initial = identify_audio(audio)
    if (client.read(SYS) & 1 or client.read(STATUS) & (3 | 0x8000) or
            client.read(0x58) & 1 or client.read(0x74) & 3 or client.axes.read(0xa8) & 0x19):
        raise RuntimeError('Existing capture/frames/motion; stop and drain previous owner')
    if client.read(FAULT) & ~0x40 or initial['errors'] or initial['armed'] or initial['pending']:
        raise RuntimeError('Existing device fault/audio data; preserve before retry')
    if epoch == initial['epoch'] or not 1 <= epoch <= 0xffffffff or not dma.ip.read(SR) & 1:
        raise RuntimeError('New audio epoch and halted DMA required')
    gate = SpeakerPermission(config, clock)
    gate.start(epoch)
    client.speaker_permission = gate
    client.expected_audio_epoch = epoch
    report = dict(result='FAIL', error=None, cleanup_errors=[], packets=0, tail_packets=0,
                  epoch=epoch, dma_halted=False, max_dma_rearm_seconds=0., max_service_gap_seconds=0.,
                  retention='bounded_statistics', first_fault=None)
    start = previous = last_packet = last_display = clock()
    last_raw = None
    tail = False

    def diagnostic():
        return dict(audio=audio_state(audio), status=client.read(STATUS), fault=client.read(FAULT),
                    drops=client.read(DROP), dma_status=int(dma.ip.read(SR)))

    def poll_permission():
        for event in speaker.poll_events():
            gate.event(event)
        allowed = gate.allowed()
        if not allowed:
            client.revoke_target()
        return allowed

    client.motion_interlock = poll_permission

    def service_frame():
        if not client.read(STATUS) & 3:
            return
        began = clock()
        client.record_one(state.accept, allow_fault=tail)
        state.stats['drained' if tail else 'consumed'] += 1
        state.stats['max_service_ns'] = max(state.stats['max_service_ns'], int((clock()-began)*1e9))

    def take_packet(rearm, forward):
        nonlocal last_raw, last_packet
        began = clock()
        data = dma.take()
        last_raw = data
        if rearm:
            dma.submit()
            report['max_dma_rearm_seconds'] = max(report['max_dma_rearm_seconds'], clock()-began)
        meta = decode_packet(data, epoch, report['packets']+report['tail_packets'])
        if forward:
            speaker.submit(data, meta)
            report['packets'] += 1
        else:
            report['tail_packets'] += 1
        last_packet = clock()

    try:
        client.disable()
        dma.reset()
        dma.start()
        audio.write(0x08, epoch)
        audio.write(0x04, 1)
        dma.wait_for(lambda: audio_state(audio)['ready'], 'Audio ARM timeout')
        dma.submit()
        start = previous = last_packet = clock()
        speaker.started(start)
        client.start(clear_faults=0x40)
        while not stop() and (not frames or state.stats['consumed'] < frames) and (not seconds or clock()-start < seconds):
            now = clock()
            report['max_service_gap_seconds'] = max(report['max_service_gap_seconds'], now-previous)
            previous = now
            poll_permission()
            # Rearm before solving or formatting anything: the single DDR buffer
            # may be reused only after the completed immutable bytes were copied.
            if dma.completed():
                take_packet(True, True)
            service_frame()
            if client.read(FAULT) or int(audio.read(0x0c)) & 0xff00:
                raise RuntimeError('Capture/servo fault; stop and preserve diagnostic state')
            if clock()-last_packet > .5:
                raise TimeoutError('No DMA packet within 0.5 seconds')
            if now-last_display >= .5:
                value = state.snapshot()
                value['speaker'] = gate.snapshot()
                display(value)
                last_display = now
            sleep(.0002)
        report['result'] = 'PASS'
        report['stop_reason'] = 'requested_limit' if not stop() else 'user_stop'
    except KeyboardInterrupt:
        report.update(result='PASS', stop_reason='user_stop')
    except Exception as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        try:
            report['first_fault'] = diagnostic()
        except Exception as extra:
            report['first_fault_error'] = repr(extra)
        # One failed packet only; continuous normal mode is not an audio recorder.
        report['last_packet_header_hex'] = last_raw[:32].hex() if last_raw else None
    finally:
        gate.revoke('SESSION_ENDED')
        # Independently attempt every stop; extension write failure must not skip SYS/audio STOP.
        for name, operation in (('axes_revoke', client.stop_direction_output),
                                ('audio_stop', lambda: audio.write(0x04, 2)),
                                ('source_stop', client.disable)):
            try:
                operation()
            except BaseException as exc:
                report['cleanup_errors'].append(name+': '+repr(exc))
        tail = True
        state.tail = True
        if report['result'] == 'PASS' and not report['cleanup_errors']:
            try:
                dma.wait_for(lambda: not audio_state(audio)['armed'], 'Audio STOP timeout')
                # Complete outstanding DMA/FIFO packets without forwarding a new
                # speaker task. All speech permissions have already been revoked.
                for _ in range(8):
                    if dma.inflight and dma.completed():
                        take_packet(False, False)
                    if not audio_state(audio)['pending']:
                        break
                    if not dma.inflight:
                        dma.submit()
                    dma.wait_for(dma.completed, 'Audio tail DMA timeout')
                else:
                    raise RuntimeError('Audio tail exceeded FIFO bound')
                end = clock()+.5
                while client.read(STATUS) & (3 | 0x8000):
                    if clock() >= end:
                        raise TimeoutError('Direction tail did not drain')
                    service_frame()
                    sleep(.0002)
                final = audio_state(audio)
                if final['errors'] or final['rejected'] or client.read(FAULT) & ~0x40:
                    raise RuntimeError('Device fault during normal STOP')
                if final['published'] != report['packets']+report['tail_packets']:
                    raise RuntimeError('Published/received PCM count differs')
            except BaseException as exc:
                report['cleanup_errors'].append('drain: '+repr(exc))
        try:
            report['hardware'] = diagnostic()
        except BaseException as exc:
            report['cleanup_errors'].append('readback: '+repr(exc))
        try:
            dma.reset()
            report['dma_halted'] = True
        except BaseException as exc:
            report['cleanup_errors'].append('dma_reset: '+repr(exc))
        if report['cleanup_errors']:
            report['result'] = 'FAIL'
        report.update(state.snapshot('stopped' if report['result'] == 'PASS' else 'failed'))
        report['speaker_permission'] = gate.snapshot()
        report['last_processed_record'] = state.last_record
        if state.debug_limit:
            report['records'] = state.records
    return report
