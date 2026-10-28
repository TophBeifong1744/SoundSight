"""Board entry for read-only PCM checks and bounded no-motion captures."""
from datetime import datetime
import json
import os
from pathlib import Path
import time

from pcm_capture import (check_hwh, identify_audio, TimedClient, SimpleReceive,
                         capture, save_capture, PACKET_BYTES, SR)
from run_capture import single_owner


def next_epoch(root, hardware_epoch):
    path = root/'pcm_epoch.local.json'
    old = json.loads(path.read_text())['last_epoch'] if path.exists() else 0
    if type(old) is not int or not 0 <= old < 0xffffffff:
        raise ValueError('Invalid/exhausted saved PCM epoch; preserve state')
    value = max(old, hardware_epoch) + 1
    if value > 0xffffffff:
        raise ValueError('PCM epoch exhausted')
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='ascii') as handle:
        json.dump(dict(last_epoch=value), handle)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return value


def retain_until_halted(dma):
    # Do not unwind/free PYNQ's buffer while PL may still write into it. This
    # exceptional wait does NOT retry capture/reset or clear the fault.
    print('DMA_NOT_HALTED: buffer retained. Power off the board before ending this process.', flush=True)
    while True:
        try:
            if int(dma.ip.read(SR)) & 1:
                print('DMA_HALTED: buffer can now be released.', flush=True)
                return
            time.sleep(1)
        except (Exception, KeyboardInterrupt):
            print('BUFFER_RETAINED: power off the board; do not kill this process.', flush=True)


def main(check_only=False, blocks=1, root=None, processor_factory=None):
    entry_begin=time.monotonic()
    detail_dir=os.environ.get('SS_ORT_PROFILE_DIR')
    chain={}
    import board_tools as board
    root = Path(root) if root is not None else board.ROOT
    if type(blocks) is not int or not 1 <= blocks <= 1024:
        raise ValueError('PCM blocks must be 1..1024')
    layout = check_hwh(root/'soundsight.hwh')  # Reject old package before extension MMIO.
    base, size = board.hwh_check(root)
    with single_owner(board.LOCK):
        overlay, slcr, clocks, mmio, ref = board.load_api(root)
        if not overlay.is_loaded():
            raise RuntimeError('Run prepare from this package first')
        board.clock_check(slcr, clocks, ref)
        board.clock_ready(slcr, clocks)
        ps = mmio(base, size)
        state = board.device_state(ps)
        if int(ps.read(0x80)) != 0x10001:
            raise RuntimeError('Loaded hardware has no audio time metadata')
        audio = mmio(*layout['audio_capture'])
        dma_regs = mmio(*layout['axi_dma_audio'])
        audio_status = identify_audio(audio)
        print('PCM_CHECK=', json.dumps(dict(ps=state, audio=audio_status,
              dma_status=int(dma_regs.read(SR)), packet_bytes=PACKET_BYTES,
              sample_rate=48000, channels=4, motion=False), sort_keys=True), flush=True)
        if check_only:
            print('PCM_INTERFACE_OK=1 NO_CAPTURE=1 SERVO=OFF', flush=True)
            return 0
        board.require_idle(state)
        from pynq import allocate
        folder = root/'logs'/('pcm-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        folder.mkdir(parents=True, exist_ok=False)
        epoch = next_epoch(root, audio_status['epoch'])
        processor = None
        buffer = dma = None
        report = None
        try:
            # The device lock and idle checks precede model loading; other control
            # commands cannot run while live speaker workers are starting.
            stamp=time.monotonic();chain['preflight_seconds']=stamp-entry_begin
            processor = processor_factory() if processor_factory is not None else None
            chain['worker_and_model_startup_seconds']=time.monotonic()-stamp
            stamp=time.monotonic()
            buffer = allocate(shape=(PACKET_BYTES,), dtype='u1')
            dma = SimpleReceive(dma_regs, buffer)
            chain['buffer_and_dma_setup_seconds']=time.monotonic()-stamp
            options = {} if processor is None else dict(packet_sink=processor.submit, started=processor.started)
            if processor is not None:
                print('SPEAKER_CAPTURE_START=1 SERVO=OFF', flush=True)
            client = TimedClient(ps, None)
            stamp=time.monotonic()
            if processor is not None and os.environ.get('SS_SPEAKER_CPU_PROFILE') == '1':
                from live_cpu_profile import CaptureMeter
                report, packets = CaptureMeter().capture(capture, client, audio, dma, epoch, blocks, **options)
            else:
                report, packets = capture(client, audio, dma, epoch, blocks, **options)
            chain['capture_seconds']=time.monotonic()-stamp
            report['hardware'] = json.loads((root/'SOURCE.json').read_text()).get('hardware_identity', {})
            if processor is not None:
                stamp=time.monotonic()
                try:
                    report['speaker'] = processor.finish(report['result'] == 'PASS')
                    if report['speaker']['status'] != 'PASS':
                        report['result'] = 'FAIL'
                        report['error'] = report['error'] or report['speaker'].get('error', 'Speaker worker failed')
                except (Exception, KeyboardInterrupt) as exc:
                    report['result'] = 'FAIL'
                    report['error'] = report['error'] or 'Speaker finish: '+repr(exc)
                print('SPEAKER_SESSION=', json.dumps({k:v for k,v in report.get('speaker', {'status':'FAIL'}).items() if k!='results'}), flush=True)
                chain['worker_drain_and_profile_flush_seconds']=time.monotonic()-stamp
            if detail_dir:report['chain_timing']=dict(chain)
            stamp=time.monotonic()
            save_capture(folder, report, packets)
            chain['save_capture_seconds']=time.monotonic()-stamp
            chain['entry_to_saved_seconds']=time.monotonic()-entry_begin
            if detail_dir:
                with (Path(detail_dir)/'capture-chain.json').open('x') as f:
                    json.dump(dict(result_path=str(folder/'result.json'),result=report['result'],timing=chain,
                        scope='Host main entry through save_capture; includes startup, capture, drain and saving; excludes final cleanup and this sidecar write. Parallel worker intervals overlap capture.'),f,indent=2)
            print('PCM_TIMING=', json.dumps(report.get('receiver_timing', {})), flush=True)
            if 'capture_cpu_profile' in report:
                print('CAPTURE_CPU_PROFILE=', json.dumps(report['capture_cpu_profile']), flush=True)
            if report.get('first_fault') is not None:
                print('PCM_FIRST_FAULT=', json.dumps(report['first_fault']), flush=True)
            print('PCM_RESULT=%s BLOCKS=%d OUTPUT=%s SERVO=OFF' %
                  (report['result'], len(report['packets']), folder), flush=True)
            if report['error']:
                print('PCM_ERROR=', report['error'], flush=True)
            return 0 if report['result'] == 'PASS' else 1
        finally:
            # Also protects against a storage exception after capture returned.
            try:
                if dma is not None and dma.exposed:
                    try:
                        halted = bool(int(dma_regs.read(SR)) & 1)
                    except (Exception, KeyboardInterrupt):
                        halted = False
                    if not halted:
                        retain_until_halted(dma)
                if buffer is not None:
                    buffer.freebuffer()
            finally:
                if processor is not None:
                    processor.close()
