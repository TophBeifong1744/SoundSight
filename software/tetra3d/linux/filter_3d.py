"""Bounded spherical direction filter; no hardware or actuator permission.

The 2-D policy is extended to unit vectors: 20 frames / 12 valid by default,
10 degree inliers, two-thirds consensus and a 3 degree spatial deadband.
Low level and faults revoke the target. CF1 may bridge bounded snapshot gaps
only with verified continuous PCM; legacy inputs remain strictly sequential.
"""
import math
import time
from angle_filter import validate_window

RADIUS = 10.0
DEADBAND = 3.0


def unit(values):
    if len(values) != 3 or any(not math.isfinite(v) for v in values):
        raise ValueError('Expected finite XYZ')
    n = math.sqrt(sum(v*v for v in values))
    if n <= 1e-12:
        raise ValueError('Undefined spatial direction')
    return tuple(v/n for v in values)


def separation(a, b):
    return math.degrees(math.acos(max(-1., min(1., sum(x*y for x, y in zip(a, b))))))


def angles(vector):
    x, y, z = unit(vector)
    observable = math.hypot(x, y) > 1e-4
    return dict(vector=[x, y, z], azimuth_valid=observable, elevation_valid=True,
                azimuth_deg=((math.degrees(math.atan2(y, x))+180) % 360-180) if observable else None,
                elevation_deg=math.degrees(math.atan2(z, math.hypot(x, y))))


class SpatialFilter:
    def __init__(self, window_frames=20, min_valid=12, verified_pcm_gaps=False, clock=time.monotonic):
        self.window, self.minimum = validate_window(window_frames, min_valid)
        self.verified_pcm_gaps = verified_pcm_gaps
        self.clock = clock
        self.stopped = False
        self.reset()

    def reset(self):
        self.count = 0
        self.vectors = []
        self.held = None
        self.last_sequence = None
        self.last_audio = None
        self.group_source_start = self.group_host_start = None

    def stop(self):
        self.stopped = True
        self.reset()

    def pcm_observation(self, frame, result, now):
        """Validate internal CF1 evidence; never infer continuity from sequence alone."""
        audio = frame.get('audio', {})
        proof = result.get('pcm_continuity', {})
        source = result.get('source_completed_at')
        start = audio.get('sample_start')
        if (result.get('frontend') != 'CF1A' or result.get('cf1_reset') or
                proof.get('policy') != 'CF1_PCM_GAPS_V1' or not audio.get('valid') or
                type(start) is not int or start < 0 or start % 512 or
                audio.get('sample_count') != 1024 or type(audio.get('epoch')) is not int or
                proof.get('epoch') != audio['epoch'] or proof.get('sample_start') != start or
                proof.get('sequence') != frame['sequence']):
            return None, 'pcm_evidence_unavailable'
        if (not isinstance(source, (int, float)) or not math.isfinite(source) or
                not 0 <= now-source < .75):
            return None, 'pcm_window_stale'
        return (audio['epoch'], start), None

    def apply(self, frame, result, threshold):
        status = frame['status']
        measured = bool(status & (1 << 17) and status & (1 << 5) and not status & 8)
        level = frame['energy'] if measured else None
        reason = None
        if self.stopped:
            reason = 'stopped_or_drain'
        elif result['bridge_status'] or result['api_status']:
            reason = 'solver_error'
        elif frame['fault'] or status & (1 << 20) or status >> 24:
            reason = 'fault_or_cancelled'
        elif status & 8:
            reason = 'bist_no_acoustic_output'
        elif not measured or type(level) is not int or not 0 <= level <= 0xffffff:
            reason = 'level_unavailable'
        elif level < threshold:
            reason = 'below_volume_threshold'
        out = dict(valid=False, updated=False, azimuth_deg=None, elevation_deg=None,
                   azimuth_valid=False, elevation_valid=False, vector=None, reason='collecting_window')
        detail = dict(window_size=self.window, min_valid=self.minimum, complete=False,
                      frame_count=0, valid_count=0, inlier_count=0, reset_reason=reason)
        now = self.clock()
        observation = None
        if reason is None and self.verified_pcm_gaps:
            observation, reason = self.pcm_observation(frame, result, now)
            detail['reset_reason'] = reason
        detail['gap_bridged'] = False
        raw_valid = reason is None and bool(result['direction_valid'])
        raw_vector = None
        if raw_valid:
            try:
                raw_vector = unit([result[k] for k in ('ux', 'uy', 'uz')])
            except (KeyError, ValueError, TypeError):
                reason = detail['reset_reason'] = 'solver_error'
                raw_valid = False
        if reason:
            self.reset()
            out['reason'] = reason
        else:
            seq = frame['sequence']
            gap = self.last_sequence is not None and seq != (self.last_sequence + 1) & 0xffffffff
            reset = None
            if self.verified_pcm_gaps:
                if self.last_audio is not None:
                    proof = result['pcm_continuity']
                    advance = observation[1]-self.last_audio[1]
                    seq_advance = (seq-self.last_sequence) & 0xffffffff
                    linked = (proof.get('verified') is True and observation[0] == self.last_audio[0] and
                              proof.get('previous_start') == self.last_audio[1] and
                              proof.get('previous_sequence') == self.last_sequence and
                              0 < advance <= 16*512 and 0 < seq_advance <= 16)
                    if not linked:
                        reset = 'pcm_discontinuity'
                    elif gap:
                        detail['gap_bridged'] = True
                if self.count and (now-self.group_host_start >= .75 or
                        observation[1]-self.group_source_start >= 36000):
                    reset = reset or 'window_age_limit'
                if reset:
                    self.reset()
                    detail['gap_bridged'] = False
                if self.count == 0:
                    self.group_host_start, self.group_source_start = now, observation[1]
                self.last_audio = observation
            elif gap:
                self.reset()
                reset = 'sequence_gap'
            detail['reset_reason'] = reset
            self.last_sequence = seq
            self.count += 1
            if raw_valid:
                self.vectors.append(raw_vector)
            detail.update(frame_count=self.count, valid_count=len(self.vectors))
            if self.count == self.window:
                detail['complete'] = True
                out['reason'] = 'insufficient_valid'
                if len(self.vectors) >= self.minimum:
                    # Squared chord-distance medoid: maximize dot(v, sum(v)).
                    # This is exactly the member minimizing summed squared
                    # Euclidean distance on the unit sphere, in O(N) work.
                    # Do not add N*N acos calls to the acquisition service path.
                    total = tuple(sum(v[i] for v in self.vectors) for i in range(3))
                    center = max(self.vectors, key=lambda a: sum(x*y for x, y in zip(a, total)))
                    cutoff = math.cos(math.radians(RADIUS))
                    kept = [v for v in self.vectors
                            if sum(x*y for x, y in zip(center, v)) >= cutoff-1e-12]
                    detail['inlier_count'] = len(kept)
                    out['reason'] = 'insufficient_consensus'
                    if len(kept) >= self.minimum and 3*len(kept) >= 2*len(self.vectors):
                        try:
                            candidate = unit([sum(v[i] for v in kept) for i in range(3)])
                            changed = self.held is None or separation(candidate, self.held) >= DEADBAND
                            if changed:
                                self.held = candidate
                            out.update(angles(self.held), valid=True, updated=changed,
                                       reason='target_updated' if changed else 'within_deadband')
                        except ValueError:
                            out['reason'] = 'undefined_mean'
                if not out['valid']:
                    self.held = None
                self.count = 0
                self.vectors = []
        return dict(direction_output=out, angle_filter=detail,
                    frame_direction=dict(valid=raw_valid, vector=raw_vector),
                    volume=dict(level_counts=level, threshold_counts=threshold, measured=measured,
                                unit='mean_abs_dc_removed_pcm'))
