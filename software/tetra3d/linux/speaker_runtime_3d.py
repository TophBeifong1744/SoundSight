"""Board setup/teardown for combined speaker and three-dimensional acquisition."""
from datetime import datetime
import json
import os
from pathlib import Path
import sys

import board_tools
from board_3d import check_hwh
from client_3d import ThreeDClient
from runtime_3d import State3D, display as angle_display
from solver_3d import Solver3D
from pcm_capture import check_hwh as audio_hwh, SimpleReceive, identify_audio, PACKET_BYTES
from run_pcm import next_epoch, retain_until_halted
from run_normal import NonblockingConsole
from run_capture import single_owner
from speaker_process import ProcessSpeaker
from speaker_scheduling import CaptureScheduling
from speaker_settings import verify_assets
from speaker_models import verify_candidates
from speaker_permission import load_settings
from speaker_follow_setup import check as check_speaker
from speaker_capture_3d import capture_joint


def display(state):
    speaker = state['speaker']
    score = 'NONE' if speaker['score'] is None else '%.4f' % speaker['score']
    return angle_display(state).rstrip()+(' SPEAKER_SCORE=%s THRESHOLD=%s PERMIT=%s REMAIN=%.2fs REASON=%s TRIAL=1\n' %
        (score, speaker['threshold'], int(speaker['permit']), speaker['remaining_seconds'], speaker['reason']))


def run(args, root):
    core = root/'software/ps/speaker_core'
    layout = audio_hwh(root/'soundsight.hwh')
    base, size = check_hwh(root/'soundsight.hwh')
    output = root/'logs'/('speaker-3d-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
    output.parent.mkdir(exist_ok=True)
    report = dict(result='FAIL', error='Not started', hardware_actions=0)
    processor = dma = buffer = console = None
    with single_owner(args.lock_file), CaptureScheduling() as scheduling:
        # Selection, score threshold and the worker's template must come from
        # one locked session. A concurrent speaker-select cannot splice a new
        # person's template into the previous person's configured permission.
        check_speaker(root)
        profile = verify_assets(core)
        models = verify_candidates(core)
        gate_config = load_settings(root)
        try:
            overlay, slcr, clocks, mmio, ref = board_tools.load_api(root)
            if not overlay.is_loaded():
                raise RuntimeError('Run prepare first with the matching 3-D bit/HWH')
            board_tools.clock_check(slcr, clocks, ref)
            board_tools.clock_ready(slcr, clocks)
            ip = mmio(base, size)
            board_tools.require_idle(board_tools.device_state(ip))
            audio = mmio(*layout['audio_capture'])
            dma_ip = mmio(*layout['axi_dma_audio'])
            epoch = next_epoch(root, identify_audio(audio)['epoch'])
            solver = Solver3D(args.library, args.geometry)
            client = ThreeDClient(ip, solver, args.min_level, args.window_frames,
                                   args.min_valid, args.axis_mask, args.calibration)
            # All expensive imports/model startup happen before capture starts.
            processor = ProcessSpeaker(core, 1., scheduling, follow=True)
            from pynq import allocate
            buffer = allocate(shape=(PACKET_BYTES,), dtype='u1')
            dma = SimpleReceive(dma_ip, buffer)
            state = State3D(args.frames+4 if args.debug else 0)
            print('SPEAKER_3D_READY TARGET=%s THRESHOLD=%s TTL=%s AXES=%s TRIAL=1' %
                  (profile.get('target_id', 'P01'), gate_config['threshold'], gate_config['permit_seconds'], args.axes), flush=True)
            console = NonblockingConsole(sys.stdout.fileno())
            report = capture_joint(client, audio, dma, processor, epoch, state, gate_config,
                                   frames=args.frames, seconds=args.seconds,
                                   display=lambda value: console.offer(display(value)))
            console.close()
            report['console_skipped'] = console.skipped
            console = None
            # Hardware STOP and DMA halt precede all inference waits and SD writes.
            report['speaker_worker'] = processor.finish(report['result'] == 'PASS')
            if report['speaker_worker']['status'] != 'PASS':
                report.update(result='FAIL', error=report.get('error') or report['speaker_worker'].get('error'))
        except BaseException as exc:
            report.update(result='FAIL', error=type(exc).__name__+': '+str(exc))
        finally:
            if console is not None:
                console.close()
            try:
                if dma is not None and dma.exposed:
                    retain_until_halted(dma)
                if buffer is not None:
                    buffer.freebuffer()
            finally:
                if processor is not None:
                    processor.close()
    report['settings'] = dict(speaker=gate_config, models=models, target_id=profile.get('target_id', 'P01'),
                               min_level=args.min_level, window_frames=args.window_frames,
                               min_valid=args.min_valid, axes=args.axes, frames=args.frames, seconds=args.seconds,
                               geometry=args.geometry, calibration=args.calibration,
                               recognition_qualified=False)
    with output.open('x', encoding='ascii') as handle:
        json.dump(report, handle, ensure_ascii=True, allow_nan=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    print('SPEAKER_3D_STOPPED RESULT=%s OUTPUT=%s ERROR=%s' % (report['result'], output, report.get('error')), flush=True)
    return int(report['result'] != 'PASS')
