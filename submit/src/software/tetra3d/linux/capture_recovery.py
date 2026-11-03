"""Explicit idle-owner audio recovery. Never starts the source or either axis.

The audio DMA reset flushes the stream through s2mm_prmry_reset_out_n.
A fresh epoch ARM while SYS is stopped clears the capture error latch; STOP
immediately follows. This is not a valid recording or an identity session.
"""
from datetime import datetime
import json
import os
import time

from pcm_capture import SimpleReceive, TimedClient, identify_audio, audio_state, SR, DMA_ERRORS
from ps_client import SYS, STATUS, FAULT, DROP
from motion_3d import DualAxis, STATE


def device_state(client, audio, dma):
    return dict(status=client.read(STATUS), fault=client.read(FAULT),
                drops=client.read(DROP), sys=client.read(SYS),
                actuator=client.read(0x58), dual_axis=client.read(STATE),
                audio=audio_state(audio), dma_status=int(dma.ip.read(SR)))


def idle(value):
    a = value['audio']
    return not (value['status'] & (3 | 0x8000) or value['sys'] & 1 or
                value['actuator'] & 1 or value['dual_axis'] & 0x19 or
                value['fault'] & ~0x40 or a['errors'] or a['pending'] or a['armed']) and \
        a['idle'] and a['dma_reset_released'] and bool(value['dma_status'] & 1) and not value['dma_status'] & DMA_ERRORS


def recover(client, audio, dma, allocate_epoch, save, clock=time.monotonic, sleep=time.sleep):
    """save(record) must durably persist before reset/CONSUME. No ignored errors."""
    axes = DualAxis(client.ip)
    axes.identify()
    client.identify()
    identify_audio(audio)
    initial = device_state(client, audio, dma)
    # Attempt every STOP even if another operation raises. Never continue recovery
    # after an unconfirmed STOP. The caller still owns the exclusive PS lock.
    errors = []
    for operation in (axes.revoke, lambda: audio.write(4, 2), client.disable):
        try:
            operation()
        except Exception as exc:
            errors.append(repr(exc))
    # Do not postpone STOP behind SD latency or a failing log destination.
    save(dict(event='before_recovery', device=initial, motion_requested=False,
              stop_errors=errors))
    if errors:
        raise RuntimeError('RECOVERY_STOP_FAILED: '+str(errors))
    axes.wait_drained(clock, sleep)
    if client.read(SYS) & 1 or client.read(STATUS) & 0x8000 or client.read(0x58) & 1:
        raise RuntimeError('RECOVERY_SOURCE_NOT_STOPPED')
    # Do not clear unrelated hardware faults. Preserve each locked snapshot before
    # CONSUME, without a solver, motion mapping or replay to the identity worker.
    if client.read(FAULT) & ~0x40:
        raise RuntimeError('RECOVERY_UNEXPECTED_PS_FAULT: inspect saved diagnostics')
    for _ in range(2):
        if not client.read(STATUS) & 3:
            break
        frame = client.acquire()
        save(dict(event='retained_snapshot', frame=frame, motion_requested=False))
        client.consume(frame)
    if client.read(STATUS) & (3 | 0x8000):
        raise RuntimeError('RECOVERY_SNAPSHOT_NOT_EMPTY')
    # No buffer is submitted and DMA is never RUN. Reset aborts old stream data;
    # this loss is explicit in the diagnostic, never counted as a passed capture.
    save(dict(event='before_audio_reset', device=device_state(client, audio, dma),
              old_audio_discarded=True))
    dma.reset()
    dma.wait_for(lambda: audio_state(audio)['idle'] and audio_state(audio)['dma_reset_released'],
                 'RECOVERY_AUDIO_NOT_IDLE_AFTER_RESET')
    epoch = allocate_epoch(audio_state(audio)['epoch'])
    armed = False
    try:
        audio.write(8, epoch)
        armed = True  # A write exception can still have reached hardware.
        audio.write(4, 1)
        dma.wait_for(lambda: audio_state(audio)['ready'], 'RECOVERY_NEW_EPOCH_NOT_READY')
    finally:
        if armed:
            audio.write(4, 2)
    dma.wait_for(lambda: idle(device_state(client, audio, dma)), 'RECOVERY_FINAL_STOP_NOT_VERIFIED')
    final = device_state(client, audio, dma)
    if final['audio']['epoch'] != epoch or final['audio']['rejected'] or final['audio']['published']:
        raise RuntimeError('RECOVERY_EPOCH_OR_COUNTER_MISMATCH')
    save(dict(event='recovered', device=final, epoch=epoch, motion_requested=False,
              source_started=False, identity_reused=False))
    return final


def run(root):
    from board_3d import check_hwh, LOCK
    from pcm_capture import check_hwh as audio_hwh
    from run_capture import single_owner
    from run_pcm import next_epoch
    import board_tools
    base, size = check_hwh(root/'soundsight.hwh')
    layout = audio_hwh(root/'soundsight.hwh')
    output = root/'logs'/('capture-recovery-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.jsonl')
    output.parent.mkdir(exist_ok=True)
    with single_owner(LOCK):
        overlay, slcr, clocks, mmio, ref = board_tools.load_api(root)
        if not overlay.is_loaded():
            raise RuntimeError('NOT_PREPARED: recovery never loads a bitstream')
        board_tools.clock_check(slcr, clocks, ref)
        board_tools.clock_ready(slcr, clocks)
        client = TimedClient(mmio(base, size), None)
        audio = mmio(*layout['audio_capture'])
        dma = SimpleReceive(mmio(*layout['axi_dma_audio']), None)
        with output.open('x', encoding='ascii') as handle:
            def save(record):
                handle.write(json.dumps(record, ensure_ascii=True, allow_nan=False)+'\n')
                handle.flush()
                os.fsync(handle.fileno())
            print('RECOVERY_LOG='+str(output), flush=True)
            try:
                final = recover(client, audio, dma, lambda old: next_epoch(root, old), save)
            except BaseException as exc:
                save(dict(event='failed', error=type(exc).__name__+': '+str(exc)))
                raise
    print('DEVICE_STATE='+json.dumps(final), flush=True)
    print('CAPTURE_RECOVERED=1 AXES=OFF NEXT_START=EXPLICIT', flush=True)
    return 0
