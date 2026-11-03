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
from speaker_scheduling import CaptureScheduling
from speaker_capture_3d import capture_joint
from coherent_frontend import CoherentSolver


class AcousticOnly:
    """No identity engine is started for the explicit follow-sound route."""
    def started(self, when):
        pass

    def submit(self, data, meta):
        pass

    def finish(self, normal):
        return dict(status='PASS', enabled=False)

    def close(self):
        pass


def display(state):
    speaker = state['speaker']
    diagnostic = speaker.get('display_result')
    score = 'NONE' if diagnostic is None else '%.4f' % diagnostic['score']
    age = 'NONE' if diagnostic is None else '%.2fs' % speaker['display_score_age_seconds']
    usable = 'NONE' if diagnostic is None else str(int(diagnostic['usable']))
    reason = 'NO_SCORE_YET' if diagnostic is None else diagnostic['reason']
    return angle_display(state).rstrip()+(' SPEAKER_SCORE=%s SCORE_STATE=%s SCORE_AGE=%s'
        ' SCORE_USABLE_AT_COMPLETION=%s SCORE_REASON=%s THRESHOLD=%s PERMIT=%s'
        ' REMAIN=%.2fs PERMIT_REASON=%s POLICY=score_ttl_v2 TRIAL=1\n' %
        (score, 'NONE' if diagnostic is None else 'LAST_COMPLETED', age, usable, reason,
         speaker['threshold'], int(speaker['permit']), speaker['remaining_seconds'], speaker['reason']))


def run(args, root, acoustic=False):
    collect_statistics = bool(getattr(args, 'speaker_stats', False))
    core = root/'software/ps/speaker_core'
    layout = audio_hwh(root/'soundsight.hwh')
    base, size = check_hwh(root/'soundsight.hwh')
    output = (Path(args.output) if acoustic else
              root/'logs'/('speaker-3d-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json'))
    output.parent.mkdir(exist_ok=True)
    report = dict(result='FAIL', error='Not started', hardware_actions=0)
    processor = dma = buffer = console = None
    with single_owner(args.lock_file), CaptureScheduling() as scheduling:
        # Selection, score threshold and the worker's template must come from
        # one locked session. A concurrent speaker-select cannot splice a new
        # person's template into the previous person's configured permission.
        profile, models, gate_config = {}, {}, None
        if not acoustic:
            from speaker_process import ProcessSpeaker
            from speaker_settings import verify_assets
            from speaker_models import verify_candidates
            from speaker_permission import load_settings
            from speaker_follow_setup import check as check_speaker
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
            solver = CoherentSolver(Solver3D(args.library, args.geometry), epoch,
                                    root/'software/tetra3d/linux/cf1_hann.mem')
            client = ThreeDClient(ip, solver, args.min_level, args.window_frames,
                                   args.min_valid, args.axis_mask, args.calibration, verified_pcm_gaps=True)
            # All expensive imports/model startup happen before capture starts.
            processor = (AcousticOnly() if acoustic else
                         ProcessSpeaker(core, 1., scheduling, follow=True,
                                        permission_threshold=gate_config['threshold'], collect_statistics=collect_statistics))
            from pynq import allocate
            buffer = allocate(shape=(PACKET_BYTES,), dtype='u1')
            dma = SimpleReceive(dma_ip, buffer)
            state = State3D(args.frames+4 if args.debug else 0, direction_diagnostics=True)
            print('THREE_D_FRONTEND=CF1A PCM=1 HISTORY=16 PHYSICAL_GATES_UNCHANGED=1', flush=True)
            print('CAPTURE_SERVICE=CAPTURE_COOPERATIVE_V1 FILTER_POLICY=CF1_PCM_GAPS_V1', flush=True)
            if acoustic:
                print('FOLLOW_SOUND=CF1A SPEAKER=DISABLED IDENTITY_GATE=OFF AXES='+args.axes, flush=True)
            else:
                print('SPEAKER_3D_READY TARGET=%s THRESHOLD=%s TTL=%s AXES=%s TRIAL=1' %
                      (profile.get('target_id', 'P01'), gate_config['threshold'], gate_config['permit_seconds'], args.axes), flush=True)
                print('SPEAKER_STATS_ENABLED='+str(int(collect_statistics)), flush=True)
            console = NonblockingConsole(sys.stdout.fileno())
            report = capture_joint(client, audio, dma, processor, epoch, state, gate_config,
                                   frames=args.frames, seconds=args.seconds,
                                   display=lambda value: console.offer(angle_display(value) if acoustic else display(value)))
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
    report['capture_scheduling'] = scheduling.info
    report['settings'] = dict(speaker=gate_config, models=models, target_id=profile.get('target_id', 'P01'),
                               min_level=args.min_level, window_frames=args.window_frames,
                               min_valid=args.min_valid, axes=args.axes, frames=args.frames, seconds=args.seconds,
                               geometry=args.geometry, calibration=args.calibration,
                               speaker_statistics_enabled=collect_statistics, recognition_qualified=False,
                               direction_frontend='CF1A', speaker_enabled=not acoustic)
    with output.open('x', encoding='ascii') as handle:
        json.dump(report, handle, ensure_ascii=True, allow_nan=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    if acoustic:
        print('THREE_D_STOPPED SUMMARY=%s ERROR=%s' % (output, report.get('error')), flush=True)
    else:
        from speaker_statistics import save_last
        save_last(root, report, output, collect_statistics)
        print('SPEAKER_3D_STOPPED RESULT=%s OUTPUT=%s ERROR=%s' % (report['result'], output, report.get('error')), flush=True)
    return int(report['result'] != 'PASS')
