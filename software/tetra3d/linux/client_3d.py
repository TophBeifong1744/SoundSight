"""Three-dimensional snapshot consumer. One owner, no DMA or speaker startup."""
import time
from pcm_capture import TimedClient
from ps_client import Client, FAULT, STATUS
from filter_3d import SpatialFilter
from motion_3d import DualAxis, STATE, mapped_targets


class ThreeDClient(TimedClient):
    def __init__(self, ip, solver, threshold, window_frames=20, min_valid=12,
                 axis_mask=0, calibration=None):
        super().__init__(ip, solver, threshold, angle_filter=False)
        self.spatial = SpatialFilter(window_frames, min_valid)
        self.axis_mask = axis_mask
        self.calibration = calibration or {}
        self.axes = DualAxis(ip)
        self.target = None
        self.target_time = 0.
        self.stopped = False
        self.stop_requested = lambda: False
        self.speaker_permission = None  # Set only by the combined single-owner runtime.
        self.expected_audio_epoch = None
        self.motion_interlock = None  # Joint owner polls latest IPC before ARM/COMMIT.
        self.frame_read_started_at = None

    def frame_stale(self):
        # Same 750ms budget as the existing direction hold, measured before
        # ACQUIRE rather than after a potentially stalled solver returns.
        return (self.frame_read_started_at is None or
                time.monotonic()-self.frame_read_started_at >= .75)

    def discard_stale_direction(self, record):
        self.spatial.reset()
        self.revoke_target()
        record['direction_output'].update(valid=False, updated=False, vector=None,
            azimuth_deg=None, elevation_deg=None, azimuth_valid=False,
            elevation_valid=False, reason='stale_locked_frame')
        record['angle_filter'].update(reset_reason='stale_locked_frame',
            complete=False, frame_count=0, valid_count=0, inlier_count=0)
        record['motion']['reason'] = 'STALE_LOCKED_FRAME'

    def motion_allowed(self):
        if self.stop_requested() or self.stopped or self.frame_stale():
            return False
        if self.motion_interlock is not None and not self.motion_interlock():
            return False
        if self.target is None or time.monotonic()-self.target_time >= .75:
            return False
        return self.speaker_permission is None or self.speaker_permission.allowed()

    @staticmethod
    def hardware_follow_qualified(frame):
        """Mirror only the published raw-frame admission rule, not the solver.

        A numerical 3-D solution can use three pairs; dual-axis PL admission
        requires four raw good pairs. Avoid submitting a known-invalid command.
        """
        status = frame['status']
        words = frame['words']
        count = sum(bool(w & (1 << 11) and w & (1 << 13) and not w & 0xc000 and
                         w >> 24 == 0x11 and (w >> 16) & 127 >= 12) for w in words[::5])
        return (len(words) == 30 and bool(status & 0x10) and not status & 8 and
                not status & (1 << 20) and not status >> 24 and count >= 4)

    def identify(self):
        super().identify()
        self.axes.identify()

    def start(self, bist=None, clear_faults=0):
        if bist is not None:
            raise ValueError('Legacy 2-D BIST is not a three-dimensional acoustic test')
        super().start(clear_faults=clear_faults)
        if self.axis_mask:
            self.axes.configure(self.calibration, self.axis_mask)

    def revoke_target(self):
        if self.axes.read(STATE) & 1:
            self.axes.revoke()
        self.target = None

    def stop_direction_output(self):
        self.stopped = True
        self.spatial.stop()
        self.revoke_target()

    def apply_motion(self, record):
        action = dict(requested=bool(self.axis_mask), committed=False, targets=None,
                      axes=self.axis_mask, reason='OFF', mechanical_arrival='UNVERIFIED')
        record['motion'] = action
        # Volume/angle protection remains separate from the speaker permission TTL.
        if self.speaker_permission is not None:
            if record['direction_output']['reason'] == 'below_volume_threshold':
                audio = record['frame'].get('audio', {})
                if audio.get('valid'):
                    self.speaker_permission.quiet((audio['sample_start']+audio['sample_count'])/3.)
            record['speaker'] = self.speaker_permission.snapshot()
        if self.frame_stale():
            self.discard_stale_direction(record)
            return
        if self.speaker_permission is not None:
            if not record['speaker']['permit']:
                self.revoke_target()
                action['reason'] = 'SPEAKER_'+record['speaker']['reason']
                return
        if not self.axis_mask:
            return
        if self.speaker_permission is not None and not self.hardware_follow_qualified(record['frame']):
            self.revoke_target()
            action['reason'] = 'INSUFFICIENT_RAW_PAIRS_FOR_HARDWARE_FOLLOW'
            return
        result = record['result']
        out = record['direction_output']
        detail = record['angle_filter']
        action['reason'] = 'WAITING_FOR_VALID_WINDOW'
        if self.stopped or self.stop_requested() or detail['reset_reason']:
            self.revoke_target()
            action['reason'] = 'REVOKED'
            return
        observable = (not self.axis_mask & 1 or result['azimuth_valid']) and (
            not self.axis_mask & 2 or result['elevation_valid'])
        if not record['frame_direction']['valid'] or not observable:
            if detail['complete']:
                self.revoke_target()
            action['reason'] = 'NO_FRESH_VALID_DIRECTION'
            return
        if self.target is not None and time.monotonic()-self.target_time >= .75:
            self.revoke_target()
        if out['valid']:
            self.target_time = self.frame_read_started_at
            self.target, reason = mapped_targets(out, self.calibration, self.axis_mask)
            if self.target is None:
                self.revoke_target()
                action['reason'] = reason
                return
        elif detail['complete']:
            self.revoke_target()
            action['reason'] = 'WINDOW_REJECTED'
            return
        if self.target is None:
            return
        state = self.axes.read(STATE)
        if state & 0x18:
            action['reason'] = 'WAITING_FOR_PWM_DRAIN'
            return
        if self.read(FAULT):
            raise RuntimeError('Fault before dual-axis command')
        # A normal application revoke needs a new valid group. A hardware
        # expiry sets FAULT and is never silently re-armed here.
        if not state & 1:
            if not self.axes.arm(True, permit_check=self.motion_allowed):
                self.revoke_target()
                if self.speaker_permission is not None:
                    record['speaker'] = self.speaker_permission.snapshot()
                action['reason'] = 'SPEAKER_REVOKED_BEFORE_ARM'
                if self.frame_stale(): self.discard_stale_direction(record)
                return
        if self.stop_requested():
            self.revoke_target()
            action['reason'] = 'USER_STOP'
            return
        if not self.axes.commit(self.target, record['frame']['sequence'], permit_check=self.motion_allowed):
            self.revoke_target()
            if self.speaker_permission is not None:
                record['speaker'] = self.speaker_permission.snapshot()
            action['reason'] = 'SPEAKER_REVOKED_BEFORE_COMMIT'
            if self.frame_stale(): self.discard_stale_direction(record)
            return
        if self.speaker_permission is not None:
            record['speaker'] = self.speaker_permission.snapshot()
        action.update(committed=True, targets=dict(self.target), reason='COMMIT_ACCEPTED')

    def record_one(self, sink, config=None, motion=False, allow_fault=False):
        record = None
        offered = False
        try:
            began = time.monotonic_ns()
            self.frame_read_started_at = time.monotonic()
            frame = self.acquire()
            if self.expected_audio_epoch is not None:
                audio = frame['audio']
                if (not audio['valid'] and not allow_fault or audio['valid'] and
                        (audio['epoch'] != self.expected_audio_epoch or audio['sample_count'] != 1024 or
                         audio['sample_start'] % 512)):
                    raise RuntimeError('Three-dimensional frame/audio session mismatch; retain snapshot')
            acquired = time.monotonic_ns()
            result = self.solver.solve(frame)
            record = dict(frame=frame, result=result, motion_requested=bool(self.axis_mask),
                          timing_ns=dict(acquire=acquired-began, solve=time.monotonic_ns()-acquired))
            record.update(self.spatial.apply(frame, result, self.threshold))
            if frame['fault'] and not allow_fault:
                raise RuntimeError('Device fault while reading frame; retain locked snapshot')
            if result['bridge_status'] or result['api_status']:
                raise RuntimeError('Three-dimensional solver bridge/API error; retain frame')
            self.apply_motion(record)
            offered = True
            sink(record)
            if not allow_fault and self.read(FAULT):
                raise RuntimeError('Device fault before CONSUME; retain locked snapshot')
            self.consume(frame)
            return record
        except BaseException:
            # Keep a diagnostic record in the bounded state before propagating failure.
            try:
                if record is not None and not offered:
                    offered = True
                    sink(record)
            finally:
                try:
                    self.stop_direction_output()
                finally:
                    Client.stop(self)
            raise
