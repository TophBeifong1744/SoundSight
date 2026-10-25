"""Opt-in 3D direction filtering and software-only two-axis setpoints.

Nothing imports PYNQ, writes hardware, or changes Solver3D's result schema.
All timestamps are seconds from ONE caller-owned monotonic timebase. Sequences
strictly increase within a session/target; change session before a counter wraps.
HOLD preserves the last accepted observation's expiry, never refreshes it.
Configuration defaults are reference tuning values, not physical calibration.
"""
import copy
from dataclasses import dataclass
import math
from collections.abc import Mapping


def _finite(value, name):
    if type(value) not in (int, float):
        raise ValueError(name + ' must be a finite number (not bool)')
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(name + ' is outside finite float range') from exc
    if not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    return value


def _time(value, name):
    value = _finite(value, name)
    if value < 0:
        raise ValueError(name + ' must be nonnegative')
    return value


def _unit(vector):
    if not isinstance(vector, (list, tuple)) or len(vector) != 3:
        raise ValueError('direction must contain three numbers')
    values = tuple(_finite(x, 'direction') for x in vector)
    scale = max(abs(x) for x in values)
    if scale == 0:
        raise ValueError('zero direction')
    values = tuple(x / scale for x in values)
    norm = math.sqrt(sum(x*x for x in values))
    return tuple(x / norm for x in values)


def _dot(a, b):
    return max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b))))


def angular_distance_deg(a, b):
    """Geodesic separation of finite, nonzero 3-vectors in degrees."""
    return math.degrees(math.acos(_dot(_unit(a), _unit(b))))


def _slerp(a, b, fraction):
    cosine = _dot(a, b)
    if cosine > 0.999999:
        return _unit(tuple((1-fraction)*x + fraction*y for x, y in zip(a, b)))
    # Calls are bounded by gate/candidate radius < 180 degrees. A confirmed
    # antipodal jump is installed directly instead of interpolating an arc.
    angle = math.acos(cosine)
    sa = math.sin((1-fraction)*angle) / math.sin(angle)
    sb = math.sin(fraction*angle) / math.sin(angle)
    return _unit(tuple(sa*x + sb*y for x, y in zip(a, b)))


def _angles(vector):
    x, y, z = vector
    horizontal = math.hypot(x, y)
    return (None if horizontal < 1e-9 else math.degrees(math.atan2(y, x)),
            math.degrees(math.atan2(z, horizontal)))


@dataclass(frozen=True)
class DirectionFilterConfig:
    smoothing_tau_s: float = 0.10
    hold_s: float = 0.25
    max_age_s: float = 0.15
    gate_deg: float = 35.0
    candidate_radius_deg: float = 15.0
    confirm_frames: int = 3
    candidate_max_gap_s: float = 0.15
    deadband_deg: float = 3.0

    def __post_init__(self):
        for key in ('smoothing_tau_s', 'hold_s', 'max_age_s',
                    'candidate_max_gap_s'):
            if _finite(getattr(self, key), key) <= 0:
                raise ValueError(key + ' must be positive')
        if self.max_age_s > self.hold_s:
            raise ValueError('max_age_s cannot exceed hold_s')
        if not 0 < _finite(self.gate_deg, 'gate_deg') < 180:
            raise ValueError('gate_deg must lie in (0,180)')
        if not 0 < _finite(self.candidate_radius_deg, 'candidate_radius_deg') < 90:
            raise ValueError('candidate_radius_deg must lie in (0,90)')
        if not 0 <= _finite(self.deadband_deg, 'deadband_deg') < self.gate_deg:
            raise ValueError('deadband_deg must lie in [0,gate_deg)')
        if type(self.confirm_frames) is not int or not 1 <= self.confirm_frames <= 1000:
            raise ValueError('confirm_frames must be an integer in [1,1000]')


class DirectionFilter3D:
    """Bounded-state spherical smoother with consecutive-candidate reacquisition.

    Input is a Solver3D result, or {'direction_valid': 1, 'direction': [x,y,z]}.
    Invalid solver status overrides a supplied direction. The fitted solver
    vector is normalized here; azimuth_valid is not required at the poles.
    Session/target changes discard the old direction and require acquisition.
    Old-session packets must be discarded by the caller's stream router: IDs
    identify contexts, not an ordering of sessions or a person's identity.
    """
    def __init__(self, config=None):
        self.config = config if config is not None else DirectionFilterConfig()
        if not isinstance(self.config, DirectionFilterConfig):
            raise ValueError('expected DirectionFilterConfig')
        self._context = None
        self._now = None
        self._clear_context()

    def _clear_context(self):
        self._seen_sequence = self._seen_time = None
        self._smooth = self._published = None
        self._accepted_time = self._accepted_sequence = None
        self._expiry = None
        self._clear_candidate()

    def _clear_candidate(self):
        self._candidate = None
        self._candidate_count = 0
        self._candidate_time = None

    def _expire(self, now):
        if self._expiry is not None and now >= self._expiry:
            self._smooth = self._published = None
        # A candidate timestamp is capture time, not arrival time. Permit the
        # configured input age so delayed but consecutive frames can acquire.
        if self._candidate_time is not None and now-self._candidate_time > (
                self.config.candidate_max_gap_s + self.config.max_age_s):
            self._clear_candidate()

    def _output(self, now, reason, fresh=False, updated=False, reject=False):
        self._expire(now)
        valid = self._published is not None and not reject
        vector = self._published if valid else None
        azimuth, elevation = _angles(vector) if valid else (None, None)
        return dict(schema=1, valid=valid, vector=vector,
                    azimuth_deg=azimuth, elevation_deg=elevation,
                    reason=reason, state=('TRACK' if fresh else 'HOLD') if valid
                    else ('ACQUIRE' if self._candidate is not None else 'LOST'),
                    fresh=bool(valid and fresh), updated=bool(valid and updated),
                    timestamp_s=self._accepted_time, valid_until_s=self._expiry,
                    age_s=(None if self._accepted_time is None else
                           max(0.0, now-self._accepted_time)),
                    sequence=self._accepted_sequence,
                    session_id=self._context[0] if self._context else None,
                    target_id=self._context[1] if self._context else None)

    def poll(self, *, now_s):
        """Read freshness without accepting observations or extending expiry."""
        now = _time(now_s, 'now_s')
        if self._now is not None and now < self._now:
            self._clear_candidate()
            return self._output(self._now, 'clock_reversed', reject=True)
        self._now = now
        self._expire(now)
        return self._output(now, 'held' if self._published is not None else 'expired')

    @staticmethod
    def _extract(result):
        if not isinstance(result, Mapping):
            raise ValueError('result must be a mapping')
        valid = result.get('direction_valid')
        if type(valid) not in (int, bool) or valid != 1:
            raise ValueError('invalid direction')
        for key in ('api_status', 'bridge_status', 'first_error', 'reason'):
            if key in result and (type(result[key]) is not int or result[key] != 0):
                raise ValueError('solver failure')
        if 'direction' in result:
            return _unit(result['direction'])
        return _unit(tuple(result[key] for key in ('ux', 'uy', 'uz')))

    def update(self, result, *, timestamp_s, now_s, sequence, session_id, target_id):
        now, stamp = _time(now_s, 'now_s'), _time(timestamp_s, 'timestamp_s')
        if type(sequence) is not int or sequence < 0:
            raise ValueError('sequence must be a nonnegative integer')
        if any(not isinstance(v, str) or not v for v in (session_id, target_id)):
            raise ValueError('session_id and target_id must be nonempty strings')
        raw = copy.deepcopy(result)

        def answer(reason, **kw):
            return dict(raw_result=raw, filtered_direction=self._output(now, reason, **kw))

        if self._now is not None and now < self._now:
            self._clear_candidate()
            return dict(raw_result=raw, filtered_direction=self._output(
                self._now, 'clock_reversed', reject=True))
        self._now = now
        context = session_id, target_id
        if context != self._context:
            self._clear_context()
            self._context = context
        if stamp > now:
            self._clear_candidate()
            return answer('future_timestamp', reject=True)
        if now-stamp > self.config.max_age_s:
            self._clear_candidate()
            return answer('stale_input', reject=True)
        if self._seen_sequence is not None and (sequence <= self._seen_sequence
                                               or stamp <= self._seen_time):
            self._clear_candidate()
            return answer('out_of_order', reject=True)
        self._seen_sequence, self._seen_time = sequence, stamp
        self._expire(now)
        if isinstance(result, Mapping) and 'sequence' in result and (
                type(result['sequence']) is not int or result['sequence'] != sequence):
            self._clear_candidate()
            return answer('sequence_mismatch', reject=True)
        try:
            direction = self._extract(result)
        except (ValueError, KeyError, TypeError):
            self._clear_candidate()
            return answer('invalid_input' if self._published is not None else 'invalid_or_expired')

        if self._smooth is None or angular_distance_deg(self._smooth, direction) > self.config.gate_deg:
            if (self._candidate is None
                    or stamp-self._candidate_time > self.config.candidate_max_gap_s
                    or angular_distance_deg(self._candidate, direction) > self.config.candidate_radius_deg):
                self._candidate, self._candidate_count = direction, 1
            else:
                self._candidate_count += 1
                self._candidate = _slerp(self._candidate, direction, 1/self._candidate_count)
            self._candidate_time = stamp
            if self._candidate_count < self.config.confirm_frames:
                return answer('reacquiring' if self._published is not None else 'acquiring')
            reason = 'reacquired' if self._accepted_time is not None else 'acquired'
            self._smooth = self._published = self._candidate
            self._clear_candidate()
            changed = True
        else:
            self._clear_candidate()
            alpha = -math.expm1(-(stamp-self._accepted_time)/self.config.smoothing_tau_s)
            self._smooth = _slerp(self._smooth, direction, alpha)
            changed = angular_distance_deg(self._smooth, self._published) > self.config.deadband_deg
            if changed:
                self._published = self._smooth
            reason = 'target_updated' if changed else 'within_deadband'
        self._accepted_time, self._accepted_sequence = stamp, sequence
        self._expiry = stamp+self.config.hold_s
        return answer(reason, fresh=True, updated=changed)


@dataclass(frozen=True)
class DualAxisConfig:
    """Explicit rig calibration; rotation maps array vectors into mount frame.

    Mount frame: +X forward, +Y positive yaw, +Z up; angles are mathematical
    yaw/pitch degrees, NOT servo PWM/degrees. Limits are hard non-wrapping
    mechanical limits. This reference models orthogonal intersecting axes.
    """
    rotation: tuple
    yaw_limits_deg: tuple
    pitch_limits_deg: tuple
    max_yaw_rate_deg_s: float
    max_pitch_rate_deg_s: float
    pole_enter_deg: float = 85.0
    pole_exit_deg: float = 80.0
    max_update_gap_s: float = 0.25
    target_timeout_s: float = 0.25

    def __post_init__(self):
        try:
            rows = tuple(tuple(_finite(x, 'rotation') for x in row) for row in self.rotation)
        except TypeError as exc:
            raise ValueError('rotation must be 3x3') from exc
        if len(rows) != 3 or any(len(row) != 3 for row in rows):
            raise ValueError('rotation must be 3x3')
        for i in range(3):
            for j in range(3):
                if abs(sum(rows[i][k]*rows[j][k] for k in range(3))-(i == j)) > 1e-6:
                    raise ValueError('rotation must be orthonormal')
        a, b, c = rows
        determinant = (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
                       + a[2]*(b[0]*c[1]-b[1]*c[0]))
        if abs(determinant-1) > 1e-6:
            raise ValueError('rotation determinant must be +1')
        object.__setattr__(self, 'rotation', rows)
        for key in ('yaw_limits_deg', 'pitch_limits_deg'):
            bounds = getattr(self, key)
            if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
                raise ValueError(key + ' must contain two ordered angles')
            lo, hi = (_finite(x, key) for x in bounds)
            if not lo < hi or hi-lo > 360:
                raise ValueError(key + ' span must lie in (0,360]')
            if key == 'pitch_limits_deg' and not -90 <= lo < hi <= 90:
                raise ValueError('pitch limits must lie in [-90,90]')
            object.__setattr__(self, key, (lo, hi))
        for key in ('max_yaw_rate_deg_s', 'max_pitch_rate_deg_s',
                    'max_update_gap_s', 'target_timeout_s'):
            if _finite(getattr(self, key), key) <= 0:
                raise ValueError(key + ' must be positive')
        if not 0 <= _finite(self.pole_exit_deg, 'pole_exit_deg') < _finite(
                self.pole_enter_deg, 'pole_enter_deg') < 90:
            raise ValueError('pole hysteresis requires 0 <= exit < enter < 90')


class DualAxisTracker:
    """Pure setpoint model, disabled per call unless enable=True.

    Initial pose/time must come from the caller's known rig state. Internal pose
    is the previous commanded setpoint, not encoder feedback; reconstruct after
    a rejected/unexecuted command or external movement. No acceleration, PWM,
    emergency-stop, or physical collision controller is implied.
    """
    def __init__(self, config, *, initial_yaw_deg, initial_pitch_deg, initial_time_s):
        if not isinstance(config, DualAxisConfig):
            raise ValueError('expected DualAxisConfig')
        self.config = config
        self._yaw = _finite(initial_yaw_deg, 'initial_yaw_deg')
        self._pitch = _finite(initial_pitch_deg, 'initial_pitch_deg')
        for value, bounds in ((self._yaw, config.yaw_limits_deg),
                              (self._pitch, config.pitch_limits_deg)):
            if not bounds[0] <= value <= bounds[1]:
                raise ValueError('initial pose outside configured limits')
        self._now = _time(initial_time_s, 'initial_time_s')
        self._pole = False
        self._pole_yaw = self._yaw
        self._context = None
        self._source_time = self._source_expiry = None
        self._source_vector = None

    def _yaw_target(self, yaw):
        lo, hi = self.config.yaw_limits_deg
        kmin, kmax = math.ceil((lo-yaw)/360), math.floor((hi-yaw)/360)
        if kmin <= kmax:
            candidates = [yaw+360*k for k in range(kmin, kmax+1)]
            return min(candidates, key=lambda x: abs(x-self._yaw)), False
        # Unreachable ray: choose closest endpoint in angular space. Hard limits
        # are not circular: do not wrap a command through a mechanical stop.
        target = min((lo, hi), key=lambda x: (abs((x-yaw+180) % 360-180), abs(x-self._yaw)))
        return target, True

    def update(self, direction, *, now_s, enable=False):
        now = _time(now_s, 'now_s')
        if type(enable) is not bool:
            raise ValueError('enable must be bool')
        dt = now-self._now

        def stopped(reason):
            return dict(command_valid=False, yaw_deg=None, pitch_deg=None,
                        reason=reason, rate_limited=False, limit_clamped=False,
                        pole_hold=self._pole, dt_s=max(0.0, dt))

        if dt <= 0:
            return stopped('nonincreasing_time')
        self._now = now
        if not enable:
            return stopped('disabled')
        if dt > self.config.max_update_gap_s:
            return stopped('update_gap')
        try:
            if not isinstance(direction, Mapping) or direction.get('valid') is not True:
                return stopped('invalid_direction')
            vector = _unit(direction['vector'])
            stamp = _time(direction['timestamp_s'], 'timestamp_s')
            expiry = _time(direction['valid_until_s'], 'valid_until_s')
            context = direction['session_id'], direction['target_id']
            if any(not isinstance(x, str) or not x for x in context):
                return stopped('invalid_context')
            if stamp > now or expiry <= stamp or now >= expiry or now-stamp >= self.config.target_timeout_s:
                return stopped('stale_or_future_direction')
        except (KeyError, TypeError, ValueError):
            return stopped('invalid_direction')
        if context != self._context:
            self._context = context
            self._source_time = self._source_expiry = None
            self._source_vector = None
            self._pole = False
        if self._source_time is not None and (stamp < self._source_time or
                (stamp == self._source_time and expiry != self._source_expiry)):
            return stopped('source_time_or_expiry_changed')
        # A repeated observation may be used during bounded HOLD, but its
        # direction is immutable. Changing it requires a new source timestamp.
        if stamp == self._source_time and vector != self._source_vector:
            return stopped('source_vector_changed')
        self._source_time, self._source_expiry = stamp, expiry
        self._source_vector = vector
        vector = _unit(tuple(sum(x*y for x, y in zip(row, vector)) for row in self.config.rotation))
        yaw, pitch = _angles(vector)
        if abs(pitch) >= self.config.pole_enter_deg and not self._pole:
            self._pole, self._pole_yaw = True, self._yaw
        elif abs(pitch) <= self.config.pole_exit_deg:
            self._pole = False
        if self._pole:
            target_yaw, yaw_clamped = self._pole_yaw, False
        else:
            # No atan2(0,0) yaw is generated: a pole always enters hold above.
            target_yaw, yaw_clamped = self._yaw_target(yaw)
        lo, hi = self.config.pitch_limits_deg
        target_pitch = max(lo, min(hi, pitch))
        yaw_step = self.config.max_yaw_rate_deg_s*dt
        pitch_step = self.config.max_pitch_rate_deg_s*dt
        limited = abs(target_yaw-self._yaw) > yaw_step or abs(target_pitch-self._pitch) > pitch_step
        self._yaw += max(-yaw_step, min(yaw_step, target_yaw-self._yaw))
        self._pitch += max(-pitch_step, min(pitch_step, target_pitch-self._pitch))
        return dict(command_valid=True, yaw_deg=self._yaw, pitch_deg=self._pitch,
                    reason='pole_hold' if self._pole else 'tracking',
                    rate_limited=limited, limit_clamped=yaw_clamped or target_pitch != pitch,
                    pole_hold=self._pole, dt_s=dt)
