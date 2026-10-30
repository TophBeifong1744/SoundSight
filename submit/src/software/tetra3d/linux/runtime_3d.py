"""Dual-core 3-D angle runtime; display is nonblocking, logs are bounded.

Reuse the established STOP/drain/owner-loss session and parent mailbox. The
only generic hooks added there select this state and display implementation.
"""
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sys
import time

from run_normal import Mailbox, NonblockingConsole, normal_session, collect
from run_smp import pinned, validate_cpus, HOST_TIMEOUT

from run_capture import address_from_hwh, single_owner
from client_3d import ThreeDClient
from solver_3d import Solver3D
from motion_3d import MASKS


class State3D:
    def __init__(self, debug_limit=0):
        self.began = time.monotonic()
        self.stats = dict(consumed=0, drained=0, raw_valid=0, accepted_windows=0,
                          motion_commits=0, sequence_gaps=0, below_volume=0,
                          first_sequence=None, last_sequence=None, fault_or=0,
                          drops_first=None, drops_last=None, max_service_ns=0)
        self.reasons = {str(i): 0 for i in range(10)}
        self.reasons['other'] = 0
        self.latest = self.last_group = self.last_clear = self.last_record = None
        self.tail = False
        self.records = []
        self.debug_limit = debug_limit

    def accept(self, record):
        self.last_record = record
        frame, result = record['frame'], record['result']
        output, detail = record['direction_output'], record['angle_filter']
        now = time.monotonic()
        self.latest = dict(sequence=frame['sequence'], level=record['volume']['level_counts'],
                           output=output, at=now, window_count=detail['frame_count'],
                           window_size=detail['window_size'], min_valid=detail['min_valid'],
                           valid_count=detail['valid_count'], motion=record.get('motion'))
        if self.debug_limit:
            if len(self.records) >= self.debug_limit:
                raise RuntimeError('Bounded debug record capacity exhausted')
            self.records.append(record)
        if self.tail:
            return
        if detail['complete']:
            self.last_group = dict(sequence=frame['sequence'], at=now, output=output,
                                   valid_count=detail['valid_count'], inlier_count=detail['inlier_count'])
        if detail['reset_reason']:
            self.last_clear = dict(sequence=frame['sequence'], reason=detail['reset_reason'], at=now)
        s = self.stats
        seq = frame['sequence']
        if s['first_sequence'] is None:
            s['first_sequence'], s['drops_first'] = seq, frame['drops']
        elif seq != (s['last_sequence'] + 1) & 0xffffffff:
            s['sequence_gaps'] += 1
        s['last_sequence'], s['drops_last'] = seq, frame['drops']
        s['fault_or'] |= frame['fault']
        s['raw_valid'] += int(bool(result['direction_valid']))
        s['below_volume'] += int(output['reason'] == 'below_volume_threshold')
        s['accepted_windows'] += int(output['valid'])
        s['motion_commits'] += int(record.get('motion', {}).get('committed', False))
        key = str(result['reason'])
        self.reasons[key if key in self.reasons else 'other'] += 1

    def snapshot(self, phase='running'):
        return dict(phase=phase, at=time.monotonic(), stats=dict(self.stats),
                    elapsed_seconds=time.monotonic()-self.began, solver_reasons=dict(self.reasons),
                    latest=self.latest, last_group=self.last_group, last_clear=self.last_clear)


def angle_text(out):
    az = '%.2f' % out['azimuth_deg'] if out['azimuth_valid'] else 'UNOBSERVABLE'
    el = '%.2f' % out['elevation_deg'] if out['elevation_valid'] else 'UNOBSERVABLE'
    return 'AZIMUTH=%s ELEVATION=%s deg' % (az, el)


def display(state, now=None):
    now = time.monotonic() if now is None else now
    if not state or state.get('latest') is None:
        return 'NO_OUTPUT: STARTING_OR_WAITING_FOR_FIRST_FRAME\n'
    row = state['latest']
    out = row['output']
    prefix = 'FRAME=%s LEVEL=%s ' % (row['sequence'], row['level'])
    if state.get('phase') != 'running' or now-row['at'] > HOST_TIMEOUT:
        text = 'NO_OUTPUT: STOPPED_FAULT_OR_STALE_DATA'
    else:
        text = angle_text(out) if out['valid'] else 'NO_OUTPUT: '+out['reason'].upper()
    text += ' WINDOW=%s/%s VALID=%s MIN=%s' % (row['window_count'], row['window_size'],
                                             row['valid_count'], row['min_valid'])
    motion = row.get('motion') or {}
    text += ' AXES=%s MOTION=%s' % (motion.get('axes', 0), motion.get('reason', 'OFF'))
    group = state.get('last_group')
    if group:
        text += '; LAST_GROUP@%s=%s AGE=%.1fs (HISTORY)' % (
            group['sequence'], angle_text(group['output']) if group['output']['valid']
            else group['output']['reason'].upper(), max(0., now-group['at']))
    else:
        text += '; LAST_GROUP=NONE'
    clear = state.get('last_clear')
    text += '; LAST_CLEAR=%s' % (
        '%s@%s' % (clear['reason'].upper(), clear['sequence']) if clear else 'NONE')
    return prefix+text+'\n'


def worker(connection, stop, mailbox, args, base, size):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        with pinned(args.worker_cpu), single_owner(args.lock_file):
            from pynq import MMIO
            solver = Solver3D(args.library, args.geometry)
            client = ThreeDClient(MMIO(base, size), solver, args.min_level,
                                   args.window_frames, args.min_valid, args.axis_mask, args.calibration)
            client.stop_requested = stop.is_set
            client.identify()
            state = State3D(args.frames+2 if args.debug else 0)
            # Debug payload stays out of the mailbox and is sent only after STOP.
            normal_session(connection, stop, mailbox, client, args,
                           state_factory=lambda: state,
                           final_extra=lambda: dict(records=state.records,
                               retention='bounded_debug_ram_before_consume') if args.debug else {})
    except BaseException as exc:
        connection.send(('error', dict(error=type(exc).__name__+': '+str(exc),
                                       motion_requested=bool(args.axis_mask))))
    finally:
        connection.close()


def run(args):
    validate_cpus(args.host_cpu, args.worker_cpu)
    base, size = address_from_hwh(args.hwh, args.ip)
    context = mp.get_context('spawn')
    parent, child = context.Pipe()
    stop = context.Event()
    mailbox = Mailbox(context)
    mailbox.poll()
    process = context.Process(target=worker, args=(child, stop, mailbox, args, base, size))
    result = dict(error='Not started')
    console = None
    with Path(args.output).open('x', encoding='utf-8') as handle:
        try:
            console = NonblockingConsole(sys.stdout.fileno())
            process.start()
            child.close()
            with pinned(args.host_cpu):
                kind, result = collect(parent, process, stop, mailbox, console, formatter=display)
        except BaseException as exc:
            result = dict(error=type(exc).__name__+': '+str(exc), last_snapshot=mailbox.poll())
        finally:
            stop.set()
            if process.pid is not None:
                process.join(HOST_TIMEOUT)
                if process.is_alive():
                    process.terminate()
                    process.join(HOST_TIMEOUT)
                    result['cleanup_error'] = 'Worker terminated; hardware STOP not confirmed'
            parent.close()
            child.close()
            if console:
                result['console_skipped'] = console.skipped
                console.close()
            result['settings'] = dict(min_level=args.min_level, window_frames=args.window_frames,
                                      min_valid=args.min_valid, frames=args.frames, axes=args.axes,
                                      geometry=args.geometry, calibration=args.calibration,
                                      debug=args.debug, units='degrees')
            handle.write(json.dumps(result, ensure_ascii=True, indent=2)+'\n')
            handle.flush()
            os.fsync(handle.fileno())
    print('THREE_D_STOPPED SUMMARY=%s ERROR=%s' % (args.output, result.get('error')), flush=True)
    return int(bool(result.get('error') or result.get('cleanup_error')))
