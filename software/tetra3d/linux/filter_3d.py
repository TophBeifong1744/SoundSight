"""Bounded spherical direction filter; no hardware or actuator permission.

The 2-D policy is extended to unit vectors: 20 frames / 12 valid by default,
10 degree inliers, two-thirds consensus and a 3 degree spatial deadband.
Low level, faults and sequence gaps revoke the previous target.
"""
import math
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
    def __init__(self, window_frames=20, min_valid=12):
        self.window, self.minimum = validate_window(window_frames, min_valid)
        self.stopped = False
        self.reset()

    def reset(self):
        self.count = 0
        self.vectors = []
        self.held = None
        self.last_sequence = None

    def stop(self):
        self.stopped = True
        self.reset()

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
            if self.last_sequence is not None and seq != (self.last_sequence + 1) & 0xffffffff:
                self.reset()
                detail['reset_reason'] = 'sequence_gap'
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
